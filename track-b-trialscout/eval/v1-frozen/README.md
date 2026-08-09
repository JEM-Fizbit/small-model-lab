# v1-frozen — the record behind the published v1 numbers

TrialScout's first published scorecard (**0.922 overall structured**, `modality` 0.773) was
measured under the **v1 schema**, whose `modality` field was a single value drawn from an enum
that mixed ten real modalities with `combination`. That field was superseded — see
[ADR-0016](../../../docs/DECISIONS.md) for the diagnosis and ADR-0017 for the replacement.

The v1 figures are cited on the [public walk-through](https://jem-fizbit.github.io/small-model-lab/track-b/)
and in external writing, so they must stay **checkable** after the schema moved on. This directory
is that guarantee.

## Check it yourself

```bash
uv run python track-b-trialscout/eval/v1-frozen/verify_v1.py
```

It re-derives the entire published per-field table from the committed files and exits non-zero if
anything drifts. No model, no adapter, no API key, no network.

## Why this is committed when the rest of the data is not

`.gitignore` excludes datasets and weights on the grounds that they are *regenerable from scripts*.
These files are not, for two independent reasons:

1. **The split cannot be reproduced.** `make_gold.py` derives the 80/10/10 split by shuffling rows
   read back from `all.jsonl`, which is written in `ThreadPoolExecutor` completion order. A fresh
   teacher run produces a different 150-trial test set. "The frozen test set" only exists as a file.
2. **The teacher moves.** Gold was labelled by `claude-sonnet-4-6` on 2026-06-06. Re-running it later
   is a different measurement, not the same one repeated.

So the choice was between committing ~250 KB and letting the published figures become permanently
unverifiable. This is a deliberate, narrow exception, recorded in ADR-0017.

## What's here

| file | what it is |
|---|---|
| `gold_test.jsonl` | the frozen 150-trial test set, v1 labels |
| `preds_qwen.jsonl` | `adapters/qwen`'s raw predictions over those 150 trials |
| `score_qwen.json` | the published scores |
| `harness_v1.py` | the v1 scorer (single-valued `modality`, accuracy + macro-F1) |
| `schema/trial_readout.schema.json` | the v1 output contract |
| `schema/normalize.py` | the v1 `snap_to_enum` |
| `schema/fewshot.jsonl` | the three worked examples in the v1 teacher prompt |
| `build_prompt_v1.py` | the v1 student prompt, lifted out of `format_for_mlx.py` |
| `MANIFEST.json` | adapter hash, training hyperparameters, gold-run provenance |
| `verify_v1.py` | recomputes the published table and asserts it |

## The one thing not committed

The **adapter itself** (224 MB of checkpoints; 29 MB for the final `adapters.safetensors`) stays
local, at `train/adapters/qwen/`. `MANIFEST.json` records its SHA-256 and full training config so a
given file can be identified as the one that produced these numbers.

Practical consequence, stated plainly: **recomputing the scores from the predictions needs only what
is committed here** — that is what `verify_v1.py` does. **Regenerating the predictions from the model**
needs the local adapter. If the adapter is ever lost, the scores remain checkable and the predictions
remain readable; what becomes unreproducible is generating *new* predictions under v1.

## Two numbers, not one

`preds_qwen.jsonl` holds the model's **raw** output. The published headline **0.922** is the raw
score. The deterministic `snap_to_enum` normalizer shipped later (ADR-0011) and lifts the same
predictions to **0.925** (`modality` 0.773 → 0.780). Both are quoted in the repo, in different
places, and `verify_v1.py` checks both — so neither reads as a discrepancy later.
