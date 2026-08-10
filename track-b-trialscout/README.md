# TrialScout (Track B)

A small model that turns an **oncology clinical-trial record into a structured, investor-relevant readout**. This is the *useful* model — the narrow, structured task where a fine-tuned SLM genuinely wins.

## Pipeline

```
ClinicalTrials.gov v2 ──fetch_trials.py──▶ data/raw/trials.jsonl   (1,500 oncology interventional trials)
                                                  │
schema/trial_readout.schema.json  +  schema/fewshot.jsonl (hand-crafted gold)
                                                  │
                          make_gold.py (Sonnet teacher, forced tool-use, prompt-cached)
                                                  ▼
                          data/gold/{train,val,test}.jsonl   (distilled gold labels)
                                                  │
                          (Phase 3) LoRA fine-tune Qwen3-4B / Gemma 4 E2B via MLX
                                                  ▼
                          eval/harness.py  ──▶ beat the majority-class baseline
```

## The task (output schema)

Each trial → a JSON readout: `phase`, `indication`, `intervention_class`, `modalities[]`, `primary_endpoint_type`, `sponsor_type`, `est_readout` (H1/H2 YYYY), `risk_flags[]`, and a ≤2-sentence `investor_note`. Controlled vocabularies + the full contract live in [`schema/trial_readout.schema.json`](schema/trial_readout.schema.json).

`modalities` is a **list** — a trial pairing an antibody with chemotherapy returns both — and is **empty** when the trial tests no drug at all, with `intervention_class` saying what it does test (surgery, external-beam radiation, a device, supportive care). Schema v1 had a single `modality` with a `combination` value; see ADR-0016 and ADR-0017 for why that was replaced, and [`eval/v1-frozen/`](eval/v1-frozen/) for the v1 measurement, still runnable.

## Run it

```bash
# 1. Fetch trials (free, public API)
uv run python track-b-trialscout/data/fetch_trials.py --target 1500

# 2. Distill gold labels with the Claude teacher (SPENDS MONEY — needs ANTHROPIC_API_KEY)
#    Hard cost cap + 10-trial pilot gate; resumable.
uv run python track-b-trialscout/train/make_gold.py --target 1500 --cap 24

# 3. Establish the baseline the fine-tuned model must beat
uv run python track-b-trialscout/eval/harness.py --baseline majority

# (Phase 3) fine-tune, then score the student:
uv run python track-b-trialscout/eval/harness.py --pred <student_preds.jsonl>
```

## Design notes

- **Teacher → student distillation.** Sonnet generates the gold labels (forced tool-use guarantees schema-valid output; prompt caching makes it cheap). The fine-tuned student learns to reproduce them locally at a fraction of the cost/latency. Teacher quality caps student quality — see `docs/DECISIONS.md`.
- **Oncology only**, interventional, phased — a deliberately narrow slice (small models reward narrowness).
- Data (`data/raw/`, `data/gold/`) is regenerable and **gitignored**; the schema + few-shot fixtures are committed (they're the contract).
