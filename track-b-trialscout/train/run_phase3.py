"""Phase 3 orchestrator: LoRA fine-tune Qwen3-4B and Gemma 4 E2B on the gold set,
score each on the held-out test trials, compare to the majority-class baseline,
and pick the winner (ADR-0002, the measured base-model decision).

All local (MLX) — no API cost. Designed to run unattended.

Run:  uv run python track-b-trialscout/train/run_phase3.py
"""
from __future__ import annotations
import json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MLX_DATA = ROOT / "train" / "mlx_data"
ADAPTERS = ROOT / "train" / "adapters"
EVAL = ROOT / "eval"
LOGS = ROOT / "train" / "logs"

MODELS = [
    ("qwen",  "mlx-community/Qwen3-4B-Instruct-2507-4bit"),
    ("gemma", "mlx-community/gemma-4-E2B-it-4bit"),
]
ITERS, BATCH, LR, MAXSEQ = 700, 4, "1e-4", 1536


def baseline_overall() -> float:
    sys.path.insert(0, str(EVAL))
    from harness import score, majority_predictor, load
    test = load("test")
    return score(test, majority_predictor(load("train"), test))["_overall_structured"]


def train(label: str, model: str, num_layers: int) -> bool:
    LOGS.mkdir(parents=True, exist_ok=True)
    adapter = ADAPTERS / label
    cmd = [sys.executable, "-m", "mlx_lm", "lora", "--model", model, "--train",
           "--data", str(MLX_DATA), "--fine-tune-type", "lora",
           "--num-layers", str(num_layers), "--batch-size", str(BATCH), "--iters", str(ITERS),
           "--learning-rate", LR, "--max-seq-length", str(MAXSEQ),
           "--steps-per-report", "50", "--steps-per-eval", "200", "--val-batches", "20",
           "--adapter-path", str(adapter), "--grad-checkpoint", "--mask-prompt", "--seed", "0"]
    print(f"\n=== TRAIN {label} (num_layers={num_layers}) ===\n{' '.join(cmd)}", flush=True)
    t0 = time.time()
    with (LOGS / f"train_{label}.log").open("w") as log:
        r = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
    print(f"[{label}] training exit={r.returncode} in {(time.time()-t0)/60:.1f} min", flush=True)
    return r.returncode == 0


def infer(label: str, model: str) -> dict | None:
    cmd = [sys.executable, str(EVAL / "infer_and_score.py"),
           "--model", model, "--adapter", str(ADAPTERS / label), "--label", label]
    print(f"\n=== INFER+SCORE {label} ===", flush=True)
    r = subprocess.run(cmd)
    sf = EVAL / f"score_{label}.json"
    return json.loads(sf.read_text()) if (r.returncode == 0 and sf.exists()) else None


def main():
    base = baseline_overall()
    print(f"majority-class baseline overall = {base}", flush=True)
    results = {}
    for label, model in MODELS:
        ok = train(label, model, num_layers=16)
        if not ok:
            print(f"[{label}] 16-layer train failed; retrying with 8 layers", flush=True)
            ok = train(label, model, num_layers=8)
        if not ok:
            print(f"[{label}] training failed — skipping", flush=True)
            continue
        res = infer(label, model)
        if res:
            results[label] = res

    # --- comparison report ---
    lines = ["# Phase 3 results — TrialScout fine-tune A/B\n",
             f"Majority-class baseline (floor): **{base}**\n",
             "| model | overall structured | valid JSON | phase | modality | endpoint | sponsor | readout | risk set-F1 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for label, res in results.items():
        lines.append(
            f"| {label} | **{res['_overall_structured']}** | {res.get('_valid_json','-')} | "
            f"{res['phase']['accuracy']} | {res['modality']['accuracy']} | "
            f"{res['primary_endpoint_type']['accuracy']} | {res['sponsor_type']['accuracy']} | "
            f"{res['est_readout']['accuracy']} | {res['risk_flags']['set_f1']} |")
    if results:
        winner = max(results, key=lambda k: results[k]["_overall_structured"])
        lift = results[winner]["_overall_structured"] - base
        lines.append(f"\n**Winner: `{winner}`** — overall {results[winner]['_overall_structured']} "
                     f"(+{lift:.3f} over baseline).")
    else:
        lines.append("\n**No models completed.** See train/logs/.")
    (EVAL / "PHASE3_RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
