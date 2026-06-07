"""Fetch trials enriched for the RARE modalities, for Phase-4 train augmentation.

Error-mining (Phase 4) showed `modality` macro-F1 is dragged down by the long tail:
the student rarely sees ADCs, bispecifics, cell/gene therapy, vaccines, oncolytic virus.
This pulls targeted cohorts for those classes from ClinicalTrials.gov v2, reusing the same
`compact()` record shape as the main fetch, and — critically — EXCLUDES every NCT already in
the original raw pull and the gold train/val/test splits, so augmentation can't leak the
test set or duplicate existing rows.

Output: data/raw/augment_rare.jsonl (net-new trials only). Free (public API, no key).

Run:  uv run python track-b-trialscout/data/fetch_rare_modalities.py --per-term 50
"""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path

import requests

from fetch_trials import API, compact  # same endpoint + record shape as the main fetch

ROOT = Path(__file__).resolve().parents[1]  # track-b-trialscout/
RAW = ROOT / "data" / "raw" / "trials.jsonl"
GOLD = ROOT / "data" / "gold"
OUT = ROOT / "data" / "raw" / "augment_rare.jsonl"

# Search terms per rare modality (CT.gov free-text). Kept broad; compact() + the teacher
# decide the final label — these just bias the *sampling* toward the tail.
TERMS = {
    "antibody-drug conjugate": ["antibody-drug conjugate", "antibody drug conjugate"],
    "bispecific": ["bispecific antibody", "bispecific T-cell engager"],
    "cell therapy": ["CAR-T", "chimeric antigen receptor", "TCR T-cell", "tumor infiltrating lymphocyte"],
    "gene therapy": ["gene therapy", "AAV gene therapy"],
    "cancer vaccine": ["cancer vaccine", "neoantigen vaccine", "peptide vaccine cancer"],
    "oncolytic virus": ["oncolytic virus", "oncolytic viral"],
}


def _excluded_nct_ids() -> set[str]:
    """Every NCT we must not re-pull: the original raw set + all gold splits."""
    seen: set[str] = set()
    if RAW.exists():
        seen |= {json.loads(line)["nct_id"] for line in RAW.read_text().splitlines() if line.strip()}
    for split in ("train", "val", "test", "all"):
        f = GOLD / f"{split}.jsonl"
        if f.exists():
            seen |= {json.loads(line)["nct_id"] for line in f.read_text().splitlines() if line.strip()}
    return seen


def _fetch_term(session: requests.Session, term: str, per_term: int, exclude: set[str]) -> list[dict]:
    out, token = [], None
    while len(out) < per_term:
        params = {
            "query.term": term,
            "query.cond": "cancer",
            "filter.advanced": "AREA[StudyType]INTERVENTIONAL",
            "pageSize": 200,
            "format": "json",
            "countTotal": "false",
        }
        if token:
            params["pageToken"] = token
        r = session.get(API, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        for st in data.get("studies", []):
            rec = compact(st)
            if rec and rec["nct_id"] and rec["nct_id"] not in exclude:
                exclude.add(rec["nct_id"])  # also dedupe across terms
                out.append(rec)
                if len(out) >= per_term:
                    break
        token = data.get("nextPageToken")
        if not token:
            break
        time.sleep(0.3)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-term", type=int, default=50, help="max NEW trials to keep per modality bucket")
    args = ap.parse_args()

    exclude = _excluded_nct_ids()
    print(f"Excluding {len(exclude)} already-used NCT ids (raw + gold splits).")
    session = requests.Session()

    rows: list[dict] = []
    for modality, terms in TERMS.items():
        before = len(rows)
        for term in terms:
            got = _fetch_term(session, term, args.per_term - (len(rows) - before), exclude)
            rows.extend(got)
            if len(rows) - before >= args.per_term:
                break
        print(f"  {modality:26s}: +{len(rows) - before} new")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"\nWrote {len(rows)} net-new trials -> {OUT}")


if __name__ == "__main__":
    main()
