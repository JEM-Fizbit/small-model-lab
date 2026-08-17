"""Evaluate TrialScout predictions against the gold test set.

Two layers:
  1. Structured fields (deterministic, free): per-field accuracy + macro-F1 for
     the categoricals, set-F1 for the set-valued fields (`modalities`, `risk_flags`),
     exact-match for est_readout.
  2. investor_note quality: Claude-as-judge (scaffolded here; used in Phase 3 on
     a real student model — not run on the trivial baseline).

Also computes a MAJORITY-CLASS baseline (predict the most common value of each field)
so we know the floor any real model must beat.

`modalities` is set-valued (schema v2, ADR-0017), so it is scored the way `risk_flags`
already was — mean per-example F1 over the two sets. Read `_scoring_note` in the output
before comparing a v2 score to a v1 one: set-F1 gives partial credit where the v1
`modality` accuracy gave none, so the two are different measurements on a shared scale.

Run:  uv run python track-b-trialscout/eval/harness.py --baseline majority
      uv run python track-b-trialscout/eval/harness.py --pred path/to/preds.jsonl
"""
from __future__ import annotations
import argparse, json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "gold"

CATEGORICAL = ["phase", "intervention_class", "primary_endpoint_type", "sponsor_type"]
SET_VALUED = ["modalities", "risk_flags_judgement"]  # risk_flags is derived, not scored

# Distinguishes "the model answered []" from "the model omitted the field". Both look like
# an empty list to .get(field, []), but [] is a claim (no drug asset) and a missing key is
# a failure to answer — scoring them the same would hand free marks to a broken output.
MISSING = object()


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


def multilabel_macro_f1(gold_sets, pred_sets):
    """Macro-F1 over a set-valued field: each label scored as a binary presence task.

    This is the metric that exposes the rare-class tail (is ADC ever recalled?), which
    mean per-example set-F1 hides — a label appearing in 5 of 150 rows barely moves it.
    """
    labels = {x for s in gold_sets for x in s} | {x for s in pred_sets for x in s}
    f1s = []
    for lab in sorted(labels):
        tp = sum(1 for g, p in zip(gold_sets, pred_sets) if lab in g and lab in p)
        fp = sum(1 for g, p in zip(gold_sets, pred_sets) if lab not in g and lab in p)
        fn = sum(1 for g, p in zip(gold_sets, pred_sets) if lab in g and lab not in p)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return sum(f1s) / len(f1s) if f1s else 0.0


#: Below this many gold occurrences, a per-class recall moves by more than 0.05 when a SINGLE
#: trial changes, so it cannot support a claim about that class. Chosen as the n at which one
#: example is worth <5 recall points.
MIN_N_FOR_CLASS_CLAIM = 20


def per_label_recall(gold_sets, pred_sets):
    """{label: {n, recall}} over gold occurrences — the rare-class table.

    Each row carries what one trial is worth, because that is the number that was misread
    three separate times in this project (ADR-0019, ADR-0020, ADR-0025). At n=4 a single
    example moves recall by 0.25, and a row like `radiopharmaceutical 1.000 -> 0.500` is two
    trials, not a finding. The figure now travels with the number instead of living in an ADR
    nobody re-reads at the moment of writing the conclusion.
    """
    out = {}
    for lab in sorted({x for s in gold_sets for x in s}):
        n = sum(1 for g in gold_sets if lab in g)
        hit = sum(1 for g, p in zip(gold_sets, pred_sets) if lab in g and lab in p)
        row = {"n": n, "recall": round(hit / n, 3) if n else 0.0}
        if n:
            row["one_trial_worth"] = round(1 / n, 3)
            if n < MIN_N_FOR_CLASS_CLAIM:
                row["_UNDERPOWERED"] = (
                    f"n={n}: one trial moves this by {1/n:.2f}. Not usable as evidence "
                    f"about this class — report it, do not conclude from it.")
        out[lab] = row
    return out


def _ci95(values):
    """Half-width of the 95% CI for the mean of `values`. Approximate and deliberately crude.

    The point is not precision, it is that a score should state what it can resolve. A field
    scored on 150 trials resolves about ±0.05; on 1,444 about ±0.015. That difference is
    exactly why a 0.046 gap read as real at n=150 and turned out to be 0.025 at n=1,439,
    while a +0.040 "improvement" at n=150 turned out to be -0.008.
    """
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return 1.96 * (var / n) ** 0.5


def set_f1(gold_sets, pred_sets):
    """Mean per-example F1 over a set-valued field."""
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


