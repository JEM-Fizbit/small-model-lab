"""Fetch oncology interventional trials from ClinicalTrials.gov API v2.

Public API, no key. Pulls cancer trials, keeps INTERVENTIONAL studies that have a
phase, extracts a compact record (just the fields TrialScout needs), and writes
JSONL to data/raw/trials.jsonl.

Run:  uv run python track-b-trialscout/data/fetch_trials.py --target 1500
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
import requests

API = "https://clinicaltrials.gov/api/v2/studies"
RAW = Path(__file__).resolve().parent / "raw" / "trials.jsonl"


def compact(study: dict) -> dict | None:
    """Pull a small, model-friendly record from the full study object."""
    ps = study.get("protocolSection", {})
    idm = ps.get("identificationModule", {})
    dm = ps.get("designModule", {})
    stm = ps.get("statusModule", {})
    spm = ps.get("sponsorCollaboratorsModule", {})
    cm = ps.get("conditionsModule", {})
    aim = ps.get("armsInterventionsModule", {})
    om = ps.get("outcomesModule", {})
    elm = ps.get("eligibilityModule", {})

    if dm.get("studyType") != "INTERVENTIONAL":
        return None
    phases = [p for p in (dm.get("phases") or []) if p not in ("NA", "")]
    if not phases:
        return None

    lead = spm.get("leadSponsor", {})
    interventions = [
        {"type": i.get("type"), "name": i.get("name")}
        for i in (aim.get("interventions") or [])
    ][:6]
    primary_outcomes = [
        {"measure": o.get("measure"), "timeFrame": o.get("timeFrame")}
        for o in (om.get("primaryOutcomes") or [])
    ][:4]
    enroll = dm.get("enrollmentInfo", {}) or {}
    design = dm.get("designInfo", {}) or {}

    return {
        "nct_id": idm.get("nctId"),
        "brief_title": idm.get("briefTitle"),
        "phases": phases,
        "overall_status": stm.get("overallStatus"),
        "start_date": (stm.get("startDateStruct") or {}).get("date"),
        "primary_completion_date": (stm.get("primaryCompletionDateStruct") or {}).get("date"),
        "lead_sponsor": lead.get("name"),
        "lead_sponsor_class": lead.get("class"),  # INDUSTRY / NIH / OTHER / etc.
        "conditions": (cm.get("conditions") or [])[:8],
        "interventions": interventions,
        "primary_outcomes": primary_outcomes,
        "enrollment": enroll.get("count"),
        "enrollment_type": enroll.get("type"),
        "allocation": design.get("allocation"),
        "masking": (design.get("maskingInfo") or {}).get("masking"),
        "n_arms": len(aim.get("armGroups") or []) or None,
        "eligibility_sex": elm.get("sex"),
        "minimum_age": elm.get("minimumAge"),
        "healthy_volunteers": elm.get("healthyVolunteers"),
        "brief_summary": (ps.get("descriptionModule", {}) or {}).get("briefSummary"),
    }


def fetch(target: int) -> list[dict]:
    out, token, seen = [], None, set()
    session = requests.Session()
    while len(out) < target:
        params = {
            "query.cond": "cancer",
            "filter.advanced": "AREA[StudyType]INTERVENTIONAL",
            "pageSize": 1000,
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
            if rec and rec["nct_id"] and rec["nct_id"] not in seen:
                seen.add(rec["nct_id"])
                out.append(rec)
                if len(out) >= target:
                    break
        token = data.get("nextPageToken")
        print(f"  fetched {len(out)}/{target} (kept interventional+phased)", flush=True)
        if not token:
            break
        time.sleep(0.3)  # be polite to the public API
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=1500)
    args = ap.parse_args()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    print(f"Fetching ~{args.target} oncology interventional trials from CT.gov v2 ...")
    rows = fetch(args.target)
    with RAW.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    # quick distribution summary
    from collections import Counter
    ph = Counter(tuple(r["phases"]) for r in rows)
    cls = Counter(r["lead_sponsor_class"] for r in rows)
    print(f"\nWrote {len(rows)} trials -> {RAW}")
    print("phase mix:", dict(ph.most_common(8)))
    print("sponsor class mix:", dict(cls))


if __name__ == "__main__":
    main()
