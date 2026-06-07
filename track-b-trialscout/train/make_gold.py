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
import argparse, json, threading, time, random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
import anthropic

ROOT = Path(__file__).resolve().parents[1]            # track-b-trialscout/
load_dotenv(ROOT.parent / ".env")

RAW = ROOT / "data" / "raw" / "trials.jsonl"
GOLD = ROOT / "data" / "gold"
SCHEMA = json.loads((ROOT / "schema" / "trial_readout.schema.json").read_text())
FEWSHOT = [json.loads(l) for l in (ROOT / "schema" / "fewshot.jsonl").read_text().splitlines() if l.strip()]

MODEL = "claude-sonnet-4-6"
# Sonnet pricing ($/token), approximate — the cap is the real guardrail.
P_IN, P_OUT, P_CACHE_W, P_CACHE_R = 3.0/1e6, 15.0/1e6, 3.75/1e6, 0.30/1e6

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
- modality: the single best-fit modality of the PRIMARY investigational agent. Decide in order: (1) one lead investigational agent -> use ITS modality (a chemo/standard-of-care backbone or an added combination partner does NOT make it "combination"); (2) "combination" ONLY when two+ investigational agents of DIFFERENT modality classes are co-equal with no single lead (e.g. an experimental anti-PD-1 mAb + an experimental TKI); (3) two+ agents of the SAME class (e.g. two small molecules) -> that class, not "combination"; (4) always prefer the SPECIFIC class (antibody-drug conjugate, bispecific, cell therapy, gene therapy, cancer vaccine, oncolytic virus) over "combination" or "other" when the lead agent is one of those.
- primary_endpoint_type: classify from the primary outcome measure(s). DLT/MTD/PK -> "safety/tolerability" or "pharmacokinetics".
- sponsor_type: lead_sponsor_class INDUSTRY -> "large pharma" if the name is a top-20 global pharma ({TOP_PHARMA}), else "biotech". OTHER/NETWORK -> "academic/cooperative group". NIH/FED/OTHER_GOV -> "government".
- est_readout: from primary_completion_date (YYYY-MM): months 01-06 -> "H1 YYYY", 07-12 -> "H2 YYYY". Missing -> "unknown".
- risk_flags: include ONLY those supported by the record. Map: 1 arm / non-randomized -> "single-arm"/"non-randomized"; enrollment <50 -> "small enrollment (<50)"; phase 1 or early -> "early-phase"; DLT/MTD/PK primary -> "PK/dose-finding only"; PFS/ORR/pCR primary -> "surrogate endpoint"; terminated/withdrawn/suspended status -> "status: terminated/withdrawn/suspended"; biomarker in indication -> "biomarker-restricted". Empty array if none apply.
- investor_note: <=2 sentences. State what the trial would prove and the key caveat. Factual, no hype, never invent data not in the record.

Worked examples:

{ex}"""

def tool_def() -> dict:
    return {"name": SCHEMA["name"], "description": SCHEMA["description"],
            "input_schema": {"type": "object", "properties": SCHEMA["properties"], "required": SCHEMA["required"]}}

ENUMS = {k: set(v["enum"]) for k, v in SCHEMA["properties"].items() if "enum" in v}
RISK_ENUM = set(SCHEMA["properties"]["risk_flags"]["items"]["enum"])
REQUIRED = SCHEMA["required"]

def valid(readout: dict) -> tuple[bool, str]:
    if not isinstance(readout, dict): return False, "not a dict"
    for k in REQUIRED:
        if k not in readout: return False, f"missing {k}"
    for k, allowed in ENUMS.items():
        if readout.get(k) not in allowed: return False, f"bad enum {k}={readout.get(k)!r}"
    if not isinstance(readout.get("risk_flags"), list): return False, "risk_flags not list"
    for r in readout["risk_flags"]:
        if r not in RISK_ENUM: return False, f"bad risk_flag {r!r}"
    if not str(readout.get("investor_note", "")).strip(): return False, "empty investor_note"
    return True, "ok"

client = anthropic.Anthropic()
SYS = [{"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}}]
TOOLS = [tool_def()]

def label_one(trial: dict, stop: threading.Event):
    if stop.is_set(): return {"skipped": True}
    for attempt in range(4):
        try:
            r = client.messages.create(
                model=MODEL, max_tokens=700, temperature=0,
                system=SYS, tools=TOOLS,
                tool_choice={"type": "tool", "name": "emit_readout"},
                messages=[{"role": "user", "content": f"TRIAL:\n{json.dumps(trial, ensure_ascii=False)}\nReturn the readout."}],
            )
            u = r.usage
            cost = (P_IN*u.input_tokens + P_OUT*u.output_tokens
                    + P_CACHE_W*(getattr(u, "cache_creation_input_tokens", 0) or 0)
                    + P_CACHE_R*(getattr(u, "cache_read_input_tokens", 0) or 0))
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
            out_f.write(json.dumps({"nct_id": res["nct_id"], **res["readout"]}) + "\n"); out_f.flush()
            n_ok += 1
        else:
            n_bad += 1

    # --- PILOT: first 10, gate on validity before bulk spend ---
    pilot = todo[:10]
    print("\n--- PILOT (10 trials) ---")
    pilot_ok = 0
    for t in pilot:
        res = label_one(t, stop)
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
        futs = [ex.submit(label_one, t, stop) for t in rest]
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
        # --- SPLIT 80/10/10 (deterministic) — main run only ---
        random.Random(42).shuffle(rows)
        a, b = int(0.8*n), int(0.9*n)
        for name, part in [("train", rows[:a]), ("val", rows[a:b]), ("test", rows[b:])]:
            (GOLD / f"{name}.jsonl").write_text("".join(json.dumps(r)+"\n" for r in part))
        split_line = f"- total gold rows: **{n}** (train {a}, val {b-a}, test {n-b})\n"
    else:
        # Augment mode: NO split — these rows feed train only (format_for_mlx merges them),
        # so val/test stay frozen and the eval delta is comparable.
        split_line = f"- augment gold rows: **{n}** in gold/{args.out}.jsonl (train-only, no split)\n"

    report = (f"# Gold labeling run ({args.out})\n\n"
              f"- labeled this run: **{n_ok}** valid, {n_bad} failed\n"
              f"{split_line}"
              f"- spend: **${cost[0]:.2f}** (cap ${args.cap})\n"
              f"- teacher: {MODEL}, forced tool-use, prompt-cached prefix\n")
    (GOLD / f"REPORT_{args.out}.md").write_text(report)
    print("\n" + report)

if __name__ == "__main__":
    main()
