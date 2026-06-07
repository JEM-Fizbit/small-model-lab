"""snap_to_enum — deterministically normalize a readout's enum fields to the schema vocabulary.

The fine-tuned student occasionally emits a near-miss enum value: wrong casing
('pathologic complete response (PCR)' for '(pCR)') or an out-of-vocab synonym
('radioimmunotherapy'). This snaps each value to the canonical enum by:
  1. exact match            -> keep
  2. case-insensitive match -> canonical casing  (fixes 'PCR' -> 'pCR')
  3. else                   -> the enum's 'other' bucket if it has one (fixes out-of-vocab)
For risk_flags (no 'other' bucket), unrecognized items are dropped rather than coerced.

It only ever touches values that were NOT already valid, so it can never turn a correct
value wrong. It's part of the *deployed* inference path (the MCP server applies it before
schema validation), so eval applies it too — the gate measures the system as shipped.
"""
from __future__ import annotations
import json
from pathlib import Path

_SCHEMA = json.loads((Path(__file__).resolve().parent / "trial_readout.schema.json").read_text())
_PROPS = _SCHEMA["properties"]
_SCALAR_ENUM_FIELDS = ("phase", "modality", "primary_endpoint_type", "sponsor_type")


def _enum(field: str) -> list[str] | None:
    p = _PROPS.get(field, {})
    if "enum" in p:
        return p["enum"]
    if p.get("type") == "array":
        return p.get("items", {}).get("enum")
    return None


def _snap_scalar(field: str, value):
    enum = _enum(field)
    if enum is None or not isinstance(value, str):
        return value
    if value in enum:
        return value
    low = value.strip().lower()
    by_low = {e.lower(): e for e in enum}
    if low in by_low:
        return by_low[low]
    return "other" if "other" in enum else value


def snap_to_enum(readout: dict) -> dict:
    """Return a copy of `readout` with enum fields snapped to the schema vocabulary."""
    out = dict(readout)
    for field in _SCALAR_ENUM_FIELDS:
        if field in out:
            out[field] = _snap_scalar(field, out[field])
    flags = out.get("risk_flags")
    if isinstance(flags, list):
        enum = _enum("risk_flags") or []
        by_low = {e.lower(): e for e in enum}
        snapped, seen = [], set()
        for x in flags:
            if not isinstance(x, str):
                continue
            canon = x if x in enum else by_low.get(x.strip().lower())
            if canon and canon not in seen:  # drop unrecognized + dedupe
                snapped.append(canon)
                seen.add(canon)
        out["risk_flags"] = snapped
    return out
