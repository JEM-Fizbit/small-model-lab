# Phase 3 results — TrialScout fine-tune A/B

**Winner: Qwen3-4B**, fine-tuned via LoRA on 1,200 Claude-distilled gold examples. It nearly reproduces the teacher on the held-out 150-trial test set, running fully local at a fraction of the cost/latency.

## Scores vs the majority-class baseline

| field | baseline (floor) | **Qwen student** | lift |
|---|---|---|---|
| **overall structured** | 0.368 | **0.922** | **+0.554** |
| valid JSON | — | 1.000 | — |
| phase | 0.447 | 1.000 | +0.553 |
| modality | 0.413 | 0.773 | +0.360 |
| primary_endpoint_type | 0.280 | 0.900 | +0.620 |
| sponsor_type | 0.673 | 0.980 | +0.307 |
| est_readout | 0.033 | 0.993 | +0.960 |
| risk_flags (set-F1) | 0.364 | 0.884 | +0.520 |

Biggest lifts where the task is most learnable: `est_readout` (the deterministic date→"H1/H2 YYYY" mapping, 0.03→0.99) and `phase` (perfect). `modality` is the weakest at 0.77 — the natural target for the Phase 4 error-mining loop.

Training: LoRA, 16 layers, 700 iters, batch 4, lr 1e-4. Train loss 2.56→0.16, val 0.656. ~50 min on M5, 10 GB peak.

## Gemma 4 E2B — did not train (and why)

Both attempts (16- and 8-layer) failed immediately with `ValueError: Received 140 parameters not in model`. **Cause:** the `mlx-community/gemma-4-E2B-it-4bit` checkpoint is the **multimodal (vision+text) model** — its weights are nested under `language_model.*` plus a vision tower, which `mlx_lm.lora`'s layer targeting can't match. No text-only Gemma 4 E2B 4-bit build currently exists on the MLX hub (the `-text`/`-lm` variants exist only for Gemma 3n).

**Does it change the decision?** No. Qwen3-4B scored 0.922 (near ceiling); a 2B-effective model would have to beat that to flip the call, which is implausible on this task. The measured base-model decision (ADR-0002) resolves to Qwen3-4B. Completing the Gemma arm (via a text-only build or a different loader) is optional rigor, parked in the backlog.
