"""Assemble the schema-v2 scorecard from the individual arm scores, and say what is comparable.

Every arm writes its own `score_<label>.json`. This collects them into one table, adds the
`modalities` error-shape diagnostic, and — the part that matters — annotates which columns
are like-for-like and which are not, so the table cannot be read as more comparable than it is.

Arms, in the order they belong on the page:
  majority          floor. Predict the most common value of each field.
  base_strict       untuned Qwen on the training prompt, scored EXACTLY as the student is.
                    That prompt never lists the enum vocabularies -- the student learns them
                    from 1,192 examples -- so this arm answers "other" to nearly everything.
  base_vocab        the same, with the allowed values appended to the prompt and nothing
                    else. base_strict -> base_vocab is the cost of not knowing the menu;
                    base_vocab -> student is what fine-tuning adds beyond it.
  frontier_zeroshot the teacher's model with the schema but none of the teacher scaffold.
  qwen_v2s          the fine-tuned student.

Run:  uv run python track-b-trialscout/eval/report_v2.py
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "eval"

ARMS = [
    ("majority",          "Baseline (floor)",     "score_majority.json"),
    ("base_strict",       "Untuned, no vocab",    "score_base_strict.json"),
    ("base_vocab",        "Untuned + enum list",  "score_base_vocab.json"),
    ("frontier_zeroshot", "Frontier zero-shot",   "score_frontier_zeroshot.json"),
    ("qwen_v2s",          "Student (no aug)",     "score_qwen_v2s.json"),
    ("qwen_v2s_aug",      "Student (PRODUCTION)", "score_qwen_v2s_aug.json"),
]

ROWS = [
    ("overall structured", lambda r: r["_overall_structured"]),
    ("valid output",       lambda r: r.get("_valid_json", r.get("_valid_output"))),
    ("phase",              lambda r: r["phase"]["accuracy"]),
    ("intervention_class", lambda r: r["intervention_class"]["accuracy"]),
    ("modalities (set-F1)", lambda r: r["modalities"]["set_f1"]),
    ("modalities (exact set)", lambda r: r["modalities"].get("exact_set_accuracy")),
    ("modalities (macro-F1)", lambda r: r["modalities"].get("macro_f1")),
    ("primary_endpoint_type", lambda r: r["primary_endpoint_type"]["accuracy"]),
    ("sponsor_type",       lambda r: r["sponsor_type"]["accuracy"]),
    ("est_readout",        lambda r: r["est_readout"]["accuracy"]),
    ("risk_flags (set-F1)", lambda r: r["risk_flags"]["set_f1"]),
]


def fmt(v):
    if v is None:
        return "—"
    return f"{v:.3f}" if isinstance(v, float) else str(v)


def main():
    scores = {}
    for key, _, fname in ARMS:
        p = EVAL / fname
        if p.exists():
            scores[key] = json.loads(p.read_text())
        else:
            print(f"  (missing: {fname})")
    present = [(k, label) for k, label, _ in ARMS if k in scores]
    if not present:
        print("No arm scores found — run the evals first.")
        return

    lines = ["| field | " + " | ".join(lbl for _, lbl in present) + " |",
             "|---" * (len(present) + 1) + "|"]
    for name, get in ROWS:
        cells = []
        for k, _ in present:
            try:
                cells.append(fmt(get(scores[k])))
            except (KeyError, TypeError):
                cells.append("—")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    table = "\n".join(lines)

    # the diagnostic that answers "did the ambiguity move?"
    diag = ""
    stu = scores.get("qwen_v2s_aug", scores.get("qwen_v2s", {})).get("modalities", {}).get("_error_shape")
    if diag is not None and stu:
        counts = stu["counts"]
        total_err = sum(v for k, v in counts.items() if k != "exact")
        diag = ("\n\n### Where `modalities` goes wrong (fine-tuned student)\n\n"
                "| error shape | count | share of errors |\n|---|---|---|\n"
                + "\n".join(f"| {k} | {v} | {v/total_err:.0%} |"
                            for k, v in sorted(counts.items(), key=lambda x: -x[1]) if k != "exact")
                + f"\n\nExact-set accuracy: **{stu['exact_set_accuracy']:.3f}**. "
                  f"Cardinality-only errors (right modalities, wrong count): "
                  f"**{stu['cardinality_only_errors']}** "
                  f"({stu['cardinality_only_share_of_errors']:.0%} of all errors).\n\n"
                  f"This is the number that decides whether the list-valued field *resolved* v1's "
                  f"`combination` argument or merely *relocated* it. v1's benchmark: 20 of 34 "
                  f"modality errors involved `combination` on one side or the other.")

    per_label = scores.get("qwen_v2s_aug", scores.get("qwen_v2s", {})).get("modalities", {}).get("_per_label")
    front_label = scores.get("frontier_zeroshot", {}).get("modalities", {}).get("_per_label", {})
    tail = ""
    if per_label:
        rows_t = []
        for k, v in sorted(per_label.items(), key=lambda x: -x[1]["n"]):
            fr = front_label.get(k, {}).get("recall")
            gap = "yes" if fr is not None and fr - v["recall"] > 0.2 else ""
            rows_t.append(f"| {k} | {v['n']} | {v['recall']:.2f} | "
                          f"{('%.2f' % fr) if fr is not None else '—'} | {gap} |")
        tail = ("\n\n### Per-modality recall — where the student's win runs out\n\n"
                "| modality | n in gold | student | frontier zero-shot | frontier much better |\n"
                "|---|---|---|---|---|\n" + "\n".join(rows_t) +
                "\n\n> **Read the n column before this table.** Several of these classes have 1-5 gold "
                "examples, where one trial swings recall by 20-100 points. Measured on the "
                "properly-powered diagnostic set (ADR-0020, n=34-100 per class) the same model "
                "scores ADC **0.77** and oncolytic virus **0.88**, not the 0.40 and 0.33 shown "
                "here. These frozen-set rare-class figures are sampling noise and must not be "
                "quoted as capability. See `PHASE6_DIAGNOSTIC.md`.")

    out = f"""# Schema-v2 scorecard — TrialScout

