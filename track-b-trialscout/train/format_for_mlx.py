"""Join raw trials + gold labels into the chat format mlx_lm.lora expects.

Each example becomes {"messages": [{"role":"user", ...}, {"role":"assistant", ...}]}:
  user      = a fixed instruction + the trial record (the INPUT)
  assistant = the gold readout JSON, minus nct_id (the TARGET to learn)

With `--mask-prompt`, mlx_lm computes loss only on the assistant turn, so the model
learns to *produce the readout*, not to echo the prompt.

Writes mlx_data/{train,valid,test}.jsonl. The same prompt builder is reused at
inference (infer_and_score.py) so train/test prompts match exactly.

Run:  uv run python track-b-trialscout/train/format_for_mlx.py
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "trials.jsonl"
RAW_AUG = ROOT / "data" / "raw" / "augment_rare.jsonl"  # Phase-4 rare-modality trials
GOLD = ROOT / "data" / "gold"
AUG_GOLD = GOLD / "augment_rare.jsonl"                   # ...their labels (train-only)
OUT = ROOT / "train" / "mlx_data"

# 600 truncated 32% of trials. Measured token cost of lifting it entirely, with uncapped
# interventions and descriptions on: median prompt 536, p95 969, max 1733 -- so it fits inside
# a 2048 max-seq-length with room to spare. None = no truncation.
SUMMARY_CHARS = None

TARGET_FIELDS = ["phase", "indication", "intervention_class", "modalities",
                 "primary_endpoint_type", "sponsor_type", "est_readout", "risk_flags_judgement",
                 "investor_note"]

INSTRUCTION = (
    "You are TrialScout. Read the oncology clinical-trial record below and return ONLY a JSON "
    "object with exactly these fields: phase, indication, intervention_class, modalities (array), "
    "primary_endpoint_type, sponsor_type, est_readout, risk_flags (array), investor_note. "
    "No prose, no code fence."
)

# --- v4 ---------------------------------------------------------------------------------
# The student's job narrows to what the registry only implies. phase, sponsor_type and
# est_readout are read or computed by schema/facts.py and schema/derive.py, so training on
# them would spend LoRA capacity learning a lookup.
RAW_FULL = ROOT / "data" / "raw" / "studies_full.jsonl"
OUT_V4 = ROOT / "train" / "mlx_data_v4"

TARGET_FIELDS_V4 = ["indication", "intervention_class", "modalities",
                    "primary_endpoint_type", "risk_flags_judgement", "investor_note"]

INSTRUCTION_V4 = (
    "You are TrialScout. Below is an oncology clinical-trial FACTS block already read from "
    "the registry — treat it as settled. Return ONLY a JSON object with exactly these fields: "
    "indication, intervention_class, modalities (array), primary_endpoint_type, "
    "risk_flags_judgement (array), investor_note. Classify every entry in `agents`; an empty "
    "`agents` means no drug is under study. No prose, no code fence."
)


def build_prompt_v4(facts: dict) -> str:
    """v4 prompt. Must stay byte-identical between training and inference -- infer_and_score
    imports this, so a divergence here shows up as an unexplained eval drop, not an error."""
    f = dict(facts)
    f.pop("nct_id", None)   # known at scoring time; don't make the model copy it
    return f"{INSTRUCTION_V4}\n\nTRIAL FACTS:\n{json.dumps(f, ensure_ascii=False)}"


def trial_input(raw: dict) -> dict:
    """The compact record shown to the model (matches what the teacher saw, summary trimmed)."""
    r = dict(raw)
    if r.get("brief_summary"):
        r["brief_summary"] = r["brief_summary"][:SUMMARY_CHARS]
    r.pop("nct_id", None)  # nct_id is known at scoring time; don't make the model copy it
    return r


def build_prompt(raw: dict) -> str:
    return f"{INSTRUCTION}\n\nTRIAL:\n{json.dumps(trial_input(raw), ensure_ascii=False)}"


def target_json(gold: dict) -> str:
    return json.dumps({k: gold[k] for k in TARGET_FIELDS}, ensure_ascii=False)


def main_v4():
    """Build the v4 training set from the facts tier."""
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    from schema.facts import extract, project_for_prompt

    facts = {}
    for line in RAW_FULL.read_text().splitlines():
        if not line.strip():
            continue
        f = project_for_prompt(extract(json.loads(line)))
        if f.get("nct_id"):
            facts.setdefault(f["nct_id"], f)
    OUT_V4.mkdir(parents=True, exist_ok=True)
    for split, fname in [("train", "train"), ("val", "valid"), ("test", "test")]:
        src = GOLD / f"{split}_v4.jsonl"
        if not src.exists():
            print(f"  MISSING {src.name} — run make_gold.py --schema v4 --out all_v4 first")
            continue
        rows = [json.loads(x) for x in src.read_text().splitlines() if x.strip()]
        n = 0
        with (OUT_V4 / f"{fname}.jsonl").open("w") as fh:
            for g in rows:
                f = facts.get(g["nct_id"])
                if not f:
                    continue
                # Gate on shape, not on presence: a v3 row merged in here would train two
                # conventions at once and do it silently (the ADR-0020 failure mode).
                if any(k not in g for k in TARGET_FIELDS_V4):
                    continue
                ex = {"messages": [
                    {"role": "user", "content": build_prompt_v4(f)},
                    {"role": "assistant",
                     "content": json.dumps({k: g[k] for k in TARGET_FIELDS_V4}, ensure_ascii=False)},
                ]}
                fh.write(json.dumps(ex, ensure_ascii=False) + "\n")
                n += 1
        print(f"{fname}.jsonl: {n} examples")
    print(f"-> {OUT_V4}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default="v3", choices=["v3", "v4"])
    if ap.parse_known_args()[0].schema == "v4":
        return main_v4()
    # raw records come from the main pull + (if present) the Phase-4 rare-modality augment
    raw = {}
    for rf in [RAW, RAW_AUG]:
        if rf.exists():
            for line in rf.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    raw[r["nct_id"]] = r
    OUT.mkdir(parents=True, exist_ok=True)
    # mlx_lm wants files named train.jsonl / valid.jsonl / test.jsonl
    for split, fname in [("train", "train"), ("val", "valid"), ("test", "test")]:
        rows = [json.loads(l) for l in (GOLD / f"{split}.jsonl").read_text().splitlines() if l.strip()]
        if split == "train" and AUG_GOLD.exists():
            aug = [json.loads(l) for l in AUG_GOLD.read_text().splitlines() if l.strip()]
            # Schema gate. The Phase-4 augment was labeled under schema v1 (single-valued
            # `modality`, with `combination`). Merging those rows into a v2 training set
            # would teach two contradictory conventions at once, and would do it silently.
            stale = [r for r in aug if "modalities" not in r]
            if stale:
                print(f"  SKIPPING {AUG_GOLD.name}: {len(stale)}/{len(aug)} rows predate the "
                      f"current schema (no `modalities` field). Relabel it before using it.")
            else:
                rows = rows + aug  # augment feeds TRAIN only; val/test stay frozen
                print(f"  (train augmented with {len(aug)} rare-modality rows -> {len(rows)} total)")
        n = 0
        with (OUT / f"{fname}.jsonl").open("w") as f:
            for g in rows:
                r = raw.get(g["nct_id"])
                if not r:
                    continue
                ex = {"messages": [
                    {"role": "user", "content": build_prompt(r)},
                    {"role": "assistant", "content": target_json(g)},
                ]}
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
                n += 1
        print(f"{fname}.jsonl: {n} examples")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
