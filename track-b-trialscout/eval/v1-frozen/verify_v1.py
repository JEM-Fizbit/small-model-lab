"""Recompute every published v1 figure from the committed files, and fail if any drifts.

The v1 numbers are cited on the public walk-through and in external writing. The schema
they were measured under no longer exists in the live tree, so "trust the repo" is not
a check anyone can run. This is: it re-derives the whole per-field table from
`gold_test.jsonl` + `preds_qwen.jsonl` using the v1 harness, and asserts the result
against the published values.

It needs nothing outside this directory -- no model, no API key, no adapter. Regenerating
the *predictions* would need the local adapter (see MANIFEST.json); regenerating the
*scores from those predictions* needs only what is committed here.

Run:  uv run python track-b-trialscout/eval/v1-frozen/verify_v1.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "schema"))

from harness_v1 import score  # noqa: E402  the v1 scorer, frozen alongside the data
from normalize import snap_to_enum  # noqa: E402  the v1 normalizer

# The published v1 figures, as they appear in score_qwen.json, eval/PHASE3_RESULTS.md
# and on the walk-through's Part 2 results table.
PUBLISHED = {
    "_overall_structured": 0.922,
    "_valid_json": 1.0,
    "phase": 1.0,
    "modality": 0.773,
    "primary_endpoint_type": 0.9,
    "sponsor_type": 0.98,
    "est_readout": 0.993,
    "risk_flags": 0.884,
}
# The post-normalizer figures quoted in ADR-0011 / eval/PHASE4_RESULTS.md.
PUBLISHED_SNAPPED = {"_overall_structured": 0.925, "modality": 0.78}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def accuracy_of(res: dict, field: str) -> float:
    """The single headline number for a field, whichever metric it is scored by."""
    block = res[field]
    return block["set_f1"] if "set_f1" in block else block["accuracy"]


def main() -> int:
    gold = load_jsonl(HERE / "gold_test.jsonl")
    preds = {r["nct_id"]: r for r in load_jsonl(HERE / "preds_qwen.jsonl")}
    stored = json.loads((HERE / "score_qwen.json").read_text())

    raw = score(gold, preds)
    snapped = score(gold, {k: snap_to_enum(v) for k, v in preds.items()})

    failures: list[str] = []

    # 1. n and parse rate are what the published table claims.
    if raw["_n"] != 150:
        failures.append(f"test set is {raw['_n']} rows, published table says 150")
    if len(preds) != 150:
        failures.append(f"{len(preds)} predictions, published valid_json 1.000 implies 150")

    # 2. Every published per-field figure re-derives from the committed data.
    print(f"{'field':<24} {'published':>10} {'recomputed':>11}   status")
    print("-" * 60)
    for field, want in PUBLISHED.items():
        if field == "_valid_json":
            # not produced by the harness -- it is the parse rate, recomputed here
            got = round(len(preds) / len(gold), 3)
        elif field.startswith("_"):
            got = raw[field]
        else:
            got = accuracy_of(raw, field)
        ok = abs(got - want) < 5e-4
        if not ok:
            failures.append(f"{field}: published {want}, recomputed {got}")
        print(f"{field:<24} {want:>10.3f} {got:>11.3f}   {'ok' if ok else 'DRIFT'}")

    # 3. The stored score file agrees with a fresh recomputation.
    if abs(stored["_overall_structured"] - raw["_overall_structured"]) > 5e-4:
        failures.append("score_qwen.json disagrees with a fresh run over the same files")

    # 4. The post-normalizer figures quoted in ADR-0011 also re-derive.
    print()
    for field, want in PUBLISHED_SNAPPED.items():
        got = snapped[field] if field.startswith("_") else accuracy_of(snapped, field)
        ok = abs(got - want) < 5e-4
        if not ok:
            failures.append(f"snapped {field}: published {want}, recomputed {got}")
        print(f"{'snapped ' + field:<24} {want:>10.3f} {got:>11.3f}   {'ok' if ok else 'DRIFT'}")

    print()
    if failures:
        print("FAILED -- the frozen record no longer reproduces the published figures:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK -- every published v1 figure re-derives from the committed files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
