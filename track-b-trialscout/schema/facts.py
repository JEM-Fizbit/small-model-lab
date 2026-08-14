"""The facts tier — everything in a readout that is a lookup, not a judgement.

WHY THIS EXISTS. Reviewing a v3 readout trial by trial, essentially every complaint was
about a *fact the record already contained*: the title was truncated, the sponsor was
missing, so were the dates, the enrollment, the phase, the recruitment status, and any
statement of whether the study was randomised, blinded, or single-arm. None of that needs a
language model. It needs the record read properly and printed.

That prompts the fair question -- if this much can be derived, why is a model involved at
all? The split this module encodes is the answer, and it is a narrow one:

    facts (here)   what the registry states     -> read it
    inference      what the registry implies    -> ask the model

``enrollment`` is stated. ``modalities`` is not: it requires knowing that trastuzumab
emtansine is an antibody-drug conjugate, which is pharmacology, not parsing. ADR-0022
already moved seven risk flags across this line after the teacher got ``enrollment < 50``
wrong 20 times in 150 -- boolean arithmetic on a number sitting in the record. This module
generalises that move rather than inventing a new principle.

WHAT IS DELIBERATELY ABSENT. Outcomes. Only 21.4% of this corpus carries a results section,
so "what happened in the trial" cannot be a reliable field; offering it would produce a
readout that is silently empty four times in five. Facts are emitted when present and
omitted when absent -- never inferred, never defaulted. A missing field means the registry
did not say, which is itself information an analyst needs.
"""
from __future__ import annotations

from .regimens import NON_DRUG_KINDS, canonical_agent, resolve

