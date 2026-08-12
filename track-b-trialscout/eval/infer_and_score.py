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

# Every raw source, not just the main pull: --gold can point at the rare-class diagnostic
# (ADR-0020) or the augment, whose records live in their own files.
# Every compact-record source. studies_full.jsonl is the untouched CT.gov archive -- same
# directory, different shape (nctId lives under protocolSection), so it is skipped by name
# AND by a defensive check. Globbing a directory means anything dropped in it becomes input.
RAW = {}
for _f in sorted((ROOT / "data" / "raw").glob("*.jsonl")):
    if _f.name == "studies_full.jsonl":
        continue
    for _l in _f.read_text().splitlines():
        if _l.strip():
            _r = json.loads(_l)
            if "nct_id" in _r:
                RAW[_r["nct_id"]] = _r
def load_gold(stem: str):
    return [json.loads(line) for line in (ROOT / "data" / "gold" / f"{stem}.jsonl").read_text().splitlines()
            if line.strip()]


GOLD_TEST = load_gold("test")


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
    ap.add_argument("--restart", action="store_true",
                    help="discard an existing preds_<label>.jsonl instead of resuming from it")
    ap.add_argument("--memory-limit-gb", type=float, default=8.0,
                    help="cap MLX's allocation. Apple Silicon shares ONE pool between the system "
                         "and the GPU, so an unbounded eval does not just run slowly -- it evicts "
                         "the desktop to swap and the whole machine crawls. Measured: batch 16 on "
                         "a 24 GB M5 caused ~7 GB of pageouts. 0 disables the cap.")
    ap.add_argument("--gold", type=str, default="test",
                    help="gold file stem under data/gold/. 'test' is the frozen 150-trial headline "
                         "set; 'rare_diagnostic' is the held-out rare-class instrument (ADR-0020), "
                         "which is NOT the headline and must be reported separately.")
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
    gold_rows = load_gold(args.gold)
    test_set = gold_rows[:args.limit] if args.limit else gold_rows

    from mlx_lm import load, generate, batch_generate
    if args.memory_limit_gb:
        import mlx.core as mx
        mx.set_memory_limit(int(args.memory_limit_gb * 1e9))
        mx.set_cache_limit(int(args.memory_limit_gb * 0.25 * 1e9))
        print(f"[{args.label}] MLX capped at {args.memory_limit_gb} GB so the desktop stays usable",
              flush=True)
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

    # Resume: generations are ~4-8 s each, so an interrupted run must not lose them. Every
    # parsed readout is appended to disk as it is produced, and an existing file is picked up.
    out_dir = ROOT / "eval"
    preds_path = out_dir / f"preds_{args.label}.jsonl"
    preds, parsed_ok, t0 = {}, 0, time.time()
    if preds_path.exists() and not args.restart:
        for line in preds_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                preds[r["nct_id"]] = r
        parsed_ok = len(preds)
        print(f"[{args.label}] resuming: {parsed_ok} readouts already on disk "
              f"(--restart to discard them)", flush=True)
    todo = [g for g in test_set if g["nct_id"] not in preds]
    preds_f = preds_path.open("a")

    bs = max(1, args.batch_size)
    for start in range(0, len(todo), bs):
        chunk = todo[start:start + bs]
        prompts = [prompt_for(g) for g in chunk]
        if bs == 1:
            texts = [generate(model, tok, prompt=prompts[0], max_tokens=args.max_tokens, verbose=False)]
        else:
            resp = batch_generate(model, tok, prompts=[tok.encode(p) for p in prompts],
                                  max_tokens=args.max_tokens, verbose=False)
            texts = resp.texts
        for g, text in zip(chunk, texts):
            before = len(preds)
            parsed_ok += record(g["nct_id"], text)
            if len(preds) > before:                       # flush immediately: kill-safe
                preds_f.write(json.dumps(preds[g["nct_id"]]) + "\n")
        preds_f.flush()
        done = min(start + bs, len(todo))
        rate = (time.time() - t0) / max(done, 1)
        print(f"  [{args.label}] {done}/{len(todo)}  parsed_ok={parsed_ok}  "
              f"({rate:.2f}s/trial, ~{rate*(len(todo)-done)/60:.0f} min left)", flush=True)
    preds_f.close()

    res = score(test_set, preds)
    res["_valid_json"] = round(parsed_ok / len(test_set), 3)
    (out_dir / f"score_{args.label}.json").write_text(json.dumps(res, indent=2))
    print(f"\n[{args.label}] overall_structured={res['_overall_structured']}  "
          f"valid_json={res['_valid_json']}  (n={res['_n']})")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
