"""A stable fingerprint of the output contract, so a model can't be served against the wrong schema.

The failure this exists to prevent (hit for real on 2026-08-10): the MCP server was loading a
schema-v1 adapter while `schema/` had moved to v2. The output still PASSED schema validation,
because `snap_to_enum` maps any unrecognised value to `other` — so a wrong readout was
indistinguishable from a right one. Validation proves an output is well-formed. It never proves
it is correct, and any normalizer with a fallback bucket will happily manufacture well-formedness
out of nonsense.

A fingerprint is bookkeeping, not inference: hash the field names and their vocabularies, write it
next to the adapter at training time, and refuse to serve a mismatch.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "trial_readout.schema.json"
STAMP_FILENAME = "schema_fingerprint.json"


def contract(schema: dict | None = None) -> dict:
    """The parts of the schema a trained model is actually coupled to.

    Field names and enum vocabularies only — descriptions and prose are excluded on purpose, so
    rewording a field's help text doesn't invalidate a perfectly good adapter.
    """
    s = schema or json.loads(SCHEMA_PATH.read_text())
    props = s["properties"]
    out = {}
    for name in sorted(props):
        p = props[name]
        if "enum" in p:
            out[name] = sorted(p["enum"])
        elif p.get("type") == "array" and "enum" in p.get("items", {}):
            out[name] = ["[]"] + sorted(p["items"]["enum"])
        else:
            out[name] = p.get("type", "string")
    return {"required": sorted(s.get("required", [])), "fields": out}


def fingerprint(schema: dict | None = None) -> str:
    payload = json.dumps(contract(schema), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def stamp(adapter_dir: Path) -> Path:
    """Record the current contract next to a freshly trained adapter."""
    adapter_dir = Path(adapter_dir)
    adapter_dir.mkdir(parents=True, exist_ok=True)
    path = adapter_dir / STAMP_FILENAME
    path.write_text(json.dumps({"fingerprint": fingerprint(), "contract": contract()}, indent=2))
    return path


def check(adapter_dir: Path) -> tuple[bool, str]:
    """(ok, message). Missing stamp is a warning; a mismatch is a refusal."""
    path = Path(adapter_dir) / STAMP_FILENAME
    current = fingerprint()
    if not path.exists():
        return True, (f"no {STAMP_FILENAME} in {Path(adapter_dir).name} — cannot verify this adapter "
                      f"was trained against the current schema ({current}). Run train/stamp_adapter.py.")
    stamped = json.loads(path.read_text()).get("fingerprint")
    if stamped != current:
        return False, (f"SCHEMA MISMATCH: adapter {Path(adapter_dir).name} was trained against "
                       f"contract {stamped}, the current schema is {current}. Serving this pair "
                       f"produces output that still validates but is wrong. Retrain or repoint.")
    return True, f"schema contract {current} matches"


if __name__ == "__main__":
    print(fingerprint())
    print(json.dumps(contract(), indent=2))
