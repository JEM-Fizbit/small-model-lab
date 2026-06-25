"""Comparative eval: explicit-schema extraction vs free-form summarization.

Grounds the essay claim "defining an explicit extraction schema beats deferring
to the model on what matters." Holds the MODEL constant (base Qwen3-4B, NOT the
fine-tuned student) and varies ONLY the prompt:

  B (schema)    : "return ONLY JSON with exactly these 7 fields ..."  (format_for_mlx.build_prompt)
  A (free-form) : "summarize the key points of this trial for an investor"  (no field list)

Both outputs are then scored identically:
  1. A neutral Claude-Sonnet JUDGE reads ONLY the model's own output text (never the
     raw trial record) and maps it to the 6 scored fields via forced tool-use. This is
     the fairness control: the judge measures "did the info survive into the output",
     not "what is the right answer". If a free-form summary omits the sponsor type, the
     judge cannot recover it -> that field scores 0, which is exactly the cost of not
     specifying a schema.
  2. snap_to_enum (same as the deployed path), then harness.score against the SAME
     frozen 150-trial gold test set, with the SAME metrics as score_qwen.json.

Run:  uv run python track-b-trialscout/eval/compare_schema_vs_freeform.py            # full n=150
      uv run python track-b-trialscout/eval/compare_schema_vs_freeform.py --limit 8  # smoke test
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
import anthropic

ROOT = Path(__file__).resolve().parents[1]            # track-b-trialscout/
load_dotenv(ROOT.parent / ".env")
sys.path.insert(0, str(ROOT / "train"))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "schema"))
from format_for_mlx import build_prompt, trial_input   # noqa: E402  schema prompt + compact record
from harness import score                              # noqa: E402  same metrics as the baseline
from normalize import snap_to_enum                     # noqa: E402  same enum-snap as deployed

RAW = {json.loads(l)["nct_id"]: json.loads(l)
       for l in (ROOT / "data" / "raw" / "trials.jsonl").read_text().splitlines() if l.strip()}
GOLD_TEST = [json.loads(l) for l in (ROOT / "data" / "gold" / "test.jsonl").read_text().splitlines() if l.strip()]
SCHEMA = json.loads((ROOT / "schema" / "trial_readout.schema.json").read_text())

BASE_MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
JUDGE_MODEL = "claude-sonnet-4-6"

# The free-form prompt: an investor summary with NO field list. Same trimmed record the
# schema condition sees (trial_input), so the only difference between A and B is the ask.
FREEFORM_INSTRUCTION = (
    "You are a biotech equity analyst. Read the oncology clinical-trial record below and "
    "write a short, useful summary of the key points for an investor. Write a natural "
    "paragraph or two of prose. Do not use JSON, bullet points, or headings."
)


def freeform_prompt(raw: dict) -> str:
    return f"{FREEFORM_INSTRUCTION}\n\nTRIAL:\n{json.dumps(trial_input(raw), ensure_ascii=False)}"


# ---- Claude judge: extract the scored fields from the MODEL'S OUTPUT TEXT only ----------

JUDGE_SYSTEM = f"""You are a strict information extractor. Below is an analyst's writeup about a single oncology clinical trial. Using ONLY information explicitly stated or unambiguously implied BY THE WRITEUP ITSELF, emit a structured readout via the `emit_readout` tool.

Hard rules:
- Use ONLY the writeup. You have NO access to the underlying trial record. Do NOT use outside knowledge or guess beyond what the text supports.
- If the writeup does not provide enough to determine a field, pick the closest-supported enum, or the field's "other"/"unknown"/empty fallback. Never invent specifics the writeup doesn't contain.

