"""Generate gold labels by distilling Claude (Sonnet) over the trial records.

Teacher -> student distillation: Sonnet reads each trial and emits a structured
TrialScout readout via forced tool-use (guaranteed schema-valid). The static
prefix (rules + few-shot examples + tool schema) is prompt-cached, so per-call
cost is dominated by the small per-trial record.

SAFETY (this spends money):
  * Hard cost cap (default $24, under the $25 authorization). The run aborts
    before making a call that could exceed it; in-flight overage is bounded.
  * 10-trial PILOT first: if <8/10 are schema-valid, abort before the bulk run.
  * Incremental + resumable: appends to data/gold/all.jsonl, skips already-labeled.

Run:  uv run python track-b-trialscout/train/make_gold.py --target 1500 --cap 24
"""
from __future__ import annotations
import argparse, json, threading, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
import anthropic

ROOT = Path(__file__).resolve().parents[1]            # track-b-trialscout/
load_dotenv(ROOT.parent / ".env")

RAW = ROOT / "data" / "raw" / "trials.jsonl"
GOLD = ROOT / "data" / "gold"
SPLITS = ROOT / "data" / "splits.json"   # frozen train/val/test assignment by NCT id
SCHEMA = json.loads((ROOT / "schema" / "trial_readout.schema.json").read_text())
FEWSHOT = [json.loads(l) for l in (ROOT / "schema" / "fewshot.jsonl").read_text().splitlines() if l.strip()]

MODEL = "claude-sonnet-5"

# Per-model pricing ($/1M tokens). The cap is the real guardrail, but it can only be
# honest if these track the model actually being called.
# Fee card. VERIFIED against platform.claude.com/docs/en/about-claude/pricing on 2026-08-10.
# These must be ACCURATE, not merely conservative: the cap aborts a run when the running
# estimate reaches it, so over-stating a price halts a paid job early and under-stating it
# overspends. Re-verify when a model launches or a promotion ends.
#
# NOTE: Sonnet 5's $2/$10 launched as introductory pricing "through 2026-08-31" and is now the
# PERMANENT price -- the scheduled rise to $3/$15 was cancelled. An earlier comment here said
# the opposite, which would have had us over-budget every future run.
#
# Tokeniser caveat: Claude 4.7-and-later models use a newer tokeniser emitting ~30% more tokens
# for the same text. Measured on 40 identical trials at identical prices, Sonnet 5 cost $0.49
# against Sonnet 4.6's $0.39 -- 26% more tokens, matching the documented figure. Sonnet 5's
# effective rate is therefore ~$2.52/$12.60: still ~16% cheaper than Sonnet 4.6, and newer.
PRICING = {
    "claude-fable-5":    {"in": 10.0, "out": 50.0},
    "claude-opus-5":     {"in":  5.0, "out": 25.0},
    "claude-sonnet-5":   {"in":  2.0, "out": 10.0},   # cheapest Sonnet AND the newest
    "claude-haiku-4-5":  {"in":  1.0, "out":  5.0},
}
# Sonnet 4.6 ($3/$15) is deliberately absent: previous-generation, and 50% DEARER than
# Sonnet 5. There is no job for which it is the right choice, so it is not priced here.
#
# There is no default price. An unknown model raises rather than being costed at some
# other model's rate -- `--cap` is a real spending guard, and a guard that silently
# invents a price is not a guard. Verified by scripts/check_fee_card.py.

# The current model family (Sonnet 5, Opus 5, Fable 5) removed the sampling parameters:
# `temperature` now returns 400. Depth is controlled by `output_config.effort` instead,
# and adaptive thinking is on by default — which shares the max_tokens budget with the
# response, so the old 700 can truncate a readout before it is emitted.
NO_SAMPLING_PARAMS = ("claude-sonnet-5", "claude-opus-5", "claude-fable-5", "claude-opus-4-8")

TOP_PHARMA = ("Pfizer, Roche, Genentech, Novartis, Merck, AstraZeneca, Bristol-Myers Squibb, "
              "Johnson & Johnson, Janssen, AbbVie, Sanofi, GSK, Amgen, Gilead, Takeda, "
              "Eli Lilly, Bayer, Boehringer Ingelheim, Daiichi Sankyo, Astellas")

