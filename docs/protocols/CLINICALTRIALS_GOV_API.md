# ClinicalTrials.gov API v2

> Query the public ClinicalTrials.gov v2 REST API: search studies, extract a compact record from the nested `protocolSection`, and paginate with `nextPageToken`.

**Applies to:** ClinicalTrials.gov API **v2** (`https://clinicaltrials.gov/api/v2`) · Python `requests` (or any HTTP client) · biopharma trial data pipelines
**Last Updated:** 2026-06-14
**Version:** 1.1
**Original Source:** `small-model-lab/track-b-trialscout/data/fetch_trials.py` (+ `fetch_rare_modalities.py`); also used in `pharma-signal-poc`; point-in-time history from `aigent-alpha/src/aigent_alpha/catalyst/`

---

## Overview

ClinicalTrials.gov v2 is a **free, key-less, public** JSON API over the registry of clinical studies. Two endpoints cover almost everything:

- `GET /api/v2/studies` — **search/list** studies (with filters + pagination).
- `GET /api/v2/studies/{nctId}` — **fetch one** study by NCT id.

The data model is deeply nested under `protocolSection`; in practice you extract a **compact flat record** of just the fields you need.

### Key benefits
- No API key, no auth, no cost; generous `pageSize` (up to 1000).
- One record shape reusable across screening, landscape, and training-data pipelines.

---

## When to Use

| Scenario | Use this? |
|----------|-----------|
| Pull trials by condition / intervention / phase | **Yes** |
| Fetch one trial by NCT id (e.g. to enrich a candidate) | **Yes** — single-study endpoint |
| **What was knowable on a past date** (backtests, point-in-time, "what did the record say in 2018?") | **Yes — but NOT the v2 API.** The current record is a lookahead trap; use the internal **history** API (see Point-in-time history below) |
| FDA approval / NDA cross-reference | No → [`FDA_OPENFDA_API.md`](FDA_OPENFDA_API.md) |
| Drug compound / MoA / indication phase | No → [`CHEMBL_API_INTEGRATION.md`](CHEMBL_API_INTEGRATION.md) |
| Literature / PubMed | No → [`NCBI_EUTILITIES_INTEGRATION.md`](NCBI_EUTILITIES_INTEGRATION.md) |

---

## Quick Start

```python
import requests

API = "https://clinicaltrials.gov/api/v2/studies"

# Search: interventional cancer trials, first page
r = requests.get(API, params={
    "query.cond": "cancer",
    "filter.advanced": "AREA[StudyType]INTERVENTIONAL",
    "pageSize": 1000,
    "format": "json",
    "countTotal": "false",
}, timeout=60)
r.raise_for_status()
data = r.json()
studies, token = data["studies"], data.get("nextPageToken")

# Fetch one study by NCT id → returns the study object directly (protocolSection at top)
one = requests.get(f"{API}/NCT02942290", params={"format": "json"}, timeout=30).json()
```

---

## Core Concepts

### Query parameters

| Param | Meaning |
|-------|---------|
| `query.cond` | **Condition/disease** search (e.g. `"cancer"`, `"fibromyalgia"`). |
| `query.term` | **Free-text** search across the record (e.g. `"CAR-T"`, `"antibody-drug conjugate"`). Use to bias sampling toward a modality/keyword. |
| `filter.advanced` | **Essie expression** filter. Syntax: `AREA[<field>]<value>`, combinable with `AND`/`OR`. The workhorse: `AREA[StudyType]INTERVENTIONAL`. |
| `pageSize` | Results per page. **Max 1000.** |
| `format` | `json` (default is JSON-ish; set it explicitly). |
| `countTotal` | `true` returns a total count (slower); usually `false`. |
| `pageToken` | Opaque cursor for the next page (see Pagination). |

`query.cond` vs `query.term`: `cond` matches the **condition** field specifically; `term` is a broad full-text match. Combine them (`query.cond=cancer` + `query.term="bispecific"`) to narrow.

### Pagination — token, not page numbers

There is **no `page=N`**. Each response carries `nextPageToken`; pass it back as `pageToken` for the next page. Stop when it's absent.

```python
out, token, seen = [], None, set()
while len(out) < target:
    params = {"query.cond": "cancer",
              "filter.advanced": "AREA[StudyType]INTERVENTIONAL",
              "pageSize": 1000, "format": "json", "countTotal": "false"}
    if token:
        params["pageToken"] = token
    data = requests.get(API, params=params, timeout=60).json()
    for st in data.get("studies", []):
        rec = compact(st)
        if rec and rec["nct_id"] not in seen:
            seen.add(rec["nct_id"]); out.append(rec)
    token = data.get("nextPageToken")
    if not token:
        break
    time.sleep(0.3)            # be polite to a free public API
```

