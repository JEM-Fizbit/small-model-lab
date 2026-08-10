"""Fetch trials enriched for the RARE modalities.

Two uses, selected by --profile:
  train      Phase-4 style augmentation, merged into training (ADR-0011, ADR-0019).
  diagnostic A HELD-OUT measurement set (ADR-0020). Never trained on. It exists because the
             frozen 150-trial test set holds 5 ADCs, 3 oncolytic viruses and 2 bispecifics, so
             one trial is worth 20-50 recall points and no training experiment on the tail can
             be read. Fixing the instrument has to come before further training work.

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

# The v2 taxonomy (ADR-0017) added classes the Phase-4 terms never targeted. These search
# terms bias the SAMPLING only -- the teacher still assigns the label, so the realized class
# counts will not match the requested ones and have to be checked after labelling.
TERMS_V2_EXTRA = {
    "radiopharmaceutical": ["radioligand therapy", "Lutetium-177", "radiopharmaceutical",
                            "PSMA-617", "radioimmunotherapy", "Actinium-225"],
    "oligonucleotide/RNA therapeutic": ["antisense oligonucleotide", "siRNA cancer",
                                        "mRNA cancer vaccine", "aptamer cancer"],
    "other protein or peptide therapeutic": ["fusion protein cancer", "recombinant interleukin",
                                             "interferon cancer", "immunotoxin", "enzyme therapy cancer"],
}


def _excluded_nct_ids() -> set[str]:
    """Every NCT we must not re-pull.

    The original raw pull, all gold splits, AND the Phase-4 augment -- which lives in its own
    file and is merged into TRAIN by format_for_mlx. Omitting it (as this function originally
    did) would let a diagnostic set silently contain trials the model was trained on, which is
    the one thing a diagnostic set must never do.
    """
    seen: set[str] = set()
    for f in (RAW, ROOT / "data" / "raw" / "augment_rare.jsonl"):
        if f.exists():
            seen |= {json.loads(line)["nct_id"] for line in f.read_text().splitlines() if line.strip()}
    for split in ("train", "val", "test", "all", "augment_rare"):
        f = GOLD / f"{split}.jsonl"
        if f.exists():
            seen |= {json.loads(line)["nct_id"] for line in f.read_text().splitlines() if line.strip()}
    for f in (GOLD / "v1-archive").glob("*.jsonl"):
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
    ap.add_argument("--profile", choices=["train", "diagnostic"], default="train",
                    help="'train' = Phase-4 augmentation terms; 'diagnostic' = those PLUS the "
                         "classes the v2 taxonomy added, written to a separate held-out file.")
    args = ap.parse_args()
    terms_map = dict(TERMS)
    out_path = OUT
    if args.profile == "diagnostic":
        terms_map.update(TERMS_V2_EXTRA)
        out_path = ROOT / "data" / "raw" / "rare_diagnostic.jsonl"

    exclude = _excluded_nct_ids()
    print(f"Excluding {len(exclude)} already-used NCT ids (raw + gold splits).")
    session = requests.Session()

    rows: list[dict] = []
    for modality, terms in terms_map.items():
        before = len(rows)
        for term in terms:
            got = _fetch_term(session, term, args.per_term - (len(rows) - before), exclude)
            rows.extend(got)
            if len(rows) - before >= args.per_term:
                break
        print(f"  {modality:26s}: +{len(rows) - before} new")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"\nWrote {len(rows)} net-new trials -> {out_path}")


if __name__ == "__main__":
    main()