All arms scored on the **same frozen 150-trial test set**, with the **same scorer**
(`eval/harness.py`) and the **same normalizer** (`schema/normalize.py`), under schema v2.

{table}
{diag}{tail}

## What is comparable to what

**Like-for-like.** Every column above shares a test set, a scorer and a schema. The
headline comparison the project cares about — **untuned Qwen (strict) vs fine-tuned
student** — is exactly apples-to-apples: the same open model, the same prompt, the same
parsing of its own JSON output. That delta is the value fine-tuning added.

**Not like-for-like.** "Untuned Qwen (judged)" gives the base model a Claude judge that
reads its prose and maps it to the fields. It is a *more generous* reading of the same
model, included because the earlier write-up used it; it is not the same measurement as
the strict column, and the student is not given that help.

**Not comparable to v1 at all.** The schema-v1 headline (0.922) came from six components
scoring `modality` by hard accuracy. This is seven components scoring `modalities` by
set-F1, which awards partial credit where v1 awarded none. The two numbers share a scale
and measure different things. The v1 figures remain reproducible in `eval/v1-frozen/`.

**Why PRODUCTION looks worse on some modality rows.** `qwen_v2s_aug` scores lower here on
modalities macro-F1 (0.569 vs 0.653) yet is the promoted adapter. Frozen-set macro-F1 weights
every label equally across classes with n=1-5, so it is mostly sampling noise. On the
properly-powered diagnostic set the ordering reverses (0.689 vs 0.663) and the augmented adapter
wins every adequately-sampled rare class. See `PHASE6_DIAGNOSTIC.md` and ADR-0020. The two
columns are tied on the headline (0.939), which is the number this page is for.

**The frontier column is a scaffold ablation, not an independent referee.** Gold was
produced by the same model *with* decision rules and worked examples; this arm has the
schema and nothing else. It bounds what the prompt engineering was worth. It cannot tell
you whether the labels are right.
"""
    (EVAL / "PHASE6_RESULTS.md").write_text(out)
    print(out)


if __name__ == "__main__":
    main()