### `protocolSection` module structure

Each study = `{ "protocolSection": {...}, "derivedSection": {...}, "hasResults": bool }`. The fields you want live in `protocolSection`'s modules:

| Module | Useful fields |
|--------|---------------|
| `identificationModule` | `nctId`, `briefTitle` |
| `statusModule` | `overallStatus`, `startDateStruct.date`, `primaryCompletionDateStruct.date` |
| `designModule` | `studyType`, `phases[]`, `enrollmentInfo.{count,type}`, `designInfo.{allocation, maskingInfo.masking}` |
| `sponsorCollaboratorsModule` | `leadSponsor.{name, class}` |
| `conditionsModule` | `conditions[]` |
| `armsInterventionsModule` | `interventions[].{type, name}`, `armGroups[]` |
| `outcomesModule` | `primaryOutcomes[].{measure, timeFrame}` |
| `eligibilityModule` | `sex`, `minimumAge`, `healthyVolunteers` |
| `descriptionModule` | `briefSummary` |

`leadSponsor.class` ∈ `INDUSTRY` / `NIH` / `FED` / `NETWORK` / `OTHER` / `OTHER_GOV` / `INDIV`. `phases` is a list like `["PHASE1","PHASE2"]`, or `["NA"]` / empty for non-phased studies.

---

## Implementation: compact-record extraction

Reduce the nested study to a flat, model/pipeline-friendly record. (Harvested from the reference impl.)

```python
def compact(study: dict) -> dict | None:
    ps = study.get("protocolSection", {})
    idm = ps.get("identificationModule", {})
    dm  = ps.get("designModule", {})
    stm = ps.get("statusModule", {})
    spm = ps.get("sponsorCollaboratorsModule", {})
    cm  = ps.get("conditionsModule", {})
    aim = ps.get("armsInterventionsModule", {})
    om  = ps.get("outcomesModule", {})
    elm = ps.get("eligibilityModule", {})

    if dm.get("studyType") != "INTERVENTIONAL":          # filter at extraction
        return None
    phases = [p for p in (dm.get("phases") or []) if p not in ("NA", "")]
    if not phases:                                        # drop phase-less studies
        return None

    lead = spm.get("leadSponsor", {})
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
        "lead_sponsor_class": lead.get("class"),
        "conditions": (cm.get("conditions") or [])[:8],
        "interventions": [{"type": i.get("type"), "name": i.get("name")}
                          for i in (aim.get("interventions") or [])][:6],
        "primary_outcomes": [{"measure": o.get("measure"), "timeFrame": o.get("timeFrame")}
                             for o in (om.get("primaryOutcomes") or [])][:4],
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
```

The **single-study endpoint** (`/studies/{nctId}`) returns the study object **directly** (with `protocolSection` at the top level), so `compact(resp.json())` works unchanged — handy for enriching a candidate by NCT id.

---

## Anti-Patterns

```python
# ❌ Page numbers — there is no page param; you'll re-fetch page 1 forever
params = {"page": n}
# ✅ Carry the cursor
if token: params["pageToken"] = token

# ❌ Trusting `phases` to be present/clean
phase = study[...]["phases"][0]              # KeyError / "NA" leaks through
# ✅ Filter NA/empty, skip phase-less studies
phases = [p for p in (dm.get("phases") or []) if p not in ("NA", "")]

# ❌ Hammering the free API with no delay across hundreds of pages
# ✅ time.sleep(0.3) between pages; dedupe on nct_id across pages

# ❌ Walking the raw nested study everywhere downstream
# ✅ Extract a compact flat record once; pass that around
```

---

## Point-in-time history (the lookahead trap)

The v2 `/studies/{nctId}` endpoint returns the **current** record. For anything
time-sensitive — backtests, "what did we know on date D", event-study windows — that
is a **lookahead trap**: the estimated primary-completion date (`primaryCompletionDateStruct`)
is silently revised over a trial's life, and an `ACTUAL` date is stamped only *after*
the event resolves. Reading "the date" off today's record schedules decisions against
information that did not exist at decision time.

**The public v2 REST API has NO history endpoint.** `GET /api/v2/studies/{nctId}/history`
returns **404** (verified 2026-06-14) — don't build on it, and don't trust a fallback
that silently collapses to the current record (it cannot reconstruct *prior* estimates).

