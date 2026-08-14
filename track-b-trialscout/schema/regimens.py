"""Acronym resolution for trial interventions — regimens, drug shorthands, and procedures.

WHY THIS EXISTS. Reviewing a v3 readout, the first substantive complaint was that
``COPP/ABV`` had been reported as if it were a drug name. It is not: it is an alternating
seven-drug Hodgkin lymphoma regimen, and every one of those seven drugs is a different
answer to "what modality is this?". The registry writes the acronym and nothing else, so a
reader — human or model — sees a token with no pharmacology attached to it.

Three distinct problems hide behind "the name is an abbreviation", and conflating them is
how you get the v1 mistake back:

1. **Multi-drug regimens** (FOLFIRI, ABVD, R-CHOP). One token, several agents, and the
   ``modalities`` field is defined as the set over *all* agents. Unexpanded, the record
   under-reports — the same class of loss as the ingest truncation audited in ADR-0021.
2. **Single drugs under a shorthand** (ATRA, BCNU, T-DM1). One agent, just not spelled out.
   Cheap to resolve and occasionally load-bearing: T-DM1 is an antibody-drug conjugate,
   which is precisely the rare class the diagnostic set was built to measure.
3. **Procedures and delivery routes that are not drugs** (IMRT, SBRT, MRI, HAIC, TACE).
   These must NOT acquire a drug modality. Schema v1 forced a drug label onto every trial
   and thereby mislabelled the 16.6% of the corpus that tests no drug at all; an acronym
   table that quietly resolved ``IMRT`` into a therapeutic class would reintroduce that
   error through a side door. Hence ``kind``, which is the point of this module as much as
   ``expansion`` is.

SCOPE AND HONESTY. This is a curated table, not a knowledge base. It covers the regimens
that recur in oncology plus those observed in this corpus; it will miss others, and a miss
is a no-op — ``resolve`` returns ``None`` and the caller falls back to the raw name. It
never guesses from the shape of a string. Entries are standard-of-care regimens whose
composition is stable and well documented; company codes (``HLX10``, ``OTS167PO``) are
deliberately absent, because resolving those needs a live drug database, not a dictionary.
"""
from __future__ import annotations

import re

# kind:
#   "regimen"   -- multi-agent; expansion is the constituent list, and modalities is the
#                  set over all of them
#   "drug"      -- one agent under a shorthand
#   "biologic"  -- one biological agent; called out because the drug/biologic split drives
#                  intervention_class
#   "procedure" -- NOT a drug. Radiotherapy, imaging, surgery. Expansion is a plain-English
#                  name for the reader; it must never become a drug modality.
#   "route"     -- a delivery technique that carries cytotoxics (HAIC, TACE, HIPEC). The
#                  drug is real but the acronym names the plumbing, so the specific agent
#                  usually has to come from elsewhere in the record.