def system_prompt() -> str:
    ex = "\n\n".join(
        f"TRIAL:\n{json.dumps(e['input'], ensure_ascii=False)}\nREADOUT:\n{json.dumps(e['output'], ensure_ascii=False)}"
        for e in FEWSHOT
    )
    return f"""You are TrialScout, an analyst that turns one oncology clinical-trial record into a structured, investor-relevant readout. Always respond by calling the `emit_readout` tool — never free text.

Rules:
- nct_id: copy verbatim from the record.
- phase: normalize (e.g. ["PHASE1","PHASE2"] -> "Phase 1/2").
- indication: concise tumor type + biomarker + line of therapy if stated (e.g. "EGFR T790M+ advanced NSCLC, 2L").
- intervention_class: decide this BEFORE modalities, from the interventions list. Read the intervention NAMES, not only their `type` — a drug named inside a PROCEDURE, DEVICE or OTHER intervention still counts (e.g. "reirradiation with concomitant cisplatin", "HIPEC: mitomycin C + cisplatin" are drug/biologic, and their agents get listed in modalities). If ANY intervention is a drug or biologic given as part of the ANTICANCER treatment strategy under study -> "drug/biologic". Otherwise classify what the trial actually tests: radiation technique only -> "external-beam radiation"; surgery or a procedure -> "procedure/surgery"; a device -> "device"; behavioral, dietary, psychological or supportive-care intervention -> "behavioral/supportive care"; a diagnostic test or an imaging tracer with no therapeutic agent -> "diagnostic/imaging"; genuinely none of these -> "other". A placebo alone is not a drug asset. Many oncology trials test a TECHNIQUE, not a drug — say so rather than forcing a modality onto them.
- modalities: an ARRAY of the DISTINCT modalities present. If intervention_class is not "drug/biologic", return []. Otherwise: (1) take EVERY drug/biologic given as anticancer therapy, INCLUDING standard-of-care backbone agents and combination partners — do NOT identify a "lead" or "primary" agent, and do NOT count agents; (2) exclude placebo/vehicle, diagnostic-only imaging tracers, and drugs given solely as supportive care (antiemetics, growth factors, premedication, bone-health bisphosphonates); (3) classify EACH remaining agent by the FIRST matching rule below; (4) return the DISTINCT values, sorted alphabetically. Several agents of the same class collapse to ONE entry: three small molecules -> ["targeted small molecule"], not three entries.
  Classify each agent by the FIRST rule it matches:
   1. living cells (CAR-T, TIL, NK, TCR-T, stem-cell product; INN -leucel/-cabtagene) -> "cell therapy"
   2. replication-competent virus given to lyse tumor -> "oncolytic virus"
   3. carries a radionuclide (Lu-177, I-131, Y-90, Ac-225, Ra-223, PSMA or dotatate ligands, radioimmunotherapy) -> "radiopharmaceutical"
   4. vector or nucleic acid delivering a gene (INN -vec, -gene) -> "gene therapy"
   5. given to raise an anti-tumor immune response as a vaccine -> "cancer vaccine"
   6. antibody carrying a cytotoxic payload (INN -vedotin/-deruxtecan/-govitecan/-mafodotin/-emtansine) -> "antibody-drug conjugate"
   7. antibody engaging two or more targets (bispecific, T-cell engager; INN -mig) -> "bispecific/multispecific antibody"
   8. unconjugated monospecific antibody (INN -mab/-tug/-bart/-ment) -> "monoclonal antibody"
   9. antisense, siRNA, mRNA or aptamer (INN -sen, -siran) -> "oligonucleotide/RNA therapeutic"
  10. hormonal or endocrine agent (aromatase inhibitor, SERD/SERM, anti-androgen, GnRH analogue, progestin, somatostatin analogue) -> "hormonal/endocrine therapy"
  11. classical cytotoxic chemotherapy (platinum, taxane, antimetabolite, anthracycline, alkylator, topoisomerase inhibitor, vinca alkaloid) -> "cytotoxic chemotherapy"
  12. other protein, peptide, fusion protein, enzyme, cytokine or interferon -> "other protein or peptide therapeutic"
  13. any other small molecule -> "targeted small molecule". This includes kinase inhibitors (-tinib), PARP (-parib), CDK (-ciclib), proteasome (-zomib), IMiDs and targeted degraders, AND ALSO agents that are easy to mis-file as biologics: photosensitizers (aminolevulinic acid, methylaminolevulinate, Levulan), topical immune agonists (imiquimod, ingenol mebutate), cytoprotectants (dexrazoxane, amifostine), retinoids, and albumin-bound formulations of a small molecule (nab-sirolimus, nab-paclitaxel — the carrier is not the drug). "other protein or peptide therapeutic" is for actual proteins and peptides; it is NOT a second "other" bucket.
  14. genuinely none of the above -> "other"
  GROUNDING RULE — every value you list must be traceable to a SPECIFIC agent NAMED in the record. Never add a modality because the trial "probably" also uses chemotherapy, because it is described as a combination, or because the tumor type usually implies a backbone. If no named agent supports it, do NOT list it. Two DIFFERENT monospecific antibodies given together are still just ["monoclonal antibody"] — "bispecific/multispecific" means ONE molecule that binds two or more targets, never two molecules given together.
  Worked cases: gemcitabine + capecitabine + sorafenib -> ["cytotoxic chemotherapy", "targeted small molecule"] (three agents, two modalities). Pembrolizumab + cyclophosphamide -> ["cytotoxic chemotherapy", "monoclonal antibody"]. Trastuzumab deruxtecan + carboplatin -> ["antibody-drug conjugate", "cytotoxic chemotherapy"]. Citalopram vs psychotherapy for depression in cancer patients -> intervention_class "behavioral/supportive care", modalities [] (no anticancer drug is under study). Stereotactic body radiotherapy alone -> "external-beam radiation", [].
- primary_endpoint_type: classify from the primary outcome measure(s). DLT/MTD/PK -> "safety/tolerability" or "pharmacokinetics".
- sponsor_type: lead_sponsor_class INDUSTRY -> "large pharma" if the name is a top-20 global pharma ({TOP_PHARMA}), else "biotech". OTHER/NETWORK -> "academic/cooperative group". NIH/FED/OTHER_GOV -> "government".
- est_readout: a MECHANICAL mapping of primary_completion_date, not a forecast of when results are published. Take the month from the date as given: 01-06 -> "H1 YYYY", 07-12 -> "H2 YYYY". Missing -> "unknown". Do NOT add a reporting lag, and do NOT reason about when data would realistically be presented — 2014-05-21 is "H1 2014" and 2011-06 is "H1 2011", full stop. The year is always the year in the date.
- risk_flags_judgement: ONLY these four, and only when the record supports them. PFS/ORR/pCR primary -> "surrogate endpoint"; DLT/MTD/PK primary -> "PK/dose-finding only"; a biomarker restricts eligibility -> "biomarker-restricted"; a single-arm design with no control at all -> "no comparator". Empty array if none apply. Do NOT report enrollment size, phase, masking, randomization, status or timeline — those are computed from the record by the pipeline, and you are measurably worse at them than an `if` statement.
- investor_note: <=2 sentences. State what the trial would prove and the key caveat. Factual, no hype, never invent data not in the record.

Worked examples:

{ex}"""