**Use the CT.gov internal API the website itself uses** (two calls):

```python
# 1. The change list: every public version, its post date, and which modules changed.
GET https://clinicaltrials.gov/api/int/studies/{nct}/history
#    -> {"changes": [{"version": 0, "date": "2013-03-22", "moduleLabels": [...]}, ...]}

# 2. One version's full record (read protocolSection like any v2 study record).
GET https://clinicaltrials.gov/api/int/studies/{nct}/history/{version}
#    -> {"studyVersion": N, "study": {"protocolSection": {...}}}
```

**Reconstruction recipe** (per field of interest, e.g. `primaryCompletionDateStruct`):
1. Fetch the change list. The `date` on each change is the **`recorded_on`** — the only
   thing that makes that version's value *knowable*.
2. **Prune**: only fetch versions whose `moduleLabels` include the module that holds your
   field (PCD lives in `"Study Status"`), plus version 0. Versions that didn't touch the
   module inherit the prior value, so skipping them is exact and bounds the per-trial
   fetch count (a busy trial has tens of versions).
3. For each fetched version read the field; emit a revision only when the value (date **or**
   `ESTIMATED`/`ACTUAL` type) actually changes. The result is a faithful revision trail.
4. Query it **as-of** a date: the latest revision whose `recorded_on <= as_of`. A revision
   recorded after `as_of` (e.g. the post-event `ACTUAL`) is thereby never leaked back.

Worked example (NCT01818596): est `2014-07` recorded 2013-03-22 → `ACTUAL 2014-07` recorded
2014-09-16 (after the event) → refined `2014-07-31` recorded 2017-02-27. So as-of 2014-01-01
correctly yields the estimate, never the actual.

**Caveats.**
- `/api/int/` is **undocumented** — it backs the live website so it is stable in practice,
  but it is not a published contract. Isolate it behind one function, keep it out of any
  hermetic test suite, and keep a fallback.
- **AACT** (CTTI's free Postgres mirror) is the documented alternative but is **strictly
  worse for point-in-time**: snapshots are *monthly* (coarse `recorded_on`, intra-month
  revisions lost), it needs a hosted/downloaded DB, and one snapshot still holds only the
  then-current record (true PIT needs diffing many). Keep it as the fallback if `/api/int/`
  breaks, not the default.
- Make the **pure reconstruction** (change-list + per-version values → revision trail) a
  separate function from the network I/O, so it is unit-testable on fixtures with a
  known-answer as-of assertion. Reference impl: `aigent-alpha/src/aigent_alpha/catalyst/`
  (`sourcing.py` `reconstruct_pcd_revisions` / `versions_to_fetch`; `pointintime.py`
  `pcd_as_of`).

---

## Troubleshooting

**`400 Bad Request` on the single-study endpoint.** The NCT id is malformed (must be `NCT` + 8 digits, uppercase). Normalize/validate before the call.

**Empty `studies` but a `nextPageToken`.** Your `filter.advanced` Essie expression excluded everything on that page — keep paging, or check the `AREA[...]` field name/value.

**Counts look wrong / slow.** `countTotal=true` is expensive; leave it `false` and stop on absent `nextPageToken`.

**A study is missing fields.** Modules are optional. Always `.get(...)` with defaults (the `compact()` pattern); never index blindly into `protocolSection`.

---

## Resources

- API docs: `https://clinicaltrials.gov/data-api/api`
- Reference impl: `small-model-lab/track-b-trialscout/data/fetch_trials.py` (bulk search) + `fetch_rare_modalities.py` (term-targeted sampling with exclude-set dedup).
- Sibling bio data-source protocols: [`FDA_OPENFDA_API.md`](FDA_OPENFDA_API.md), [`CHEMBL_API_INTEGRATION.md`](CHEMBL_API_INTEGRATION.md), [`NCBI_EUTILITIES_INTEGRATION.md`](NCBI_EUTILITIES_INTEGRATION.md).

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-06-08 | Initial release. Extracted from small-model-lab + pharma-signal-poc CT.gov v2 usage. |
| 1.1 | 2026-06-14 | Added **Point-in-time history** section: the v2 API has no history endpoint (404); reconstruct prior estimated/actual dates from the internal `/api/int/studies/{nct}/history` + `/history/{version}` API; prune-by-moduleLabels recipe, as-of query, AACT-is-worse, pure-vs-network split. From aigent-alpha. |

---

**Protocol Version**: 1.1
**Last Updated**: 2026-06-14
**Original Source**: small-model-lab (track-b-trialscout/data), pharma-signal-poc