Field normalization (apply to what the writeup says):
- phase: one of {SCHEMA['properties']['phase']['enum']}. If the writeup gives a numeric phase, normalize (e.g. "phase 1/2" -> "Phase 1/2").
- modality: the single best-fit modality of the lead investigational agent, from {SCHEMA['properties']['modality']['enum']}.
- primary_endpoint_type: from {SCHEMA['properties']['primary_endpoint_type']['enum']}.
- sponsor_type: from {SCHEMA['properties']['sponsor_type']['enum']} (a top-20 global pharma -> "large pharma", other industry -> "biotech").
- est_readout: the expected primary readout as "H1 YYYY" or "H2 YYYY" (months 01-06 -> H1, 07-12 -> H2). If the writeup gives only a year, use the half it states; if it gives no readout timing at all, use "unknown".
- risk_flags: subset of {SCHEMA['properties']['risk_flags']['items']['enum']} that the writeup supports. Empty array if none are stated.
- indication / investor_note: fill briefly from the writeup (not scored, but required by the tool)."""


def tool_def() -> dict:
    return {"name": SCHEMA["name"], "description": "Emit the structured readout extracted from the writeup.",
            "input_schema": {"type": "object", "properties": SCHEMA["properties"], "required": SCHEMA["required"]}}


def judge_extract(client: anthropic.Anthropic, writeup: str) -> dict | None:
    """Claude reads ONLY `writeup` and returns the structured readout (or None on failure)."""
    for attempt in range(4):
        try:
            msg = client.messages.create(
                model=JUDGE_MODEL, max_tokens=600,
                system=[{"type": "text", "text": JUDGE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
                tools=[tool_def()], tool_choice={"type": "tool", "name": SCHEMA["name"]},
                messages=[{"role": "user", "content": f"ANALYST WRITEUP:\n{writeup}"}],
            )
            for block in msg.content:
                if block.type == "tool_use":
                    return block.input
            return None
        except (anthropic.RateLimitError, anthropic.APIStatusError) as e:
            if attempt == 3:
                print(f"  judge failed: {type(e).__name__}", flush=True)
                return None
            time.sleep(2 * (attempt + 1))
    return None


# ---- local generation (base model, no adapter) -----------------------------------------

def generate_all(limit: int):
    from mlx_lm import load, generate
    print(f"loading base model {BASE_MODEL} (no adapter) ...", flush=True)
    model, tok = load(BASE_MODEL)
    test_set = GOLD_TEST[:limit] if limit else GOLD_TEST
    rows = []
    t0 = time.time()
    for i, g in enumerate(test_set, 1):
        raw = RAW[g["nct_id"]]
        schema_prompt = tok.apply_chat_template(
            [{"role": "user", "content": build_prompt(raw)}], add_generation_prompt=True, tokenize=False)
        ff_prompt = tok.apply_chat_template(
            [{"role": "user", "content": freeform_prompt(raw)}], add_generation_prompt=True, tokenize=False)
        schema_out = generate(model, tok, prompt=schema_prompt, max_tokens=400, verbose=False)
        ff_out = generate(model, tok, prompt=ff_prompt, max_tokens=400, verbose=False)
        rows.append({"nct_id": g["nct_id"], "schema_out": schema_out, "freeform_out": ff_out})
        if i % 10 == 0 or i == len(test_set):
            print(f"  gen {i}/{len(test_set)}  ({(time.time()-t0)/i:.1f}s/trial)", flush=True)
    return test_set, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="score only the first N test trials (0 = all 150)")
    args = ap.parse_args()

    test_set, rows = generate_all(args.limit)

    # Judge both conditions identically, in parallel. The judge sees ONLY the model output text.
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], base_url="https://api.anthropic.com")
    print(f"judging {len(rows)*2} outputs with {JUDGE_MODEL} (output-text only) ...", flush=True)

    def judge_row(r):
        s = judge_extract(client, r["schema_out"])
        f = judge_extract(client, r["freeform_out"])
        return r["nct_id"], s, f

    judged = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(judge_row, r): r["nct_id"] for r in rows}
        done = 0
        for fut in as_completed(futs):
            nct, s, f = fut.result()
            judged[nct] = (s, f)
            done += 1
            if done % 20 == 0 or done == len(rows):
                print(f"  judged {done}/{len(rows)}", flush=True)

    schema_preds, ff_preds, schema_ok, ff_ok = {}, {}, 0, 0
    for r in rows:
        nct = r["nct_id"]
        s, f = judged.get(nct, (None, None))
        if s:
            schema_ok += 1
            schema_preds[nct] = snap_to_enum({"nct_id": nct, **s})
        if f:
            ff_ok += 1
            ff_preds[nct] = snap_to_enum({"nct_id": nct, **f})

    schema_res = score(test_set, schema_preds)
    ff_res = score(test_set, ff_preds)
    schema_res["_judge_ok"] = round(schema_ok / len(rows), 3)
    ff_res["_judge_ok"] = round(ff_ok / len(rows), 3)

    out = {
        "model": BASE_MODEL, "judge": JUDGE_MODEL, "n": len(rows),
        "note": "base model (NOT fine-tuned); same model both arms; judge reads only model output text.",
        "B_schema": schema_res, "A_freeform": ff_res,
    }
    eval_dir = ROOT / "eval"
    (eval_dir / "score_schema_vs_freeform.json").write_text(json.dumps(out, indent=2))
    (eval_dir / "preds_schema_vs_freeform.jsonl").write_text(
        "".join(json.dumps({"nct_id": r["nct_id"], "schema_out": r["schema_out"],
                            "freeform_out": r["freeform_out"],
                            "judged_schema": judged.get(r["nct_id"], (None, None))[0],
                            "judged_freeform": judged.get(r["nct_id"], (None, None))[1]}) + "\n"
                for r in rows))

    print("\n=== SCHEMA vs FREE-FORM (base Qwen3-4B, n={}) ===".format(len(rows)))
    print(f"  B (schema)    overall_structured = {schema_res['_overall_structured']}")
    print(f"  A (free-form) overall_structured = {ff_res['_overall_structured']}")
    print("\nper-field accuracy (schema / free-form):")
    for fld in ["phase", "modality", "primary_endpoint_type", "sponsor_type"]:
        print(f"  {fld:24s} {schema_res[fld]['accuracy']:.3f} / {ff_res[fld]['accuracy']:.3f}")
    print(f"  {'est_readout':24s} {schema_res['est_readout']['accuracy']:.3f} / {ff_res['est_readout']['accuracy']:.3f}")
    print(f"  {'risk_flags (set-F1)':24s} {schema_res['risk_flags']['set_f1']:.3f} / {ff_res['risk_flags']['set_f1']:.3f}")
    print("\nwrote eval/score_schema_vs_freeform.json + preds_schema_vs_freeform.jsonl")


if __name__ == "__main__":
    main()
