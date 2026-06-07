"""Run a fine-tuned student on the held-out test trials and score it vs the baseline.

Loads base model + LoRA adapter, generates a readout for each of the 150 test trials,
parses the JSON, and scores the structured fields against the gold test set using the
same metrics as the majority-class baseline (harness.score).

Run:  uv run python track-b-trialscout/eval/infer_and_score.py \
          --model mlx-community/Qwen3-4B-Instruct-2507-4bit \
          --adapter track-b-trialscout/train/adapters/qwen --label qwen
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "train"))
sys.path.insert(0, str(ROOT / "eval"))
from format_for_mlx import build_prompt  # noqa: E402  (after sys.path.insert) exact same prompt as training
from harness import score  # noqa: E402  (after sys.path.insert) same metrics as the baseline

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
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--limit", type=int, default=0, help="score only the first N test trials (0 = all)")
    args = ap.parse_args()
    test_set = GOLD_TEST[:args.limit] if args.limit else GOLD_TEST

    from mlx_lm import load, generate
    print(f"[{args.label}] loading {args.model} + adapter {args.adapter} ...", flush=True)
    model, tok = load(args.model, adapter_path=args.adapter)

    preds, parsed_ok = {}, 0
    for i, g in enumerate(test_set, 1):
        raw = RAW[g["nct_id"]]
        prompt = tok.apply_chat_template(
            [{"role": "user", "content": build_prompt(raw)}],
            add_generation_prompt=True, tokenize=False)
        out = generate(model, tok, prompt=prompt, max_tokens=args.max_tokens, verbose=False)
        obj = extract_json(out)
        if obj:
            parsed_ok += 1
            preds[g["nct_id"]] = {"nct_id": g["nct_id"], **obj}
        if i % 30 == 0:
            print(f"  [{args.label}] {i}/{len(test_set)}  parsed_ok={parsed_ok}", flush=True)

    res = score(test_set, preds)
    res["_valid_json"] = round(parsed_ok / len(test_set), 3)
    out_dir = ROOT / "eval"
    (out_dir / f"preds_{args.label}.jsonl").write_text(
        "".join(json.dumps(p) + "\n" for p in preds.values()))
    (out_dir / f"score_{args.label}.json").write_text(json.dumps(res, indent=2))
    print(f"\n[{args.label}] overall_structured={res['_overall_structured']}  "
          f"valid_json={res['_valid_json']}  (n={res['_n']})")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