# CT.gov design vocabularies, mapped to words a person would use. Anything unlisted passes
# through in lower case rather than being coerced into a neighbour.
_MASKING = {
    "NONE": "open-label",
    "SINGLE": "single-blind",
    "DOUBLE": "double-blind",
    "TRIPLE": "triple-blind",
    "QUADRUPLE": "quadruple-blind",
}
_ASSIGNMENT = {
    "SINGLE_GROUP": "single-group",
    "PARALLEL": "parallel",
    "CROSSOVER": "crossover",
    "SEQUENTIAL": "sequential",
    "FACTORIAL": "factorial",
}
_ACTIVE_STATUSES = {"RECRUITING", "ENROLLING_BY_INVITATION", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING"}


def _date(struct: dict | None) -> str | None:
    return (struct or {}).get("date") or None


def _design(ps: dict, arms: list[dict]) -> dict:
    di = (ps.get("designModule") or {}).get("designInfo") or {}
    alloc = (di.get("allocation") or "").upper()
    masking_raw = ((di.get("maskingInfo") or {}).get("masking") or "").upper()
    model_raw = (di.get("interventionModel") or "").upper()

    # "NA" is not "non-randomised" -- it means allocation does not apply, which is what a
    # single-group study reports. Collapsing the two would assert a design choice the
    # sponsor never made, so an inapplicable allocation stays None.
    randomized: bool | None
    if alloc == "RANDOMIZED":
        randomized = True
    elif alloc == "NON_RANDOMIZED":
        randomized = False
    else:
        randomized = None

    arm_types = {(a.get("type") or "").upper() for a in arms}
    out = {
        "randomized": randomized,
        "masking": _MASKING.get(masking_raw, masking_raw.lower() or None),
        "assignment": _ASSIGNMENT.get(model_raw, model_raw.lower().replace("_", "-") or None),
        "purpose": (di.get("primaryPurpose") or "").lower().replace("_", " ") or None,
        "placebo_controlled": "PLACEBO_COMPARATOR" in arm_types or "SHAM_COMPARATOR" in arm_types,
        "active_comparator": "ACTIVE_COMPARATOR" in arm_types,
        "n_arms": len(arms) or None,
    }
    out["summary"] = _design_sentence(ps, out)
    return out


def _design_sentence(ps: dict, d: dict) -> str:
    """The one-line design descriptor an analyst expects at the top of a readout."""
    bits: list[str] = []
    phases = [p for p in ((ps.get("designModule") or {}).get("phases") or []) if p != "NA"]
    if phases:
        bits.append("/".join(p.replace("PHASE", "Phase ").replace("EARLY_Phase 1", "Early Phase 1") for p in phases))
    if d["randomized"] is True:
        bits.append("randomised")
    elif d["randomized"] is False:
        bits.append("non-randomised")
    if d["masking"]:
        bits.append(d["masking"])
    if d["placebo_controlled"]:
        bits.append("placebo-controlled")
    elif d["active_comparator"]:
        bits.append("active-controlled")
    n, asg = d["n_arms"], d["assignment"]
    if asg == "single-group":
        bits.append("single-arm")
    elif n and asg:
        bits.append(f"{n} {asg} arms")
    elif n:
        bits.append(f"{n} arms")
    return ", ".join(bits) if bits else "design not stated"


def _arms(ps: dict) -> list[dict]:
    out = []
    for a in (ps.get("armsInterventionsModule") or {}).get("armGroups") or []:
        out.append({
            "label": a.get("label"),
            "type": (a.get("type") or "").upper() or None,
            "interventions": list(a.get("interventionNames") or []),
            # 19.6% of trials give arms no description at all. Preserved as None so the
            # readout can say the registry is silent instead of implying a distinction.
            "description": a.get("description"),
        })
    return out


def _interventions(ps: dict) -> list[dict]:
    out = []
    for iv in (ps.get("armsInterventionsModule") or {}).get("interventions") or []:
        row = {
            "type": (iv.get("type") or "").upper() or None,
            "name": iv.get("name"),
            # Where dose and schedule actually live, on 89.2% of trials.
            "description": iv.get("description"),
            "other_names": list(iv.get("otherNames") or []) or None,
        }
        hit = resolve(iv.get("name", ""))
        if hit:
            row["resolved"] = hit
        out.append(row)
    return out


def agents(interventions: list[dict]) -> list[str]:
    """Distinct therapeutic agents, with regimen acronyms expanded.

    This is the list ``modalities`` is defined over, so an unexpanded ``COPP/ABV`` here
    under-reports by six drugs. Procedures and delivery routes are excluded by ``kind``:
    they are interventions but not agents, and letting them through is how a radiotherapy
    trial acquires a drug modality.
    """
    out: list[str] = []
    seen: set[str] = set()

    def add(nm: str | None) -> None:
        c = canonical_agent(nm or "")
        if c and c.casefold() not in seen:
            seen.add(c.casefold())
            out.append(c)

    for iv in interventions:
        hit = iv.get("resolved")
        if hit:
            if hit["kind"] in NON_DRUG_KINDS:
                continue
            for nm in hit["expansion"]:
                add(nm)
            # A partial composite -- "encorafenib + cetuximab + FOLFIRI" -- resolves only
            # the acronym. The unresolved halves are real agents and dropping them makes
            # this WORSE than not expanding at all: that trial lost two drugs, which is the
            # precise under-reporting the dictionary exists to prevent.
            for nm in hit.get("unresolved") or []:
                add(nm)
            continue
        if (iv.get("type") or "") not in {"DRUG", "BIOLOGICAL"}:
            continue
        # The intervention NAME is the agent. `otherNames` is deliberately NOT mined here.
        #
        # An earlier version treated a multi-entry `otherNames` as a constituent list,
        # generalising from NCT00592111 (prose name "intensive chemo with concurrent growth
        # factor", constituents listed as other names). That is the exception. CT.gov
        # specifies the field as SYNONYMS, and the common case is NCT00557193, where
        # "Asparaginase" carries 19 alternative spellings -- which produced 433 "agents"
        # for one trial and would have fed straight into modalities.
        #
        # The deeper objection is architectural: deciding whether a prose intervention name
        # implies specific drugs is a judgement about pharmacology, not a field lookup. It
        # belongs on the inference side of the line this module exists to draw. The names
        # stay in `interventions[].other_names` where the model can read them.
        add(iv.get("name"))
    return out


#: Prompt-build bounds. Chosen from the corpus, not by feel: arms are median 1 / p99 9,
#: interventions median 2 / p99 12, so these leave >99% of trials untouched. ADR-0021's
#: finding was that limits applied at INGEST are unrecoverable; these apply at prompt-build
#: against a full archived record, so widening them costs a re-run and no re-fetch.
MAX_ARMS = 12
MAX_INTERVENTIONS = 15


def project_for_prompt(f: dict, max_arms: int = MAX_ARMS, max_ivs: int = MAX_INTERVENTIONS) -> dict:
    """Bound the facts tier for prompting, marking any elision in the payload itself.

    A truncation the model cannot see is a truncation it will answer over confidently --
    the trial with 39 arms would otherwise look like a 12-arm trial. Every cut states its
    own size, so `modalities` can be qualified rather than silently under-reported.
    """
    out = dict(f)
    for key, cap, label in (("arms", max_arms, "arms"), ("interventions", max_ivs, "interventions")):
        items = f.get(key) or []
        if len(items) > cap:
            out[key] = items[:cap]
            out[f"{label}_elided"] = len(items) - cap
    return out


def extract(study: dict) -> dict:
    """Build the facts tier from a full ClinicalTrials.gov v2 study record.

    Takes the FULL archived record, not the compact one -- the compact shape drops arms,
    intervention descriptions, and most dates, which is exactly the material this tier
    exists to surface (ADR-0021).
    """
    ps = study.get("protocolSection") or {}
    ident = ps.get("identificationModule") or {}
    status = ps.get("statusModule") or {}
    design_mod = ps.get("designModule") or {}
    sponsor = (ps.get("sponsorCollaboratorsModule") or {}).get("leadSponsor") or {}
    enroll = design_mod.get("enrollmentInfo") or {}
    arms = _arms(ps)
    ivs = _interventions(ps)
    overall = (status.get("overallStatus") or "").upper() or None
    phases = [p for p in (design_mod.get("phases") or []) if p != "NA"]

    return {
        "nct_id": ident.get("nctId"),
        # Full titles, never abridged. A truncated title was the first thing a reader
        # flagged, and the registry's own official title is the authoritative one.
        "title": ident.get("officialTitle") or ident.get("briefTitle"),
        "brief_title": ident.get("briefTitle"),
        "phase": "/".join(phases) or None,
        "sponsor": {"name": sponsor.get("name"), "class": (sponsor.get("class") or "").upper() or None},
        "status": {
            "overall": overall,
            "is_recruiting": overall == "RECRUITING",
            "is_active": overall in _ACTIVE_STATUSES,
            "start_date": _date(status.get("startDateStruct")),
            "primary_completion_date": _date(status.get("primaryCompletionDateStruct")),
            "primary_completion_type": (status.get("primaryCompletionDateStruct") or {}).get("type"),
            "completion_date": _date(status.get("completionDateStruct")),
            "last_update": _date(status.get("lastUpdatePostDateStruct")),
        },
        "enrollment": enroll.get("count"),
        # ACTUAL vs ESTIMATED is the difference between a fact and a plan, and an analyst
        # reads them differently. Never flattened to a bare number.
        "enrollment_type": (enroll.get("type") or "").upper() or None,
        "conditions": list((ps.get("conditionsModule") or {}).get("conditions") or []),
        "design": _design(ps, arms),
        "arms": arms,
        "interventions": ivs,
        "agents": agents(ivs),
        # 21.4% of the corpus. Stated so a reader knows whether outcomes exist at all.
        "has_results": bool(study.get("hasResults")),
    }