def tool_def() -> dict:
    """The teacher's tool: every field EXCEPT the ones the pipeline derives.

    A field marked `x-derived` is computed from the record (schema/derive.py). Offering it to
    the teacher would invite a second, worse opinion on arithmetic it cannot do reliably.
    """
    props = {k: v for k, v in SCHEMA["properties"].items() if not v.get("x-derived")}
    req = [r for r in SCHEMA["required"] if r in props]
    return {"name": SCHEMA["name"], "description": SCHEMA["description"],
            "input_schema": {"type": "object", "properties": props, "required": req}}

# Derived from the schema rather than hand-listed, so a field changing shape (scalar ->
# array, as `modality` -> `modalities` did) can't silently slip past the pilot gate.
_ASKED = {k: v for k, v in SCHEMA["properties"].items() if not v.get("x-derived")}
SCALAR_ENUMS = {k: set(v["enum"]) for k, v in _ASKED.items() if "enum" in v}
ARRAY_ENUMS = {k: set(v["items"]["enum"]) for k, v in _ASKED.items()
               if v.get("type") == "array" and "enum" in v.get("items", {})}
REQUIRED = [r for r in SCHEMA["required"] if r in _ASKED]

def valid(readout: dict) -> tuple[bool, str]:
    if not isinstance(readout, dict): return False, "not a dict"
    for k in REQUIRED:
        if k not in readout: return False, f"missing {k}"
    for k, allowed in SCALAR_ENUMS.items():
        if readout.get(k) not in allowed: return False, f"bad enum {k}={readout.get(k)!r}"
    for k, allowed in ARRAY_ENUMS.items():
        v = readout.get(k)
        if not isinstance(v, list): return False, f"{k} not list"
        for item in v:
            if item not in allowed: return False, f"bad {k} item {item!r}"
    # Cross-field invariant: the two new fields have to agree. A non-drug trial has no
    # modalities, and a drug trial has at least one. Catching this at label time is what
    # stops the teacher quietly reintroducing "pick something anyway" on technique trials.
    is_drug = readout.get("intervention_class") == "drug/biologic"
    if is_drug and not readout.get("modalities"):
        return False, "intervention_class is drug/biologic but modalities is empty"
    if not is_drug and readout.get("modalities"):
        return False, (f"intervention_class is {readout.get('intervention_class')!r} "
                       f"but modalities is {readout.get('modalities')!r}")
    if not str(readout.get("investor_note", "")).strip(): return False, "empty investor_note"
    return True, "ok"


