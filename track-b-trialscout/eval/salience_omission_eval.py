"""Salience-capture eval: does a generic LLM's free-form summary VOLUNTEER what matters?

Round 2 of the schema-vs-free-form study (see SALIENCE_EXPERIMENT_NOTES.md). Round 1
measured information *recoverability* (a strong judge mined fields from prose, and could
classify name-dropped entities) — which flatters free-form and does NOT test the claim that
a generic model self-selects the WRONG salient features.

This run measures *salience capture* instead, on the SAME base-model outputs (reused verbatim
from preds_schema_vs_freeform.jsonl — only the scoring changes):

  * The judge sees ONLY the writeup (never the trial record, never the gold answer).
  * It credits a field ONLY if the writeup explicitly states it or an unambiguous paraphrase.
  * NO rescue: a named sponsor/drug whose TYPE/CLASS is not stated -> NOT_STATED (omission),
    not a classification from outside knowledge.
  * Every field resolves to stated-correct / stated-wrong / not-stated.

Both arms go through the same extractor for symmetry, then score with the same harness.score
(so the headline overall stays comparable to Round 1's 0.711 / 0.755).

Run:  uv run python track-b-trialscout/eval/salience_omission_eval.py            # all 150 (reused gens)
      uv run python track-b-trialscout/eval/salience_omission_eval.py --limit 8  # smoke test
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
import anthropic

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT.parent / ".env")
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "schema"))
from harness import score                    # noqa: E402  same metrics as Round 1 / the baseline
from normalize import snap_to_enum           # noqa: E402  same enum-snap as deployed

GENS_DEFAULT = ROOT / "eval" / "preds_schema_vs_freeform.jsonl"   # reused base-model outputs
GOLD_TEST = [json.loads(l) for l in (ROOT / "data" / "gold" / "test.jsonl").read_text().splitlines() if l.strip()]
SCHEMA = json.loads((ROOT / "schema" / "trial_readout.schema.json").read_text())
JUDGE_MODEL = "claude-sonnet-5"   # was sonnet-4-6: older AND 50% dearer

SENTINEL = "NOT_STATED"
SCALARS = ["phase", "intervention_class", "primary_endpoint_type", "sponsor_type", "est_readout"]
# Set-valued fields need an "addressed?" flag of their own: for these, [] is a real answer
# ("no drug asset", "no risks raised") and must not be confused with never mentioning them.
SET_FIELDS = ["modalities", "risk_flags"]


JUDGE_SYSTEM = f"""You normalize a model's output about one oncology clinical trial into a fixed schema. The output may be JSON or prose. Your job is to capture WHAT THE OUTPUT ITSELF CONVEYS — never to supply the correct answer from your own knowledge.

You do NOT have the trial record and you do NOT know the right answers. You must NOT use outside knowledge to fill, refine, or look anything up.

For each field, decide: did the output ADDRESS this field?
- A JSON field that is present with a value, OR prose that explicitly states/paraphrases the value, counts as ADDRESSED -> normalize it to the enum (see below).
- If the output does NOT address the field at all (no JSON key for it AND no mention in prose), output the exact string "{SENTINEL}".

Normalization of an ADDRESSED value (this is reformatting, NOT outside knowledge — always do it):
- map synonyms/casing to the enum spelling ("Vaccine" -> "cancer vaccine"; "Overall Response Rate"/"ORR" -> "objective response rate (ORR)"; "PHASE1-PHASE2" -> "Phase 1/2").
- est_readout: a date "YYYY-MM[-DD]" or a stated month/half -> "H1 YYYY" (month 01-06) or "H2 YYYY" (07-12). If the value is just a bare year with no month/half, or the field is not addressed, output "{SENTINEL}".
- if an addressed value is genuinely ambiguous within the enum (e.g. sponsor_type "INDUSTRY" could be biotech OR large pharma and the output does not say which), pick the closest single enum the TEXT itself supports; if none fits, "other". Do NOT resolve it by looking up the named entity.

Hard rule on entities: naming a sponsor ("Enterome") or drug ("pembrolizumab") is NOT, by itself, stating its TYPE or MODALITY CLASS. In PROSE, if only the name appears and the type/class is never characterized, that field is "{SENTINEL}" (or discussed_modalities=false). This is the whole point of the measurement: it asks whether the output SURFACED the class, not whether you can recognize the drug. (In JSON, a populated intervention_class or modalities field IS addressed — normalize it.)

