"""Evaluate TrialScout predictions against the gold test set.

Two layers:
  1. Structured fields (deterministic, free): per-field accuracy + macro-F1 for
     the categoricals, set-F1 for risk_flags, exact-match for est_readout.
  2. investor_note quality: Claude-as-judge (scaffolded here; used in Phase 3 on
     a real student model — not run on the trivial baseline).

Until the fine-tuned student exists (Phase 3), this also computes a MAJORITY-CLASS
baseline (predict the most common value of each field) so we know the floor the
student must beat.

Run:  uv run python track-b-trialscout/eval/harness.py --baseline majority
      uv run python track-b-trialscout/eval/harness.py --pred path/to/preds.jsonl
"""
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "gold"
CATEGORICAL = ["phase", "modality", "primary_endpoint_type", "sponsor_type"]


def load(name): return [json.loads(l) for l in (GOLD / f"{name}.jsonl").read_text().splitlines() if l.strip()]


def macro_f1(gold_vals, pred_vals):
    """Manual macro-F1 over the label set (no sklearn)."""
    labels = set(gold_vals) | set(pred_vals)
    f1s = []
    for lab in labels:
        tp = sum(1 for g, p in zip(gold_vals, pred_vals) if g == lab and p == lab)
        fp = sum(1 for g, p in zip(gold_vals, pred_vals) if g != lab and p == lab)
        fn = sum(1 for g, p in zip(gold_vals, pred_vals) if g == lab and p != lab)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return sum(f1s) / len(f1s) if f1s else 0.0


def set_f1(gold_sets, pred_sets):
    """Mean per-example F1 over risk_flags (a set-valued field)."""
    scores = []
    for g, p in zip(gold_sets, pred_sets):
        g, p = set(g), set(p)
        if not g and not p:
            scores.append(1.0); continue
        tp = len(g & p)
        prec = tp / len(p) if p else 0.0
        rec = tp / len(g) if g else 0.0
        scores.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def score(gold, pred_by_id):
    """gold: list of rows; pred_by_id: {nct_id: readout dict}."""
    g = [r for r in gold if r["nct_id"] in pred_by_id]
    p = [pred_by_id[r["nct_id"]] for r in g]
    out = {}
    for field in CATEGORICAL:
        gv = [r.get(field) for r in g]; pv = [x.get(field) for x in p]
        acc = sum(1 for a, b in zip(gv, pv) if a == b) / len(gv)
        out[field] = {"accuracy": round(acc, 3), "macro_f1": round(macro_f1(gv, pv), 3)}
    # est_readout exact match
    out["est_readout"] = {"accuracy": round(
        sum(1 for r, x in zip(g, p) if r.get("est_readout") == x.get("est_readout")) / len(g), 3)}
    # risk_flags set-F1
    out["risk_flags"] = {"set_f1": round(
        set_f1([r.get("risk_flags", []) for r in g], [x.get("risk_flags", []) for x in p]), 3)}
    # headline: mean of the categorical accuracies + readout acc + risk set-F1
    parts = [out[f]["accuracy"] for f in CATEGORICAL] + [out["est_readout"]["accuracy"], out["risk_flags"]["set_f1"]]
    out["_overall_structured"] = round(sum(parts) / len(parts), 3)
    out["_n"] = len(g)
    return out


def majority_predictor(train, test):
    """Predict the most common value of each field (the floor a real model must beat)."""
    modes = {f: Counter(r.get(f) for r in train).most_common(1)[0][0] for f in CATEGORICAL}
    modes["est_readout"] = Counter(r.get("est_readout") for r in train).most_common(1)[0][0]
    # most common single risk flag, as a 1-element guess
    flat = Counter(fl for r in train for fl in r.get("risk_flags", []))
    common_flag = [flat.most_common(1)[0][0]] if flat else []
    return {r["nct_id"]: {**modes, "risk_flags": common_flag} for r in test}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", choices=["majority"], default=None)
    ap.add_argument("--pred", type=str, default=None, help="JSONL of predictions (nct_id + readout fields)")
    args = ap.parse_args()
    test = load("test")
    if args.baseline == "majority":
        preds = majority_predictor(load("train"), test)
        label = "MAJORITY-CLASS BASELINE"
    elif args.pred:
        rows = [json.loads(l) for l in Path(args.pred).read_text().splitlines() if l.strip()]
        preds = {r["nct_id"]: r for r in rows}
        label = f"predictions: {args.pred}"
    else:
        print("Pass --baseline majority or --pred <file>."); return
    res = score(test, preds)
    print(f"=== {label} ===")
    print(json.dumps(res, indent=2))
    if args.baseline:
        (ROOT / "eval" / "BASELINE.md").write_text(
            f"# Structured-field baseline (majority-class) on the gold test set\n\n"
            f"Overall structured score: **{res['_overall_structured']}** (n={res['_n']})\n\n"
            f"```json\n{json.dumps(res, indent=2)}\n```\n\n"
            f"The Phase 3 fine-tuned student must beat this floor.\n")
        print("\nWrote eval/BASELINE.md")


if __name__ == "__main__":
    main()