def canonical(readout: dict) -> dict:
    """Sort + dedupe the set-valued fields so gold is stored in one canonical form."""
    out = dict(readout)
    for k in ARRAY_ENUMS:
        if isinstance(out.get(k), list):
            out[k] = sorted(set(out[k]))
    return out

client = anthropic.Anthropic()
SYS = [{"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}}]
TOOLS = [tool_def()]

def request_kwargs(model: str, effort: str = "medium") -> dict:
    """Per-family request shape. Kept in one place so the difference is visible."""
    if model in NO_SAMPLING_PARAMS:
        # No temperature knob exists on this family. Determinism is not something we can
        # request, so it is something we MEASURE -- see the self-consistency probe in
        # ADR-0018. The larger max_tokens stops adaptive thinking from crowding out the
        # tool call. Effort is `medium`, not `low`: at `low` the teacher put a June
        # primary-completion date in H2 about half the time, flunking its own
        # months-01-06-are-H1 rule. Cheap arithmetic still needs room to happen.
        return {"max_tokens": 2000, "output_config": {"effort": effort}}
    return {"max_tokens": 700, "temperature": 0}


def label_one(trial: dict, stop: threading.Event, model: str = MODEL, effort: str = "medium"):
    if stop.is_set(): return {"skipped": True}
    if model not in PRICING:
        raise SystemExit(
            f"no fee-card entry for {model!r} -- refusing to spend against a guessed price.\n"
            f"priced models: {', '.join(sorted(PRICING))}\n"
            f"add it to PRICING from docs/protocols/ANTHROPIC_MODEL_REFERENCE.md, "
            f"then run: uv run python scripts/check_fee_card.py"
        )
    price = PRICING[model]
    p_in, p_out = price["in"]/1e6, price["out"]/1e6
    p_cache_w, p_cache_r = p_in*1.25, p_in*0.10
    for attempt in range(4):
        try:
            r = client.messages.create(
                model=model,
                system=SYS, tools=TOOLS,
                tool_choice={"type": "tool", "name": "emit_readout"},
                messages=[{"role": "user", "content": f"TRIAL:\n{json.dumps(trial, ensure_ascii=False)}\nReturn the readout."}],
                **request_kwargs(model, effort),
            )
            u = r.usage
            cost = (p_in*u.input_tokens + p_out*u.output_tokens
                    + p_cache_w*(getattr(u, "cache_creation_input_tokens", 0) or 0)
                    + p_cache_r*(getattr(u, "cache_read_input_tokens", 0) or 0))
            readout = next((b.input for b in r.content if b.type == "tool_use"), None)
            return {"nct_id": trial["nct_id"], "readout": readout, "cost": cost}
        except Exception as e:
            if attempt == 3:
                return {"nct_id": trial["nct_id"], "error": f"{type(e).__name__}: {str(e)[:160]}", "cost": 0.0}
            time.sleep(2 ** attempt)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=1500)
    ap.add_argument("--cap", type=float, default=24.0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--effort", type=str, default="medium",
                    choices=["low", "medium", "high"],
                    help="output_config.effort for current-family teachers (ignored otherwise)")
    ap.add_argument("--model", type=str, default=MODEL,
                    help=f"teacher model id (default {MODEL}); pricing + request shape adapt to it")
    ap.add_argument("--input", type=str, default=str(RAW), help="raw trials JSONL to label")
    ap.add_argument("--out", type=str, default="all",
                    help="gold file stem to append to (gold/<stem>.jsonl). 'all' also does the 80/10/10 split.")
    args = ap.parse_args()
    GOLD.mkdir(parents=True, exist_ok=True)
    all_path = GOLD / f"{args.out}.jsonl"

    trials = [json.loads(l) for l in Path(args.input).read_text().splitlines() if l.strip()][:args.target]
    done = set()
    if all_path.exists():
        for l in all_path.read_text().splitlines():
            if l.strip(): done.add(json.loads(l)["nct_id"])
    todo = [t for t in trials if t["nct_id"] not in done]
    print(f"Trials: {len(trials)} | already labeled: {len(done)} | to label: {len(todo)} | cap ${args.cap}")

    cost = [0.0]; lock = threading.Lock(); stop = threading.Event()
    out_f = all_path.open("a")
    n_ok = n_bad = 0

    def record(res):
        nonlocal n_ok, n_bad
        if not res or res.get("skipped"): return
        with lock:
            cost[0] += res.get("cost", 0.0)
        if res.get("error"):
            n_bad += 1; return
        ok, why = valid(res["readout"])
        if ok:
            row = canonical({"nct_id": res["nct_id"], **res["readout"]})
            out_f.write(json.dumps(row) + "\n"); out_f.flush()
            n_ok += 1
        else:
            n_bad += 1

    # --- PILOT: first 10, gate on validity before bulk spend ---
    pilot = todo[:10]
    print("\n--- PILOT (10 trials) ---")
    pilot_ok = 0
    for t in pilot:
        res = label_one(t, stop, args.model, args.effort)
        if res and not res.get("error") and valid(res["readout"])[0]:
            pilot_ok += 1
        record(res)
    print(f"pilot valid: {pilot_ok}/10  | spent ${cost[0]:.3f}")
    if pilot_ok < 8:
        print("ABORT: pilot quality below 8/10 — not starting bulk run. Inspect data/gold/all.jsonl.")
        out_f.close(); return
    # show one pilot sample
    sample = json.loads(all_path.read_text().splitlines()[-1])
    print("sample readout:", json.dumps(sample, indent=2)[:700])

    # --- BULK ---
    rest = todo[10:]
    print(f"\n--- BULK ({len(rest)} trials, {args.workers} workers) ---")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(label_one, t, stop, args.model, args.effort) for t in rest]
        for i, fut in enumerate(as_completed(futs), 1):
            record(fut.result())
            if cost[0] >= args.cap and not stop.is_set():
                stop.set()
                print(f"COST CAP ${args.cap} reached — stopping new calls.")
            if i % 100 == 0:
                print(f"  {i}/{len(rest)}  ok={n_ok} bad={n_bad}  ${cost[0]:.2f}  ({time.time()-t0:.0f}s)", flush=True)
    out_f.close()

    rows = [json.loads(l) for l in all_path.read_text().splitlines() if l.strip()]
    n = len(rows)
    if args.out == "all":
        # --- SPLIT: read the frozen assignment, never re-derive it ---
        # This used to be `random.Random(42).shuffle(rows)` over all.jsonl. That looks
        # deterministic and isn't: all.jsonl is written in ThreadPoolExecutor completion
        # order, so every fresh teacher run reshuffled the corpus into a DIFFERENT test
        # set — silently, while the docs claimed a frozen 150. data/splits.json pins it.
        assignment = json.loads(SPLITS.read_text())
        by_id = {r["nct_id"]: r for r in rows}
        parts, missing = {}, {}
        for name in ("train", "val", "test"):
            ids = assignment[name]
            parts[name] = [by_id[i] for i in ids if i in by_id]
            missing[name] = len(ids) - len(parts[name])
            (GOLD / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in parts[name]))
        unassigned = [i for i in by_id if i not in set(sum((assignment[s] for s in ("train", "val", "test")), []))]
        split_line = (f"- total gold rows: **{n}** "
                      f"(train {len(parts['train'])}, val {len(parts['val'])}, test {len(parts['test'])})\n"
                      f"- split: frozen, from `data/splits.json` (not re-derived)\n")
        if any(missing.values()):
            split_line += f"- **unlabeled slots**: {missing} — these trials are in the split but got no valid label\n"
        if unassigned:
            split_line += f"- **{len(unassigned)} labeled trials are not in any split** — they were dropped\n"
    else:
        # Augment mode: NO split — these rows feed train only (format_for_mlx merges them),
        # so val/test stay frozen and the eval delta is comparable.
        split_line = f"- augment gold rows: **{n}** in gold/{args.out}.jsonl (train-only, no split)\n"

    report = (f"# Gold labeling run ({args.out})\n\n"
              f"- labeled this run: **{n_ok}** valid, {n_bad} failed\n"
              f"{split_line}"
              f"- spend: **${cost[0]:.2f}** (cap ${args.cap})\n"
              f"- teacher: {args.model}, forced tool-use, prompt-cached prefix\n")
    (GOLD / f"REPORT_{args.out}.md").write_text(report)
    print("\n" + report)

if __name__ == "__main__":
    main()
