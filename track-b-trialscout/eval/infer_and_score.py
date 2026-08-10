"""Run a fine-tuned student on the held-out test trials and score it vs the baseline.

Loads base model + LoRA adapter, generates a readout for each of the 150 test trials,
parses the JSON, and scores the structured fields against the gold test set using the
same metrics as the majority-class baseline (harness.score).

Run:  uv run python track-b-trialscout/eval/infer_and_score.py \
          --model mlx-community/Qwen3-4B-Instruct-2507-4bit \
          --adapter track-b-trialscout/train/adapters/qwen --label qwen
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "train"))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "schema"))
from format_for_mlx import build_prompt  # noqa: E402  (after sys.path.insert) exact same prompt as training
from harness import score  # noqa: E402  (after sys.path.insert) same metrics as the baseline
from normalize import snap_to_enum  # noqa: E402  same enum-snap the server applies, so eval == deployed

SCHEMA = json.loads((ROOT / "schema" / "trial_readout.schema.json").read_text())


def enum_appendix() -> str:
    """The allowed values, spelled out — for scoring an UNTUNED model fairly.

    `build_prompt` names the fields but never lists their vocabularies, because the student
    learns those from 1,192 worked examples. A base model has never seen them, so scoring it
    on that prompt measures "did you guess our menu", not "can you do the task" — it answers
    `other` for everything and floors. This appendix supplies the menu and nothing else: no
    rules, no examples, no guidance on how to choose. The gap between the two conditions is
    how much of fine-tuning's gain is vocabulary rather than judgement.
    """
    P = SCHEMA["properties"]
    lines = ["", "Allowed values:"]
    for f in ("phase", "intervention_class", "primary_endpoint_type", "sponsor_type"):
        lines.append(f"- {f}: {P[f]['enum']}")
    for f in ("modalities", "risk_flags"):
        lines.append(f"- {f} (array, choose zero or more): {P[f]['items']['enum']}")
    lines.append('- est_readout: "H1 YYYY" or "H2 YYYY" (from primary_completion_date; '
                 'months 01-06 -> H1, 07-12 -> H2), or "unknown".')
    return "\n".join(lines)

RAW = {json.loads(l)["nct_id"]: json.loads(l)
       for l in (ROOT / "data" / "raw" / "trials.jsonl").read_text().splitlines() if l.strip()}
GOLD_TEST = [json.loads(l) for l in (ROOT / "data" / "gold" / "test.jsonl").read_text().splitlines() if l.strip()]


def extract_json(text: str) -> dict | None:
    """Pull the first balanced {...} object out of the model's output."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--adapter", default=None,
                    help="LoRA adapter path. OMIT to score the UNTUNED base model through the\n                         identical path -- same prompt, same JSON parse, same normalizer, same\n                         scorer. That is the apples-to-apples fine-tuning comparison.")
    ap.add_argument("--label", required=True)
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--limit", type=int, default=0, help="score only the first N test trials (0 = all)")
    ap.add_argument("--batch-size", type=int, default=1,
                    help="prompts decoded together. DEFAULT 1 (sequential) ON PURPOSE -- see below. "
                         "Batching amortises the per-token weight read across prompts, and a "
                         "16-prompt micro-benchmark on an M5 showed 2.5x (5.85 -> 2.33 s/trial). "
                         "Measured end to end over the full 150 it was only ~1.4x, because a batch "
                         "runs until its SLOWEST member finishes and output lengths vary widely. "
                         "It also CHANGED 6 of 150 predictions (overall 0.939 -> 0.936): different "
                         "padding, different numerics. A 1.4x speedup is not worth a score that "
                         "cannot be reconciled with the published one. Use >1 only for throughput "
                         "work where exact reproduction does not matter.")
    ap.add_argument("--with-enums", action="store_true",
                    help="append the allowed enum values to the prompt. Use for UNTUNED baselines: "
                         "the training prompt never lists them, so a base model cannot know them.")
    args = ap.parse_args()
    test_set = GOLD_TEST[:args.limit] if args.limit else GOLD_TEST

    from mlx_lm import load, generate, batch_generate
    if args.adapter:
        print(f"[{args.label}] loading {args.model} + adapter {args.adapter} ...", flush=True)
        model, tok = load(args.model, adapter_path=args.adapter)
    else:
        print(f"[{args.label}] loading {args.model} (UNTUNED base, no adapter) ...", flush=True)
        model, tok = load(args.model)

    def prompt_for(g):
        user = build_prompt(RAW[g["nct_id"]]) + (enum_appendix() if args.with_enums else "")
        return tok.apply_chat_template([{"role": "user", "content": user}],
                                       add_generation_prompt=True, tokenize=False)

    def record(nct_id, text):
        obj = extract_json(text)
        if obj:
            preds[nct_id] = snap_to_enum({"nct_id": nct_id, **obj})
            return 1
        return 0

    preds, parsed_ok, t0 = {}, 0, time.time()
    bs = max(1, args.batch_size)
    for start in range(0, len(test_set), bs):
        chunk = test_set[start:start + bs]
        prompts = [prompt_for(g) for g in chunk]
        if bs == 1:
            texts = [generate(model, tok, prompt=prompts[0], max_tokens=args.max_tokens, verbose=False)]
        else:
            resp = batch_generate(model, tok, prompts=[tok.encode(p) for p in prompts],
                                  max_tokens=args.max_tokens, verbose=False)
            texts = resp.texts
        for g, text in zip(chunk, texts):
            parsed_ok += record(g["nct_id"], text)
        done = min(start + bs, len(test_set))
        print(f"  [{args.label}] {done}/{len(test_set)}  parsed_ok={parsed_ok}  "
              f"({(time.time()-t0)/done:.2f}s/trial)", flush=True)

    # Save the generations BEFORE scoring. Generation is ~20 minutes of local compute and
    # scoring is milliseconds; a scorer bug should never throw the expensive half away.
    out_dir = ROOT / "eval"
    (out_dir / f"preds_{args.label}.jsonl").write_text(
        "".join(json.dumps(p) + "\n" for p in preds.values()))
    res = score(test_set, preds)
    res["_valid_json"] = round(parsed_ok / len(test_set), 3)
    (out_dir / f"score_{args.label}.json").write_text(json.dumps(res, indent=2))
    print(f"\n[{args.label}] overall_structured={res['_overall_structured']}  "
          f"valid_json={res['_valid_json']}  (n={res['_n']})")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