REGIMENS: dict[str, dict] = {
    # --- multi-drug cytotoxic regimens -------------------------------------------------
    "FOLFOX":    {"kind": "regimen", "expansion": ["folinic acid", "fluorouracil", "oxaliplatin"]},
    "FOLFIRI":   {"kind": "regimen", "expansion": ["folinic acid", "fluorouracil", "irinotecan"]},
    "FOLFOXIRI": {"kind": "regimen", "expansion": ["folinic acid", "fluorouracil", "oxaliplatin", "irinotecan"]},
    "FOLFIRINOX": {"kind": "regimen", "expansion": ["folinic acid", "fluorouracil", "irinotecan", "oxaliplatin"]},
    "XELOX":     {"kind": "regimen", "expansion": ["capecitabine", "oxaliplatin"]},
    "CAPOX":     {"kind": "regimen", "expansion": ["capecitabine", "oxaliplatin"]},
    "GEMOX":     {"kind": "regimen", "expansion": ["gemcitabine", "oxaliplatin"]},
    "COPP":      {"kind": "regimen", "expansion": ["cyclophosphamide", "vincristine", "procarbazine", "prednisone"]},
    "ABV":       {"kind": "regimen", "expansion": ["doxorubicin", "bleomycin", "vinblastine"]},
    "COPP/ABV":  {"kind": "regimen", "expansion": ["cyclophosphamide", "vincristine", "procarbazine",
                                                   "prednisone", "doxorubicin", "bleomycin", "vinblastine"],
                  "note": "alternating COPP and ABV cycles"},
    "ABVD":      {"kind": "regimen", "expansion": ["doxorubicin", "bleomycin", "vinblastine", "dacarbazine"]},
    "MOPP":      {"kind": "regimen", "expansion": ["mechlorethamine", "vincristine", "procarbazine", "prednisone"]},
    "BEACOPP":   {"kind": "regimen", "expansion": ["bleomycin", "etoposide", "doxorubicin", "cyclophosphamide",
                                                   "vincristine", "procarbazine", "prednisone"]},
    "CHOP":      {"kind": "regimen", "expansion": ["cyclophosphamide", "doxorubicin", "vincristine", "prednisone"]},
    "R-CHOP":    {"kind": "regimen", "expansion": ["rituximab", "cyclophosphamide", "doxorubicin",
                                                   "vincristine", "prednisone"],
                  "note": "CHOP plus a monoclonal antibody -- modalities must include both"},
    "EPOCH":     {"kind": "regimen", "expansion": ["etoposide", "prednisone", "vincristine",
                                                   "cyclophosphamide", "doxorubicin"]},
    "ICE":       {"kind": "regimen", "expansion": ["ifosfamide", "carboplatin", "etoposide"]},
    "DHAP":      {"kind": "regimen", "expansion": ["dexamethasone", "cytarabine", "cisplatin"]},
    "CMF":       {"kind": "regimen", "expansion": ["cyclophosphamide", "methotrexate", "fluorouracil"]},
    "CAV":       {"kind": "regimen", "expansion": ["cyclophosphamide", "doxorubicin", "vincristine"]},
    "VAC":       {"kind": "regimen", "expansion": ["vincristine", "dactinomycin", "cyclophosphamide"]},
    "BEP":       {"kind": "regimen", "expansion": ["bleomycin", "etoposide", "cisplatin"]},
    "MVAC":      {"kind": "regimen", "expansion": ["methotrexate", "vinblastine", "doxorubicin", "cisplatin"]},
    "HYPERCVAD": {"kind": "regimen", "expansion": ["cyclophosphamide", "vincristine", "doxorubicin",
                                                   "dexamethasone"]},

    # --- single drugs written as shorthand ---------------------------------------------
    "ATRA":   {"kind": "drug", "expansion": ["tretinoin"], "note": "all-trans retinoic acid"},
    "ARA-C":  {"kind": "drug", "expansion": ["cytarabine"]},
    "ARAC":   {"kind": "drug", "expansion": ["cytarabine"]},
    "BCNU":   {"kind": "drug", "expansion": ["carmustine"]},
    "CCNU":   {"kind": "drug", "expansion": ["lomustine"]},
    "TMZ":    {"kind": "drug", "expansion": ["temozolomide"]},
    "5-FU":   {"kind": "drug", "expansion": ["fluorouracil"]},
    "6-MP":   {"kind": "drug", "expansion": ["mercaptopurine"]},
    "MTX":    {"kind": "drug", "expansion": ["methotrexate"]},
    "ATO":    {"kind": "drug", "expansion": ["arsenic trioxide"]},
    "T-DM1":  {"kind": "drug", "expansion": ["trastuzumab emtansine"],
               "note": "antibody-drug conjugate -- a rare class the diagnostic set measures"},

    # --- biologics ----------------------------------------------------------------------
    "G-CSF":     {"kind": "biologic", "expansion": ["filgrastim"], "note": "supportive care, not antitumour"},
    "PEG-RHG-CSF": {"kind": "biologic", "expansion": ["pegfilgrastim"], "note": "supportive care"},
    "GM-CSF":    {"kind": "biologic", "expansion": ["sargramostim"], "note": "supportive care"},
    "IL-2":      {"kind": "biologic", "expansion": ["aldesleukin"]},
    "ATG":       {"kind": "biologic", "expansion": ["anti-thymocyte globulin"],
                  "note": "POLYCLONAL antibody preparation -- not a monoclonal antibody"},
    "BCG":       {"kind": "biologic", "expansion": ["Bacillus Calmette-Guerin"], "note": "live attenuated; immunotherapy"},
    "TIL":       {"kind": "biologic", "expansion": ["tumour-infiltrating lymphocytes"], "note": "cell therapy"},

    # --- procedures: NOT drugs ----------------------------------------------------------
    "RT":    {"kind": "procedure", "expansion": ["radiotherapy"]},
    "EBRT":  {"kind": "procedure", "expansion": ["external beam radiotherapy"]},
    "IMRT":  {"kind": "procedure", "expansion": ["intensity-modulated radiotherapy"]},
    "SBRT":  {"kind": "procedure", "expansion": ["stereotactic body radiotherapy"]},
    "SRS":   {"kind": "procedure", "expansion": ["stereotactic radiosurgery"]},
    "IORT":  {"kind": "procedure", "expansion": ["intraoperative radiotherapy"]},
    "WBRT":  {"kind": "procedure", "expansion": ["whole-brain radiotherapy"]},
    "MRI":   {"kind": "procedure", "expansion": ["magnetic resonance imaging"]},
    "CT":    {"kind": "procedure", "expansion": ["computed tomography"]},
    "PET":   {"kind": "procedure", "expansion": ["positron emission tomography"]},
    "SPECT": {"kind": "procedure", "expansion": ["single-photon emission computed tomography"]},
    "EUS":   {"kind": "procedure", "expansion": ["endoscopic ultrasound"]},
    "HSCT":  {"kind": "procedure", "expansion": ["haematopoietic stem cell transplant"]},
    "ASCT":  {"kind": "procedure", "expansion": ["autologous stem cell transplant"]},
    "ALLOSCT": {"kind": "procedure", "expansion": ["allogeneic stem cell transplant"]},

    # --- delivery routes carrying cytotoxics --------------------------------------------
    "HAIC":  {"kind": "route", "expansion": ["hepatic arterial infusion chemotherapy"],
              "note": "route, not an agent -- the specific drug is elsewhere in the record"},
    "TACE":  {"kind": "route", "expansion": ["transarterial chemoembolisation"], "note": "route, not an agent"},
    "HIPEC": {"kind": "route", "expansion": ["hyperthermic intraperitoneal chemotherapy"], "note": "route, not an agent"},
    "PIPAC": {"kind": "route", "expansion": ["pressurised intraperitoneal aerosol chemotherapy"],
              "note": "route, not an agent"},
}