Enums:
- phase: {SCHEMA['properties']['phase']['enum']}
- intervention_class: {SCHEMA['properties']['intervention_class']['enum']}
- modalities items: {SCHEMA['properties']['modalities']['items']['enum']}
- primary_endpoint_type: {SCHEMA['properties']['primary_endpoint_type']['enum']}
- sponsor_type: {SCHEMA['properties']['sponsor_type']['enum']}
- risk_flags items: {SCHEMA['properties']['risk_flags']['items']['enum']}
risk_flags: list the risks/limitations the output raises, normalized to that vocabulary. discussed_risks=false + empty array only if the output does not address risks/limitations at all.
modalities: list the distinct therapeutic modalities the output characterizes, normalized to that vocabulary. discussed_modalities=false + empty array if the output never characterizes what KIND of therapy is involved. If the output explicitly says the trial tests no drug (surgery, radiotherapy technique, a device, supportive care), that IS addressing it: discussed_modalities=true with an empty array."""

TOOL = {
    "name": "report_stated",
    "description": "Report only what the writeup explicitly states; use NOT_STATED for anything it does not.",
    "input_schema": {
        "type": "object",
        "properties": {
            "phase": {"type": "string"},
            "intervention_class": {"type": "string"},
            "primary_endpoint_type": {"type": "string"},
            "sponsor_type": {"type": "string"},
            "est_readout": {"type": "string"},
            "discussed_modalities": {"type": "boolean"},
            "modalities": {"type": "array", "items": {"type": "string"}},
            "discussed_risks": {"type": "boolean"},
            "risk_flags": {"type": "array", "items": {"type": "string"}},
        },
        "required": SCALARS + ["discussed_modalities", "modalities", "discussed_risks", "risk_flags"],
    },
}


def extract(client: anthropic.Anthropic, writeup: str) -> dict | None:
    for attempt in range(4):
        try:
            msg = client.messages.create(
                model=JUDGE_MODEL, max_tokens=1500, output_config={"effort": "low"},
                system=[{"type": "text", "text": JUDGE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
                tools=[TOOL], tool_choice={"type": "tool", "name": TOOL["name"]},
                messages=[{"role": "user", "content": f"ANALYST WRITEUP:\n{writeup}"}],
            )
            for b in msg.content:
                if b.type == "tool_use":
                    return b.input
            return None
        except (anthropic.RateLimitError, anthropic.APIStatusError):
            if attempt == 3:
                return None
            time.sleep(2 * (attempt + 1))
    return None


def _scalar(v):
    """Coerce a stated scalar to a hashable string. A list/number value (e.g. the base model
    emitting ["PHASE1","PHASE2"]) is a real wrong-value, not an omission -> stringify it."""
    if v is None:
        return SENTINEL
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return " ".join(map(str, v))
    return str(v)


def stated_map(ext: dict) -> dict:
    """Build a stated map from the normalizer's output. A field is 'omitted' iff the normalizer
    returned NOT_STATED (the output never addressed it). Same treatment for both arms; the schema
    JSON addresses every field so it ~never omits, while free-form omits what it didn't surface."""
    m = {f: _scalar(ext.get(f, SENTINEL)) for f in SCALARS}
    m["_risk_discussed"] = bool(ext.get("discussed_risks"))
    m["risk_flags"] = ext.get("risk_flags", []) if ext.get("discussed_risks") else []
    m["_modalities_discussed"] = bool(ext.get("discussed_modalities"))
    m["modalities"] = ext.get("modalities", []) if ext.get("discussed_modalities") else []
    return m


def pred_from_stated(nct_id: str, m: dict) -> dict:
    """Snap the stated map into a scorable readout (SENTINEL stays -> counts as a miss vs gold)."""
    r = {"nct_id": nct_id, **{f: m[f] for f in SCALARS},
         "modalities": m["modalities"], "risk_flags": m["risk_flags"]}
    return snap_to_enum(r)