def set_error_shape(gold_sets, pred_sets):
    """How set predictions fail — the 'did we fix the ambiguity or move it?' diagnostic.

    v1's `combination` boundary was an argument about HOW MANY modalities a trial has.
    If the list-valued field merely relocated that argument, it shows up here as
    `subset` + `superset` — the right modalities, the wrong count. If it resolved it,
    those buckets stay small and what's left is `disjoint`: a genuinely wrong class,
    which is the rare-tail problem more data can fix.
    """
    shape = Counter()
    for g, p in zip(gold_sets, pred_sets):
        g, p = set(g), set(p)
        if g == p:
            shape["exact"] += 1
        elif not (g & p):
            shape["disjoint"] += 1
        elif g < p:
            shape["superset (predicted extra)"] += 1
        elif p < g:
            shape["subset (predicted fewer)"] += 1
        else:
            shape["partial overlap"] += 1
    n = sum(shape.values())
    cardinality_only = shape["superset (predicted extra)"] + shape["subset (predicted fewer)"]
    return {
        "counts": dict(shape),
        "exact_set_accuracy": round(shape["exact"] / n, 3) if n else 0.0,
        "cardinality_only_errors": cardinality_only,
        "cardinality_only_share_of_errors": round(cardinality_only / (n - shape["exact"]), 3)
                                            if n - shape["exact"] else 0.0,
    }


def _sets_for(field, rows):
    """Pull a set-valued field, keeping missing keys distinguishable from []."""
    return [r.get(field, MISSING) for r in rows]


def _scalar(v):
    """Coerce a predicted scalar to something hashable and comparable.

    An untuned model happily emits `"phase": ["PHASE1","PHASE2"]` where the schema wants one
    string. That is a WRONG ANSWER, not a crash and not an omission, so it is stringified and
    scored as wrong — same convention as salience_omission_eval._scalar. Gold is always
    well-formed, so this only ever touches predictions.
    """
    if v is None or isinstance(v, str):
        return v
    if isinstance(v, list):
        return " ".join(map(str, v))
    return str(v)


#: v4 scores only what the model is actually asked for. phase, sponsor_type and est_readout
#: moved to the derived tier (ADR-0024), so scoring them would credit the student for a
#: lookup it no longer performs -- and would make v3 and v4 headlines look comparable when
#: they measure different jobs.
CATEGORICAL_V4 = ["intervention_class", "primary_endpoint_type"]
SET_VALUED_V4 = ["modalities", "risk_flags_judgement"]


