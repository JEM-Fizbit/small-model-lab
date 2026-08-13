"""A deterministic readout, written in `if` statements, as the comparator the project lacked.

Until now the only floor was the majority-class baseline, which answers "is this better than
guessing?". That is the wrong question. The right one is **"is this better than an afternoon of
rules?"** — and for several fields the answer turned out to be no.

Nothing here uses a model. Every value is a lookup, a date format, a name match, or a keyword
scan over text already in the record. Where a field genuinely cannot be derived (`indication`,
`modalities`, `investor_note`) the rules return their weakest honest answer rather than guessing,
so the gap those fields show is the real value of inference.

Run:  uv run python track-b-trialscout/eval/rules_baseline.py --gold holdout_natural
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "schema"))
from harness import score  # noqa: E402  the same scorer every other arm uses
from derive import derive_risk_flags  # noqa: E402  the seven arithmetic flags

PHASES = {("EARLY_PHASE1",): "Early Phase 1", ("PHASE1",): "Phase 1", ("PHASE1", "PHASE2"): "Phase 1/2",
          ("PHASE2",): "Phase 2", ("PHASE2", "PHASE3"): "Phase 2/3", ("PHASE3",): "Phase 3",
          ("PHASE4",): "Phase 4"}

TOP_PHARMA = ("pfizer roche genentech novartis merck astrazeneca bristol johnson janssen abbvie sanofi "
              "gsk glaxo amgen gilead takeda lilly bayer boehringer daiichi astellas").split()

DRUGISH = {"DRUG", "BIOLOGICAL", "GENETIC", "COMBINATION_PRODUCT"}

# Ordered: first match wins, so the specific patterns must precede the general ones.
ENDPOINTS = [
    (r"\boverall survival\b|(^|\W)OS(\W|$)", "overall survival (OS)"),
    (r"progression[- ]free|(^|\W)PFS(\W|$)", "progression-free survival (PFS)"),
    (r"objective response|overall response|(^|\W)ORR(\W|$)|\bresponse rate\b", "objective response rate (ORR)"),
    (r"disease[- ]free|(^|\W)DFS(\W|$)|event[- ]free", "disease-free survival (DFS)"),
    (r"pathologic(al)? complete|(^|\W)pCR(\W|$)", "pathologic complete response (pCR)"),
    (r"pharmacokinet|(^|\W)AUC(\W|$)|(^|\W)Cmax|plasma concentration", "pharmacokinetics"),
    (r"dose[- ]limiting|maximum tolerated|(^|\W)MTD(\W|$)|(^|\W)DLT|adverse event|toxicit|safety|tolerab",
     "safety/tolerability"),
]

# INN stems and class words. Reaches ~21% of unique agent names -- deliberately NOT extended into a
# drug dictionary, because the point is to show where a lookup stops and knowledge begins.
MODALITY_PATTERNS = [
    (r"leucel\b|cabtagene|\bCAR[- ]?T\b|chimeric antigen|tumor infiltrating", "cell therapy"),
    (r"oncolytic", "oncolytic virus"),
    (r"177lu|lu-?177|225ac|ac-?225|y-?90|i-?131|131i|psma|dotatate|radioimmunother", "radiopharmaceutical"),
    (r"\bvec\b|gene therapy|aav\b", "gene therapy"),
    (r"vaccine", "cancer vaccine"),
    (r"vedotin|deruxtecan|govitecan|mafodotin|emtansine|tirumotecan|antibody[- ]drug conjugate",
     "antibody-drug conjugate"),
    (r"bispecific|t-?cell engager|\w+mig\b", "bispecific/multispecific antibody"),
    (r"\w+mab\b|\w+tug\b|\w+bart\b", "monoclonal antibody"),
    (r"antisense|sirna|\w+siran\b|oligonucleotide|aptamer", "oligonucleotide/RNA therapeutic"),
    (r"anastrozole|letrozole|exemestane|tamoxifen|fulvestrant|abiraterone|enzalutamide|goserelin|"
     r"leuprolide|degarelix|bicalutamide|octreotide|lanreotide", "hormonal/endocrine therapy"),
    (r"cisplatin|carboplatin|oxaliplatin|paclitaxel|docetaxel|gemcitabine|fluorouracil|capecitabine|"
     r"doxorubicin|cyclophosphamide|etoposide|pemetrexed|irinotecan|cytarabine|methotrexate|vincristine|"
     r"vinblastine|bleomycin|temozolomide|bendamustine|melphalan", "cytotoxic chemotherapy"),
    (r"interferon|interleukin|aldesleukin|asparaginase|aflibercept|\w+cept\b", "other protein or peptide therapeutic"),
    (r"\w+tinib\b|\w+parib\b|\w+ciclib\b|\w+zomib\b|\w+lisib\b|\w+rafenib\b", "targeted small molecule"),
]


def rules_readout(rec: dict) -> dict:
    """A complete readout with no model involved."""
    types = {i.get("type") for i in (rec.get("interventions") or [])}
    names = " ; ".join((i.get("name") or "") + " " + (i.get("description") or "")
                       for i in (rec.get("interventions") or []))

    if types & DRUGISH:
        klass = "drug/biologic"
    elif "RADIATION" in types:
        klass = "external-beam radiation"
    elif "PROCEDURE" in types:
        klass = "procedure/surgery"
    elif "DEVICE" in types:
        klass = "device"
    elif "DIAGNOSTIC_TEST" in types:
        klass = "diagnostic/imaging"
    elif types & {"BEHAVIORAL", "DIETARY_SUPPLEMENT", "OTHER"}:
        klass = "behavioral/supportive care"
    else:
        klass = "other"

    modalities = []
    if klass == "drug/biologic":
        for pat, val in MODALITY_PATTERNS:
            if re.search(pat, names, re.I) and val not in modalities:
                modalities.append(val)
        if not modalities:
            modalities = ["other"]   # a name we cannot resolve -- exactly where knowledge is needed

    outcomes = " ; ".join((o.get("measure") or "") for o in (rec.get("primary_outcomes") or []))
    endpoint = next((v for p, v in ENDPOINTS if re.search(p, outcomes, re.I)), "other")

    cls = (rec.get("lead_sponsor_class") or "").upper()
    nm = (rec.get("lead_sponsor") or "").lower()
    if cls == "INDUSTRY":
        sponsor = "large pharma" if any(t in nm for t in TOP_PHARMA) else "biotech"
    elif cls in ("NIH", "FED", "OTHER_GOV"):
        sponsor = "government"
    elif cls in ("OTHER", "NETWORK", "INDIV"):
        sponsor = "academic/cooperative group"
    else:
        sponsor = "other"

    d = str(rec.get("primary_completion_date") or "")
    readout = ("H1 " if len(d) >= 7 and int(d[5:7]) <= 6 else "H2 ") + d[:4] if len(d) >= 7 else "unknown"

    # Three of the four "judgement" flags follow from fields already decided above. Only
    # biomarker-restricted needs the eligibility text read, which rules cannot do.
    judged = []
    if endpoint in ("progression-free survival (PFS)", "objective response rate (ORR)",
                    "pathologic complete response (pCR)"):
        judged.append("surrogate endpoint")
    if endpoint in ("safety/tolerability", "pharmacokinetics"):
        judged.append("PK/dose-finding only")
    if str(rec.get("allocation") or "").upper() in ("NA", "NON_RANDOMIZED") or rec.get("n_arms") == 1:
        judged.append("no comparator")

    return {
        "nct_id": rec.get("nct_id"),
        "phase": PHASES.get(tuple(rec.get("phases") or [])),
        "indication": ", ".join(rec.get("conditions") or []),   # verbatim, not the compressed form
        "intervention_class": klass,
        "modalities": sorted(modalities),
        "primary_endpoint_type": endpoint,
        "sponsor_type": sponsor,
        "est_readout": readout,
        "risk_flags_judgement": sorted(judged),
        "risk_flags": derive_risk_flags(rec),
        "investor_note": "",                                     # rules cannot write one
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="holdout_natural")
    ap.add_argument("--label", default="rules")
    args = ap.parse_args()
    gold = [json.loads(x) for x in (ROOT / "data" / "gold" / f"{args.gold}.jsonl").read_text().splitlines() if x.strip()]
    raw = {}
    for f in sorted((ROOT / "data" / "raw").glob("*.jsonl")):
        if f.name == "studies_full.jsonl":
            continue
        for line in f.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if "nct_id" in r:
                    raw[r["nct_id"]] = r
    preds = {g["nct_id"]: rules_readout(raw[g["nct_id"]]) for g in gold if g["nct_id"] in raw}
    res = score(gold, preds)
    res["_condition"] = ("deterministic rules only -- no model. `indication` is the verbatim condition "
                         "list and `investor_note` is empty, so those fields are not scored here.")
    (ROOT / "eval" / f"score_{args.label}.json").write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if not k.startswith("_")}, indent=2))
    print(f"\noverall (rules) = {res['_overall_structured']}  n={res['_n']}")


if __name__ == "__main__":
    main()
