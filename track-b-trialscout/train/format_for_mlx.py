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


def main():
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
