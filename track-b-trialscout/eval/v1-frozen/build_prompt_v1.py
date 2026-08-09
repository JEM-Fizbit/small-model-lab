"""The v1 student prompt, frozen verbatim.

Copied out of `train/format_for_mlx.py` as it stood at commit 07ade7f (2026-06-07),
the state that produced `preds_qwen.jsonl` and the published 0.922. The live file has
since moved to the v2 schema (list-valued `modalities`), so this copy exists to keep
the v1 measurement reconstructible without archaeology through git history.

Deliberately self-contained: no imports from the live tree, so a future refactor
there cannot silently change what this says the v1 prompt was.
"""
from __future__ import annotations
import json

TARGET_FIELDS = ["phase", "indication", "modality", "primary_endpoint_type",
                 "sponsor_type", "est_readout", "risk_flags", "investor_note"]

INSTRUCTION = (
    "You are TrialScout. Read the oncology clinical-trial record below and return ONLY a JSON "
    "object with exactly these fields: phase, indication, modality, primary_endpoint_type, "
    "sponsor_type, est_readout, risk_flags (array), investor_note. No prose, no code fence."
)


def trial_input(raw: dict) -> dict:
    """The compact record shown to the model (matches what the teacher saw, summary trimmed)."""
    r = dict(raw)
    if r.get("brief_summary"):
        r["brief_summary"] = r["brief_summary"][:600]
    r.pop("nct_id", None)  # nct_id is known at scoring time; don't make the model copy it
    return r


def build_prompt(raw: dict) -> str:
    return f"{INSTRUCTION}\n\nTRIAL:\n{json.dumps(trial_input(raw), ensure_ascii=False)}"
