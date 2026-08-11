"""Fetch oncology interventional trials from ClinicalTrials.gov API v2.

Public API, no key. Keeps INTERVENTIONAL studies that have a phase.

**Archive the whole study, trim only at prompt-build time.** The original version trimmed
on the way in -- `interventions[:6]`, `primary_outcomes[:4]`, `conditions[:8]`,
`brief_summary[:600]` -- and discarded intervention and arm descriptions entirely. Those
limits were round numbers, never chosen against evidence, and because the trimming happened
at *download* time the discarded content was unrecoverable without re-fetching. An audit on
2026-08-10 measured what they cost:

  brief_summary[:600]     32% of trials exceeded it
  primary_outcomes[:4]     9%   (measured harmless: endpoint accuracy 0.952 vs 0.958)
  interventions[:6]        8%   (NOT harmless: modalities exact-set 0.699 -> 0.568)
  conditions[:8]           5%
  intervention.description dropped entirely -- and it is where a codenamed asset is often
                           identified ("BM7PE immunotoxin"), which is exactly the failure
                           mode behind the weakest modality classes.

Full study objects are 3-44 KB, so the entire corpus archives in ~45 MB. There was never a
reason to pay for this. `--full` writes the untouched studies to data/raw/studies_full.jsonl;
`compact()` now takes explicit limits, so every trim is a reversible decision made where the
prompt is built rather than a permanent loss at the point of download.

Run:  uv run python track-b-trialscout/data/fetch_trials.py --target 1500 --full
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
import requests

API = "https://clinicaltrials.gov/api/v2/studies"
RAW = Path(__file__).resolve().parent / "raw" / "trials.jsonl"
FULL = Path(__file__).resolve().parent / "raw" / "studies_full.jsonl"  # untouched study objects


# Default trims, applied at prompt-build time rather than at download. Every one of these
# is now a parameter: change it and rebuild the prompt, no re-fetch required.
# Measured 2026-08-10 (see the module docstring). `interventions` and `descriptions` changed
# with the v3 regeneration; the two that stayed did so on evidence, not inertia:
#   primary_outcomes[:4]  9% hit it, endpoint accuracy 0.952 vs 0.958 at the cap -- harmless
#   conditions[:8]        5% hit it, on a field nothing scores
# Removing a limit that costs nothing is churn; these stay until something says otherwise.
LIMITS = {"interventions": None,   # was 6: 122 trials (5.5%) exceeded it and 510 agents were
                                   # discarded, one trial losing 24 of 30. `modalities` means
                                   # "list every agent", so this was deleting the answer.
          "primary_outcomes": 4,
          "conditions": 8,
          "brief_summary": 600,    # applied in format_for_mlx.trial_input, not here
          "descriptions": True,    # intervention.description carries the only class word on 7%
                                   # of trials ("BM7PE immunotoxin") -- see ADR-0021
          "description_chars": 300}
# 300 chosen from the FULL corpus, not a sample. Uncapped, one 20-intervention trial reached
# 14,560 chars of descriptions and a 3,900-token prompt. At 300 the longest paired
# prompt+target is 2,541 tokens (fits --max-seq-length 2560 with zero truncation) and 97% of
# the class-word signal survives, because the class is named in the first sentence
# ("BM7PE immunotoxin is supplied as..."). A 400-record sample had said the max was 1,733 --
# tail-sensitive limits must be set from the whole distribution.


def compact(study: dict, limits: dict | None = None) -> dict | None:
    """Pull a model-friendly record from a full study object.

    `limits` overrides LIMITS per key. Pass {"interventions": None} for no cap.
    """
    lim = {**LIMITS, **(limits or {})}
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
    def _iv(i):
        d = {"type": i.get("type"), "name": i.get("name")}
        if lim["descriptions"] and i.get("description"):
            d["description"] = i["description"][:lim["description_chars"]]
        return d
    interventions = [_iv(i) for i in (aim.get("interventions") or [])][:lim["interventions"]]
    primary_outcomes = [
        {"measure": o.get("measure"), "timeFrame": o.get("timeFrame")}
        for o in (om.get("primaryOutcomes") or [])
    ][:lim["primary_outcomes"]]
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
        "conditions": (cm.get("conditions") or [])[:lim["conditions"]],
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


def fetch(target: int, keep_full: list | None = None) -> list[dict]:
    """Return compact records; if `keep_full` is a list, append the untouched studies to it."""
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
                if keep_full is not None:
                    keep_full.append(st)
                if len(out) >= target:
                    break
        token = data.get("nextPageToken")
        print(f"  fetched {len(out)}/{target} (kept interventional+phased)", flush=True)
        if not token:
            break
        time.sleep(0.3)  # be polite to the public API
    return out


def fetch_by_ids(nct_ids: list[str], keep_full: list | None = None, workers: int = 8) -> list[dict]:
    """Re-fetch SPECIFIC trials by NCT id.

    Required for any re-fetch of an existing corpus: the discovery query walks CT.gov pages and
    would return a different set of trials, which would silently invalidate data/splits.json and
    every frozen comparison built on it. Fetching by id keeps the corpus identical and changes
    only how much of each record we keep.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    out: list[dict] = []
    session = requests.Session()

    def one(nct: str):
        for attempt in range(4):
            try:
                r = session.get(f"{API}/{nct}", params={"format": "json"}, timeout=30)
                if r.status_code == 404:
                    return nct, None
                r.raise_for_status()
                return nct, r.json()
            except Exception:
                if attempt == 3:
                    return nct, None
                time.sleep(2 ** attempt)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, n) for n in nct_ids]
        for i, fut in enumerate(as_completed(futs), 1):
            nct, study = fut.result()
            if study is None:
                print(f"  MISSING {nct}", flush=True)
                continue
            rec = compact(study)
            if rec is None:
                print(f"  FILTERED OUT {nct} (no longer interventional+phased)", flush=True)
                continue
            out.append(rec)
            if keep_full is not None:
                keep_full.append(study)
            if i % 250 == 0:
                print(f"  {i}/{len(nct_ids)}", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids-from", type=str, default=None,
                    help="JSONL of records with nct_id: re-fetch exactly those trials. Use this for "
                         "any re-fetch -- the discovery query would return a DIFFERENT corpus and "
                         "invalidate data/splits.json.")
    ap.add_argument("--target", type=int, default=1500)
    ap.add_argument("--full", action="store_true",
                    help="also archive the untouched study objects to raw/studies_full.jsonl, so "
                         "future trim decisions never need a re-fetch (~20 KB/trial)")
    ap.add_argument("--out", type=str, default=str(RAW))
    ap.add_argument("--full-out", type=str, default=str(FULL))
    ap.add_argument("--append-full", action="store_true", help="append to the full archive instead of overwriting")
    args = ap.parse_args()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    print(f"Fetching ~{args.target} oncology interventional trials from CT.gov v2 ...")
    full: list | None = [] if args.full else None
    if args.ids_from:
        ids = [json.loads(x)["nct_id"] for x in Path(args.ids_from).read_text().splitlines() if x.strip()]
        print(f"re-fetching {len(ids)} trials BY ID from {args.ids_from}")
        rows = fetch_by_ids(ids, keep_full=full)
    else:
        rows = fetch(args.target, keep_full=full)
    if full is not None:
        with Path(args.full_out).open("a" if args.append_full else "w") as f:
            for st in full:
                f.write(json.dumps(st) + "\n")
        mb = FULL.stat().st_size / 1e6
        print(f"archived {len(full)} full study objects -> {FULL} ({mb:.0f} MB)")
    with Path(args.out).open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    # quick distribution summary
    from collections import Counter
    ph = Counter(tuple(r["phases"]) for r in rows)
    cls = Counter(r["lead_sponsor_class"] for r in rows)
    print(f"\nWrote {len(rows)} trials -> {args.out}")
    print("phase mix:", dict(ph.most_common(8)))
    print("sponsor class mix:", dict(cls))


if __name__ == "__main__":
    main()
