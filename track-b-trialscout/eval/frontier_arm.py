"""Score a frontier model on the same test set, with the schema but WITHOUT the teacher scaffold.

Why this exists. The gold labels ARE the teacher's output, so scoring the teacher against
gold returns 1.000 by construction. That is not a measurement, and it leaves the project's
central claim — "a small fine-tuned model approaches frontier performance on a narrow task"
— resting on a comparison with no denominator.

This arm supplies one. Same frontier model, same 150 trials, same scorer, same forced
tool-use contract, but stripped of everything the teacher run was given beyond the schema
itself: no decision rules, no worked examples, no few-shot prefix. It answers "how much of
the teacher's quality is the MODEL, and how much is the scaffolding we wrote around it?"

Read the honest limitation before quoting it: the gold was produced by this same model
family with the scaffold, so this is a scaffold-ablation, not an independent referee. It
bounds the value of the prompt engineering; it does not prove the labels are correct.

Run:  uv run python track-b-trialscout/eval/frontier_arm.py --model claude-sonnet-5
      uv run python track-b-trialscout/eval/frontier_arm.py --limit 5   # smoke test
"""
from __future__ import annotations
import argparse, json, sys, threading, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
import anthropic

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT.parent / ".env")
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "train"))
sys.path.insert(0, str(ROOT / "schema"))
from harness import score            # noqa: E402  same metrics as every other arm
from normalize import snap_to_enum   # noqa: E402  same normalizer as the deployed path
from format_for_mlx import trial_input  # noqa: E402  same trimmed record the student sees
from make_gold import PRICING, request_kwargs, canonical  # noqa: E402  one pricing source

SCHEMA = json.loads((ROOT / "schema" / "trial_readout.schema.json").read_text())
GOLD_TEST = [json.loads(l) for l in (ROOT / "data" / "gold" / "test.jsonl").read_text().splitlines() if l.strip()]
RAW = {json.loads(l)["nct_id"]: json.loads(l)
       for l in (ROOT / "data" / "raw" / "trials.jsonl").read_text().splitlines() if l.strip()}

# The ENTIRE system prompt. Deliberately minimal: this is the control condition, so it gets
# the contract and nothing else. Every rule, worked example and disambiguation that
# make_gold.py supplies is withheld on purpose — that difference is what is being measured.
SYSTEM = ("You are an analyst. Read the oncology clinical-trial record and emit a structured "
          "readout by calling the `emit_readout` tool. Field definitions are in the tool schema.")

TOOL = {"name": SCHEMA["name"], "description": SCHEMA["description"],
        "input_schema": {"type": "object", "properties": SCHEMA["properties"],
                         "required": SCHEMA["required"]}}

client = anthropic.Anthropic()


def one(trial: dict, nct: str, model: str, effort: str, stop: threading.Event):
    if stop.is_set():
        return None
    price = PRICING.get(model, PRICING["claude-sonnet-4-6"])
    p_in, p_out = price["in"] / 1e6, price["out"] / 1e6
    for attempt in range(4):
        try:
            r = client.messages.create(
                model=model, system=SYSTEM, tools=[TOOL],
                tool_choice={"type": "tool", "name": SCHEMA["name"]},
                messages=[{"role": "user",
                           "content": f"TRIAL:\n{json.dumps(trial, ensure_ascii=False)}\nReturn the readout."}],
                **request_kwargs(model, effort),
            )
            u = r.usage
            cost = p_in * u.input_tokens + p_out * u.output_tokens
            out = next((b.input for b in r.content if b.type == "tool_use"), None)
            if out is None:
                return {"nct_id": nct, "cost": cost, "readout": None}
            return {"nct_id": nct, "cost": cost,
                    "readout": snap_to_enum(canonical({**out, "nct_id": nct}))}
        except Exception as e:
            if attempt == 3:
                return {"nct_id": nct, "cost": 0.0, "readout": None,
                        "error": f"{type(e).__name__}: {str(e)[:120]}"}
            time.sleep(2 ** attempt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=str, default="claude-sonnet-5")
    ap.add_argument("--effort", type=str, default="medium", choices=["low", "medium", "high"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--cap", type=float, default=3.0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--label", type=str, default="frontier_zeroshot")
    args = ap.parse_args()

    test = GOLD_TEST[:args.limit] if args.limit else GOLD_TEST
    cost, lock, stop = [0.0], threading.Lock(), threading.Event()
    preds, failed = {}, 0

    print(f"[{args.label}] {args.model} (effort={args.effort}), n={len(test)}, cap ${args.cap}", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(one, trial_input(RAW[g["nct_id"]]), g["nct_id"], args.model, args.effort, stop)
                for g in test]
        for i, fut in enumerate(as_completed(futs), 1):
            res = fut.result()
            if not res:
                continue
            with lock:
                cost[0] += res.get("cost", 0.0)
            if res.get("readout"):
                preds[res["nct_id"]] = res["readout"]
            else:
                failed += 1
            if cost[0] >= args.cap and not stop.is_set():
                stop.set()
                print(f"COST CAP ${args.cap} reached — stopping.", flush=True)
            if i % 30 == 0:
                print(f"  {i}/{len(test)}  ok={len(preds)} failed={failed}  ${cost[0]:.2f}", flush=True)

    res = score(test, preds)
    res["_valid_output"] = round(len(preds) / len(test), 3)
    res["_model"] = args.model
    res["_effort"] = args.effort
    res["_spend_usd"] = round(cost[0], 3)
    res["_condition"] = ("frontier model, schema/tool contract only — no decision rules, no worked "
                         "examples, no few-shot prefix. Gold was produced by the same model WITH all "
                         "of those, so this is a scaffold ablation, not an independent referee.")
    (ROOT / "eval" / f"score_{args.label}.json").write_text(json.dumps(res, indent=2))
    (ROOT / "eval" / f"preds_{args.label}.jsonl").write_text(
        "".join(json.dumps(p) + "\n" for p in preds.values()))
    print(f"\n[{args.label}] overall_structured={res['_overall_structured']}  "
          f"spend=${cost[0]:.2f}  (n={res['_n']})")
    print(json.dumps({k: v for k, v in res.items() if not k.startswith("_")}, indent=2))


if __name__ == "__main__":
    main()