def score(gold, pred_by_id, categorical=None, set_valued=None, include_est_readout=True):
    """gold: list of rows; pred_by_id: {nct_id: readout dict}.

    Field lists are parameters so a schema version cannot silently change what the headline
    averages over. Pass CATEGORICAL_V4 / SET_VALUED_V4 / include_est_readout=False for v4.
    """
    CATEGORICAL = categorical if categorical is not None else globals()["CATEGORICAL"]
    SET_VALUED = set_valued if set_valued is not None else globals()["SET_VALUED"]
    g = [r for r in gold if r["nct_id"] in pred_by_id]
    p = [pred_by_id[r["nct_id"]] for r in g]
    out = {}
    for field in CATEGORICAL:
        gv = [r.get(field) for r in g]; pv = [_scalar(x.get(field)) for x in p]
        hits = [1.0 if a == b else 0.0 for a, b in zip(gv, pv)]
        acc = sum(hits) / len(gv)
        block = {"accuracy": round(acc, 3), "macro_f1": round(macro_f1(gv, pv), 3)}
        ci = _ci95(hits)
        if ci is not None:
            block["_resolves_to"] = round(ci, 3)
        out[field] = block
    # est_readout exact match (v3 only -- v4 computes it from the record)
    if include_est_readout:
        out["est_readout"] = {"accuracy": round(
            sum(1 for r, x in zip(g, p) if r.get("est_readout") == x.get("est_readout")) / len(g), 3)}
    # set-valued fields
    for field in SET_VALUED:
        gs_raw, ps_raw = _sets_for(field, g), _sets_for(field, p)
        n_missing = sum(1 for x in ps_raw if x is MISSING)
        # A missing field scores as an empty prediction, which is a miss against any
        # non-empty gold -- but never as a free 1.0 against an empty gold.
        gs = [[] if x is MISSING else list(x) for x in gs_raw]
        ps = [None if x is MISSING else list(x) for x in ps_raw]
        scored_ps = [[] if x is None else x for x in ps]
        per = [0.0 if pp is None else set_f1([gg], [pp]) for gg, pp in zip(gs, ps)]
        block: dict = {"set_f1": round(sum(per) / len(per), 3) if per else 0.0}
        ci = _ci95(per)
        if ci is not None:
            block["_resolves_to"] = round(ci, 3)
        if n_missing:
            block["_omitted"] = n_missing
        if field == "risk_flags_judgement":
            # Split what the model is genuinely responsible for from what is arithmetic.
            # See schema/derive.py: seven of these eleven are pure functions of the record.
            try:
                sys.path.insert(0, str(ROOT / "schema"))
                from derive import DETERMINISTIC_FLAGS, JUDGEMENT_FLAGS
                def sub(sets, keep):
                    return [[x for x in s_ if x in keep] for s_ in sets]
                block["judgement_subset_f1"] = round(
                    set_f1(sub(gs, JUDGEMENT_FLAGS), sub(scored_ps, JUDGEMENT_FLAGS)), 3)
                block["deterministic_subset_f1"] = round(
                    set_f1(sub(gs, DETERMINISTIC_FLAGS), sub(scored_ps, DETERMINISTIC_FLAGS)), 3)
                block["_note"] = ("judgement_subset_f1 is the honest number for what the model is "
                                  "asked to reason about; the deterministic subset should be computed "
                                  "from the record (schema/derive.py), not generated.")
            except Exception:
                pass
        if field == "modalities":
            block["macro_f1"] = round(multilabel_macro_f1(gs, scored_ps), 3)
            block["_error_shape"] = set_error_shape(gs, scored_ps)
            block["exact_set_accuracy"] = block["_error_shape"]["exact_set_accuracy"]
            block["_per_label"] = per_label_recall(gs, scored_ps)
        out[field] = block
    # headline: mean of the categorical accuracies + readout acc + the two set-F1s
    parts = ([out[f]["accuracy"] for f in CATEGORICAL]
             + ([out["est_readout"]["accuracy"]] if include_est_readout else [])
             + [out[f]["set_f1"] for f in SET_VALUED])
    out["_overall_structured"] = round(sum(parts) / len(parts), 3)
    out["_n"] = len(g)
    out["_components"] = len(parts)
    # The headline aggregates many fields and is steadier than any of them; the per-field
    # resolution is what a reader needs before comparing two runs field by field. Reported as
    # the widest across fields, so it is the honest bound rather than the flattering one.
    field_cis = [b["_resolves_to"] for b in out.values()
                 if isinstance(b, dict) and "_resolves_to" in b]
    if field_cis:
        worst = max(field_cis)
        out["_field_resolution"] = round(worst, 3)
        out["_reading_rule"] = (
            f"n={len(g)}. Per-field differences smaller than ~{worst:.3f} are not "
            f"distinguishable from noise here; do not report one as an improvement or a "
            f"regression. This project has drawn a per-field conclusion from a small set and "
            f"had a larger set overturn it three times (ADR-0019, ADR-0020, ADR-0025) -- "
            f"including a '+0.040 improvement' at n=150 that measured -0.008 at n=1,439.")
    out["_scoring_note"] = (
        f"{len(parts)} components ({len(CATEGORICAL)} categorical accuracies"
        + (", est_readout exact match" if include_est_readout else "")
        + f", {len(SET_VALUED)} set-F1s). Overalls are comparable ONLY across identical "
        "component sets: v3 averaged 7 and v4 averages 4, because phase, sponsor_type and "
        "est_readout moved to the derived tier. The v4 number is lower by construction -- "
        "the three that left all scored 0.976-0.997, i.e. above the v3 mean. The like-for-like "
        "v3 figure on the v4 components is 0.893, not 0.932.")
    return out


def majority_predictor(train, test):
    """Predict the most common value of each field (the floor a real model must beat)."""
    modes = {f: Counter(r.get(f) for r in train).most_common(1)[0][0] for f in CATEGORICAL}
    modes["est_readout"] = Counter(r.get("est_readout") for r in train).most_common(1)[0][0]
    # For a set-valued field the analogue of "the most common value" is the most common
    # exact SET, not the most common member -- guessing one popular member every time is a
    # different (and easier) strategy than the categoricals get.
    for field in SET_VALUED:
        common = Counter(tuple(sorted(r.get(field, []))) for r in train).most_common(1)
        modes[field] = list(common[0][0]) if common else []
    return {r["nct_id"]: dict(modes) for r in test}


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
        (ROOT / "eval" / "score_majority.json").write_text(json.dumps(res, indent=2))
        (ROOT / "eval" / "BASELINE.md").write_text(
            f"# Structured-field baseline (majority-class) on the gold test set\n\n"
            f"Overall structured score: **{res['_overall_structured']}** (n={res['_n']})\n\n"
            f"Schema v2 (ADR-0017): 7 scored components. The v1 floor was **0.368** over 6\n"
            f"components with a single-valued `modality` — a different measurement, not a\n"
            f"regression or an improvement.\n\n"
            f"```json\n{json.dumps(res, indent=2)}\n```\n\n"
            f"The fine-tuned student must beat this floor.\n")
        print("\nWrote eval/BASELINE.md")


if __name__ == "__main__":
    main()
