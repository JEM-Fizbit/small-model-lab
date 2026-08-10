"""snap_to_enum — deterministically normalize a readout's enum fields to the schema vocabulary.

The fine-tuned student occasionally emits a near-miss enum value: wrong casing
('pathologic complete response (PCR)' for '(pCR)') or an out-of-vocab synonym
('radioimmunotherapy'). This snaps each value to the canonical enum by:
  1. exact match            -> keep
  2. case-insensitive match -> canonical casing  (fixes 'PCR' -> 'pCR')
  3. else                   -> the enum's 'other' bucket if it has one (fixes out-of-vocab)

Set-valued fields (`modalities`, `risk_flags`) get the same treatment per item, then are
deduped and sorted so two readouts naming the same set compare equal. They differ in the
fallback, and deliberately so: `modalities` HAS an 'other' bucket, so an unrecognized item
becomes 'other' — dropping it could empty the list, and an empty `modalities` means
"this trial has no drug asset", which is a much worse thing to say by accident.
`risk_flags` has no 'other', so unrecognized items are dropped.

Which fields are scalar and which are set-valued is read from the schema, not listed here —
`modality` (scalar) became `modalities` (a list) in the v2 schema, and a hardcoded list is
exactly what quietly mishandles that kind of change.

It only ever touches values that were NOT already valid, so it can never turn a correct
value wrong. Note what it deliberately does NOT do: it never enforces the cross-field rule
that `modalities` is empty iff `intervention_class` is not 'drug/biologic'. Doing so would
mean overwriting values that are individually valid, on the assumption that the other field
is the right one — which can turn a correct answer wrong. The teacher enforces that
invariant at label time (make_gold.valid); inference reports what the model actually said.

It's part of the *deployed* inference path (the MCP server applies it before schema
validation), so eval applies it too — the gate measures the system as shipped.
"""
from __future__ import annotations
import json
from pathlib import Path

_SCHEMA = json.loads((Path(__file__).resolve().parent / "trial_readout.schema.json").read_text())
_PROPS = _SCHEMA["properties"]

SCALAR_ENUM_FIELDS = tuple(k for k, v in _PROPS.items() if "enum" in v)
ARRAY_ENUM_FIELDS = tuple(k for k, v in _PROPS.items()
                          if v.get("type") == "array" and "enum" in v.get("items", {}))


def _enum(field: str) -> list[str] | None:
    p = _PROPS.get(field, {})
    if "enum" in p:
        return p["enum"]
    if p.get("type") == "array":
        return p.get("items", {}).get("enum")
    return None


def _snap_one(enum: list[str], value):
    """Snap a single string to the enum: exact, then case-insensitive, then 'other'."""
    if not isinstance(value, str):
        return None
    if value in enum:
        return value
    canon = {e.lower(): e for e in enum}.get(value.strip().lower())
    if canon:
        return canon
    return "other" if "other" in enum else None


def _snap_scalar(field: str, value):
    enum = _enum(field)
    if enum is None or not isinstance(value, str):
        return value
    return _snap_one(enum, value) or value


def snap_to_enum(readout: dict) -> dict:
    """Return a copy of `readout` with enum fields snapped to the schema vocabulary."""
    out = dict(readout)
    for field in SCALAR_ENUM_FIELDS:
        if field in out:
            out[field] = _snap_scalar(field, out[field])
    for field in ARRAY_ENUM_FIELDS:
        items = out.get(field)
        if not isinstance(items, list):
            continue
        enum = _enum(field) or []
        snapped = {c for c in (_snap_one(enum, x) for x in items) if c is not None}
        out[field] = sorted(snapped)  # dedupe + canonical order: these are sets, not lists
    return out