def decompose(test_set, stated_by_id):
    """Per-field stated-correct / stated-wrong / not-stated, using the snapped value vs gold."""
    g = [r for r in test_set if r["nct_id"] in stated_by_id]
    out = {}
    n = len(g)
    for f in SCALARS:
        correct = wrong = omitted = 0
        for r in g:
            m = stated_by_id[r["nct_id"]]
            if m[f] == SENTINEL:
                omitted += 1
            elif snap_to_enum({f: m[f]}).get(f) == r.get(f):
                correct += 1
            else:
                wrong += 1
        out[f] = {"correct": round(correct/n, 3), "wrong": round(wrong/n, 3), "omitted": round(omitted/n, 3)}
    rf_disc = sum(1 for r in g if stated_by_id[r["nct_id"]]["_risk_discussed"]) / n
    out["risk_flags"] = {"discussed": round(rf_disc, 3), "not_discussed": round(1 - rf_disc, 3)}
    # modalities gets the fuller treatment: unlike risk_flags it has a gold set to check
    # against, so "addressed but wrong" is separable from "never addressed".
    md_disc = exact = wrong = 0
    for r in g:
        m = stated_by_id[r["nct_id"]]
        if not m["_modalities_discussed"]:
            continue
        md_disc += 1
        if sorted(snap_to_enum({"modalities": m["modalities"]})["modalities"]) == sorted(r.get("modalities", [])):
            exact += 1
        else:
            wrong += 1
    out["modalities"] = {"discussed": round(md_disc/n, 3), "not_discussed": round(1 - md_disc/n, 3),
                         "exact_when_discussed": round(exact/md_disc, 3) if md_disc else 0.0,
                         "wrong_when_discussed": round(wrong/md_disc, 3) if md_disc else 0.0}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--gens", type=str, default=str(GENS_DEFAULT),
                    help="raw generations file (schema_out + freeform_out per trial)")
    ap.add_argument("--suffix", type=str, default="", help="output filename suffix, e.g. '_ft'")
    args = ap.parse_args()

    rows = [json.loads(l) for l in Path(args.gens).read_text().splitlines() if l.strip()]
    if args.limit:
        rows = rows[:args.limit]
    test_set = [r for r in GOLD_TEST if r["nct_id"] in {x["nct_id"] for x in rows}]

    # Both arms go through the SAME normalizer (each fed its native output: JSON for schema,
    # prose for free-form). Normalization is held constant so the only difference measured is
    # whether the STRATEGY surfaced the field. Omission is possible only when the output never
    # addresses a field -> in practice, the free-form arm.
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], base_url="https://api.anthropic.com")
    print(f"normalizing {len(rows)*2} outputs (both arms, no-rescue) with {JUDGE_MODEL} ...", flush=True)

    def judge_row(r):
        return r["nct_id"], extract(client, r["schema_out"]), extract(client, r["freeform_out"])

    raw = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(judge_row, r) for r in rows]
        done = 0
        for fut in as_completed(futs):
            nct, s, f = fut.result()
            raw[nct] = {"schema": s, "freeform": f}
            done += 1
            if done % 25 == 0 or done == len(rows):
                print(f"  normalized {done}/{len(rows)}", flush=True)

    schema_stated, ff_stated, schema_preds, ff_preds = {}, {}, {}, {}
    for r in rows:
        nct = r["nct_id"]
        if raw[nct]["schema"]:
            schema_stated[nct] = stated_map(raw[nct]["schema"])
            schema_preds[nct] = pred_from_stated(nct, schema_stated[nct])
        if raw[nct]["freeform"]:
            ff_stated[nct] = stated_map(raw[nct]["freeform"])
            ff_preds[nct] = pred_from_stated(nct, ff_stated[nct])

    schema_res = score(test_set, schema_preds)
    ff_res = score(test_set, ff_preds)
    schema_dec = decompose(test_set, schema_stated)
    ff_dec = decompose(test_set, ff_stated)

    out = {
        "model": f"mlx-community/Qwen3-4B-Instruct-2507-4bit (gens={Path(args.gens).name})",
        "judge": JUDGE_MODEL, "n": len(test_set),
        "regime": ("salience-capture: same normalizer both arms (each fed its native output), "
                   "no-rescue, omissions penalized; the only difference measured is whether the "
                   "strategy surfaced the field."),
        "B_schema": {**schema_res, "_decomposition": schema_dec},
        "A_freeform": {**ff_res, "_decomposition": ff_dec},
    }
    (ROOT / "eval" / f"score_salience{args.suffix}.json").write_text(json.dumps(out, indent=2))
    (ROOT / "eval" / f"preds_salience{args.suffix}.jsonl").write_text(
        "".join(json.dumps({"nct_id": r["nct_id"],
                            "schema_norm": raw[r["nct_id"]]["schema"],
                            "freeform_norm": raw[r["nct_id"]]["freeform"]}) + "\n" for r in rows))

    def acc(res, f):
        return res[f]["accuracy"] if f != "risk_flags" else res["risk_flags"]["set_f1"]

    print(f"\n=== SALIENCE CAPTURE (gens={Path(args.gens).name}, n={len(test_set)}) ===")
    print(f"  B (schema, JSON parse)   overall = {schema_res['_overall_structured']}")
    print(f"  A (free-form, no-rescue) overall = {ff_res['_overall_structured']}")
    print("\nfield                    schemaAcc  freeAcc   | free-form correct/wrong/OMIT | schema correct/wrong/miss")
    for f in SCALARS:
        d, s = ff_dec[f], schema_dec[f]
        print(f"  {f:22s} {acc(schema_res, f):<9.3f} {acc(ff_res, f):<9.3f} |   "
              f"{d['correct']:.2f} / {d['wrong']:.2f} / {d['omitted']:.2f}     |   "
              f"{s['correct']:.2f} / {s['wrong']:.2f} / {s['omitted']:.2f}")
    print(f"  {'risk_flags(setF1)':22s} {acc(schema_res,'risk_flags'):<9.3f} {acc(ff_res,'risk_flags'):<9.3f} |   "
          f"free-form discussed risks: {ff_dec['risk_flags']['discussed']:.2f}")
    print(f"\nwrote eval/score_salience{args.suffix}.json + preds_salience{args.suffix}.jsonl")


if __name__ == "__main__":
    main()
