"""Assemble the complete TrialScout readout from its three sources.

THE ONE PLACE the finished record is built. Until v4.1 no such place existed: the serve
layer merged risk flags and left every other field to whatever the caller stitched
together, and the worked example in review was assembled by a throwaway script. A product
whose central claim is "these fields come from different places and you should trust them
differently" cannot leave the joining-up to ad-hoc code at each call site.

Three sources, and the whole design rests on keeping them apart:

    registry   read verbatim from the ClinicalTrials.gov record   (schema/facts.py)
    computed   arithmetic on that record                          (schema/derive.py)
    model      inference the record does not state                (the LoRA / teacher)

The model contributes six fields. Everything else is a lookup or a calculation, and asking
a language model for those was measurably worse than an `if` statement -- the teacher got
`enrollment < 50` wrong 20 times in 150 (ADR-0022).

`_provenance` ships by default. In the flat record `sponsor_type` (a table lookup) and
`modalities` (a 4B model's pharmacology judgement) sit side by side looking equally
authoritative, and an analyst has no way to tell which is which. Naming the source per
field is the cheapest possible honesty for a tool built on that distinction.
"""
from __future__ import annotations

from .derive import derive_est_readout, derive_sponsor_type, merge_risk_flags
from .facts import extract

#: Fields the model is asked for. Everything else in the readout is read or computed.
MODEL_FIELDS = (
    "indication",
    "intervention_class",
    "modalities",
    "primary_endpoint_type",
    "risk_flags_judgement",
    "investor_note",
)

PROVENANCE = {
    "nct_id": "registry", "title": "registry", "phase": "registry",
    "sponsor": "registry", "status": "registry", "enrollment": "registry",
    "enrollment_type": "registry", "design": "registry", "arms": "registry",
    "interventions": "registry", "agents": "registry", "conditions": "registry",
    "primary_outcomes": "registry", "has_results": "registry",
    "sponsor_type": "computed", "est_readout": "computed",
    "indication": "model", "intervention_class": "model", "modalities": "model",
    "primary_endpoint_type": "model", "investor_note": "model",
    "risk_flags": "computed+model",
}


def _flag_record(f: dict) -> dict:
    """Re-shape the facts tier into the compact keys derive_risk_flags expects.

    derive.py predates the facts tier and reads the flat CT.gov-ish record v3 used. Mapping
    here rather than rewriting derive.py keeps the arithmetic flags byte-identical to the
    ones the v3 numbers were computed with.
    """
    d = f.get("design") or {}
    randomized = d.get("randomized")
    return {
        "enrollment": f.get("enrollment"),
        "overall_status": (f.get("status") or {}).get("overall"),
        "phases": [f["phase"]] if f.get("phase") else [],
        # None means CT.gov said allocation is NA -- not applicable, not "non-randomised".
        "allocation": ("RANDOMIZED" if randomized is True
                       else "NON_RANDOMIZED" if randomized is False else "NA"),
        "masking": "NONE" if d.get("masking") == "open-label" else (d.get("masking") or ""),
        "n_arms": d.get("n_arms"),
        "start_date": (f.get("status") or {}).get("start_date"),
        "primary_completion_date": (f.get("status") or {}).get("primary_completion_date"),
    }


def assemble(study: dict, inferred: dict, *,
             provenance: bool = True, detail: bool = False) -> dict:
    """Build the finished readout.

    ``study``    a full ClinicalTrials.gov v2 record (not the compact v3 shape)
    ``inferred`` the model's output -- the six MODEL_FIELDS
    ``detail``   include arms, interventions and outcome measures. Off by default: the
                 summary record is what a reader wants, and the detail is what a reader
                 wants when they doubt it.

    Missing model fields are omitted rather than defaulted. A readout that silently prints
    an empty ``modalities`` is indistinguishable from a trial that genuinely tests no drug,
    and that ambiguity is the exact defect schema v1 shipped.
    """
    f = extract(study)
    status = f.get("status") or {}
    out: dict = {
        "nct_id": f.get("nct_id"),
        "title": f.get("title"),
        "phase": f.get("phase"),
        "indication": inferred.get("indication"),
        "sponsor": (f.get("sponsor") or {}).get("name"),
        "sponsor_type": derive_sponsor_type(f),
        "status": status.get("overall"),
        "is_active": status.get("is_active"),
        "enrollment": f.get("enrollment"),
        "enrollment_type": f.get("enrollment_type"),
        "design": (f.get("design") or {}).get("summary"),
        "intervention_class": inferred.get("intervention_class"),
        "modalities": inferred.get("modalities"),
        "agents": f.get("agents"),
        "primary_endpoint_type": inferred.get("primary_endpoint_type"),
        "est_readout": derive_est_readout(f),
        "risk_flags": merge_risk_flags(_flag_record(f), inferred.get("risk_flags_judgement")),
        "has_results": f.get("has_results"),
        "investor_note": inferred.get("investor_note"),
    }
    if detail:
        out["conditions"] = f.get("conditions")
        out["arms"] = f.get("arms")
        out["interventions"] = f.get("interventions")
        out["primary_outcomes"] = f.get("primary_outcomes")
        out["start_date"] = status.get("start_date")
        out["primary_completion_date"] = status.get("primary_completion_date")
        out["completion_date"] = status.get("completion_date")
    out = {k: v for k, v in out.items() if v is not None}
    if provenance:
        out["_provenance"] = {k: PROVENANCE[k] for k in out if k in PROVENANCE}
    return out


def to_markdown(r: dict) -> str:
    """The readout as a person would read it. Order follows how a trial is actually asked
    about: what is it, who is running it, how big, what is being given, what would it show.
    """
    lines = [f"# {r.get('title') or r.get('nct_id')}", ""]
    ident = [r.get("nct_id"), r.get("phase"), r.get("status")]
    lines.append(" · ".join(str(x) for x in ident if x))
    if r.get("indication"):
        lines.append(f"\n**{r['indication']}**")
    lines.append("")
    lines.append(f"- **Design** — {r.get('design', 'not stated')}")
    n, kind = r.get("enrollment"), (r.get("enrollment_type") or "").lower()
    if n is not None:
        lines.append(f"- **Enrollment** — {n}{f' ({kind})' if kind else ''}")
    if r.get("sponsor"):
        lines.append(f"- **Sponsor** — {r['sponsor']} ({r.get('sponsor_type', 'unknown')})")
    if r.get("agents"):
        lines.append(f"- **Agents** — {', '.join(r['agents'])}")
    if r.get("modalities") is not None:
        lines.append(f"- **Modalities** — {', '.join(r['modalities']) or 'none (no drug under study)'}")
    if r.get("primary_endpoint_type"):
        lines.append(f"- **Primary endpoint** — {r['primary_endpoint_type']}")
    if r.get("est_readout"):
        lines.append(f"- **Est. readout** — {r['est_readout']}")
    if r.get("risk_flags"):
        lines.append(f"- **Risk flags** — {', '.join(r['risk_flags'])}")
    if r.get("investor_note"):
        lines += ["", "## Note", "", r["investor_note"]]
    return "\n".join(lines)
