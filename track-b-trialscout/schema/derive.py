"""Risk flags that are arithmetic, not judgement — computed from the record, never asked of a model.

Seven of the eleven `risk_flags` are pure functions of fields already in the trial record.
`small enrollment (<50)` is literally `record["enrollment"] < 50`. Asking a language model to
evaluate that is asking it to do boolean arithmetic on a number it can already see, and it is
measurably worse at it than an `if` statement:

    on the 150-trial test set, for `small enrollment (<50)`
      teacher gold disagrees with the record  20 times
      the student disagrees with the record   31 times

The student is worse because it faithfully learned the teacher's mistakes — distillation working
exactly as advertised, on an answer that should never have been generated in the first place.

So the deployed pipeline computes these seven and lets the model keep the four that need reading
comprehension. Note the consequence for scoring: computed flags score *lower* against the existing
gold (set-F1 0.825 vs the student's 0.907), because gold is wrong on them and the student
reproduces the same wrongness. Lower against a flawed answer key is the correct direction.

The model is still trained to emit all eleven — retiring the seven from its target needs a gold
regeneration, which belongs to a future schema version. Until then this module is applied at
serving and reported as a diagnostic at eval.
"""
from __future__ import annotations

# Pure functions of the record. The model should not be asked for these.
DETERMINISTIC_FLAGS = (
    "small enrollment (<50)",
    "status: terminated/withdrawn/suspended",
    "early-phase",
    "non-randomized",
    "open-label",
    "single-arm",
    "long timeline (>4y)",
)

# These need the model: they depend on reading the outcome measures and the indication.
JUDGEMENT_FLAGS = (
    "surrogate endpoint",
    "biomarker-restricted",
    "PK/dose-finding only",
    "no comparator",
)


def derive_risk_flags(record: dict) -> list[str]:
    """The deterministic subset, computed from a compact CT.gov record.

    Mirrors the mapping make_gold.py states in prose, but executes it instead of asking for it.
    Fields that are absent simply do not fire — never guessed.
    """
    flags: list[str] = []

    enrollment = record.get("enrollment")
    if isinstance(enrollment, (int, float)) and enrollment < 50:
        flags.append("small enrollment (<50)")

    status = str(record.get("overall_status") or "").upper()
    if any(k in status for k in ("TERMINATED", "WITHDRAWN", "SUSPENDED")):
        flags.append("status: terminated/withdrawn/suspended")

    phases = " ".join(record.get("phases") or []).upper()
    if "PHASE1" in phases or "EARLY" in phases:
        flags.append("early-phase")

    if str(record.get("allocation") or "").upper().startswith("NON"):
        flags.append("non-randomized")

    if str(record.get("masking") or "").upper() == "NONE":
        flags.append("open-label")

    n_arms = record.get("n_arms")
    if isinstance(n_arms, int) and n_arms == 1:
        flags.append("single-arm")

    start, done = str(record.get("start_date") or ""), str(record.get("primary_completion_date") or "")
    if len(start) >= 4 and len(done) >= 4 and start[:4].isdigit() and done[:4].isdigit():
        if int(done[:4]) - int(start[:4]) > 4:
            flags.append("long timeline (>4y)")

    return sorted(flags)


def merge_risk_flags(record: dict, model_flags: list[str] | None) -> list[str]:
    """The served answer: computed flags for the seven, the model's `risk_flags_judgement` for
    the four.

    Anything the model emits from the deterministic set is discarded — not merged — because the
    record is the authority for those and a second opinion adds only noise. As of schema v3 the
    model is not even offered those seven (they are `x-derived`), so this filter is now a
    belt-and-braces guard rather than the main mechanism.
    """
    judged = {f for f in (model_flags or []) if f in JUDGEMENT_FLAGS}
    return sorted(set(derive_risk_flags(record)) | judged)