#: Kinds that must never contribute a drug modality.
NON_DRUG_KINDS = frozenset({"procedure", "route"})

#: Brand and legacy names -> generic, for the agents most often written both ways in this
#: corpus. Needed because CT.gov's ``otherNames`` mixes true synonyms with regimen
#: constituents: NCT00592111 lists "Adriamycin" where the resolved regimen says
#: "doxorubicin", and without this the same drug is counted twice under two spellings.
#: Deliberately small and one-directional -- a general synonym database is a drug registry,
#: not a dictionary, and guessing is worse than leaving a name unmapped.
SYNONYMS: dict[str, str] = {
    "ADRIAMYCIN": "doxorubicin",
    "ONCOVIN": "vincristine",
    "CYTOXAN": "cyclophosphamide",
    "CYTOSINE ARABINOSIDE": "cytarabine",
    "VP-16": "etoposide",
    "VELBAN": "vinblastine",
    "TAXOL": "paclitaxel",
    "TAXOTERE": "docetaxel",
    "PLATINOL": "cisplatin",
    "PARAPLATIN": "carboplatin",
    "5-FLUOROURACIL": "fluorouracil",
    "LEUCOVORIN": "folinic acid",
    "FILGRASTIM": "filgrastim",
    "G-CSF (FILGRASTIM)": "filgrastim",
    # Brands that turn up in otherNames beside their own generic, producing a duplicate
    # agent for one drug (NCT00216086 listed Camptosar and Irinotecan as two agents).
    "CAMPTOSAR": "irinotecan",
    "XELODA": "capecitabine",
    "GEMZAR": "gemcitabine",
    "ELOXATIN": "oxaliplatin",
    "AVASTIN": "bevacizumab",
    "HERCEPTIN": "trastuzumab",
    "RITUXAN": "rituximab",
    "ERBITUX": "cetuximab",
    "ALIMTA": "pemetrexed",
    "NAVELBINE": "vinorelbine",
    "TEMODAR": "temozolomide",
}


def canonical_agent(name: str) -> str:
    """Map a brand or legacy drug name to its generic, unchanged when unknown."""
    n = re.sub(r"\s+", " ", (name or "").strip())
    return SYNONYMS.get(n.upper(), n)

_STRIP = re.compile(r"^(?:drug|biological|procedure|radiation|device|other)\s*:\s*", re.I)


def _key(name: str) -> str:
    """Normalise an intervention name to a lookup key."""
    n = _STRIP.sub("", (name or "").strip())
    n = re.sub(r"\s*\(.*?\)\s*", " ", n)          # drop parentheticals
    return re.sub(r"\s+", " ", n).strip().upper()


def resolve(name: str) -> dict | None:
    """Look up one intervention name. Returns None when unknown -- never a guess.

    Handles the ``A/B`` and ``A+B`` composites the registry uses for alternating or
    concurrent regimens by resolving each side and merging, so ``FOLFOX+bevacizumab``
    contributes the FOLFOX agents *and* leaves the unknown half visible to the caller.
    """
    k = _key(name)
    if not k:
        return None
    if k in REGIMENS:
        return {"acronym": k, **REGIMENS[k]}

    # Split the ORIGINAL text, not the uppercased key: the unresolved halves are returned
    # to the caller and become agent names, so they must keep the registry's own casing.
    raw_parts = [p.strip() for p in re.split(r"\s*[/+]\s*", _STRIP.sub("", (name or "").strip())) if p.strip()]
    parts = [_key(p) for p in raw_parts]
    if len(parts) > 1:
        hits = [(p, REGIMENS[p]) for p in parts if p in REGIMENS]
        if hits:
            expansion: list[str] = []
            for _, e in hits:
                expansion += [d for d in e["expansion"] if d not in expansion]
            kinds = {e["kind"] for _, e in hits}
            unresolved = [raw for raw, up in zip(raw_parts, parts) if up not in REGIMENS]
            out = {
                "acronym": k,
                # A composite is a regimen once more than one agent is involved; if every
                # resolved part is a procedure it stays a procedure and earns no modality.
                "kind": "regimen" if len(expansion) > 1 and kinds - NON_DRUG_KINDS else next(iter(kinds)),
                "expansion": expansion,
                "partial": bool(unresolved),
            }
            if unresolved:
                out["unresolved"] = unresolved
            return out
    return None


def annotate(interventions: list[dict]) -> list[dict]:
    """Attach resolutions to a CT.gov intervention list, leaving unknowns untouched."""
    out = []
    for iv in interventions or []:
        row = dict(iv)
        hit = resolve(iv.get("name", ""))
        if hit:
            row["resolved"] = hit
        out.append(row)
    return out
