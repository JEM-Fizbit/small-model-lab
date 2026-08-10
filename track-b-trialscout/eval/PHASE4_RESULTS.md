# Phase 4 results — recursive error-mining loop (B6)

> **⚠️ Schema v1 artifact.** These numbers were measured under the v1 schema (single-valued
> `modality`, with a `combination` value) and the Sonnet 4.6 teacher. Both were replaced on
> 2026-08-10 — see ADR-0016, ADR-0017 and ADR-0018. They remain reproducible via
> [`eval/v1-frozen/`](v1-frozen/); the current scorecard is [`PHASE6_RESULTS.md`](PHASE6_RESULTS.md).
> They are kept, not deleted, because the published walk-through and outside writing cite them.

**One-line:** the loop ran end-to-end and worked *as a process*; the model gain was **marginal**
because TrialScout was already near its ceiling, and the dominant residual error is teacher-label
noise (the `combination` boundary), not something more data can fix.

## What we did (error → data → retrain)

1. **Mined the errors** on the held-out test set. `modality`'s low macro-F1 (0.57) decomposed into
   three failure modes, not one:
   - **definitional** — `combination` ↔ `small molecule`/`mAb` (~half of modality errors), where even
     the teacher's gold labels are inconsistent;
   - **enum drift** — out-of-vocab/casing values (`PCR` for `pCR`, `radioimmunotherapy`);
   - **rare-class gaps** — ADC / bispecific / cell / gene / vaccine / oncolytic.
2. **Free fix — snap-to-enum** (`schema/normalize.py`, deterministic): off-schema preds **4→0**
   (server now always schema-valid), overall **0.922→0.925**.
3. **Targeted generation** — fetched 300 net-new rare-modality trials (excluding all gold NCTs → no
   test leakage), Sonnet-labeled them ($2.76, 300/300 valid) under a **clarified** `combination` rule
   (convention unchanged — test labels are frozen). Rare-class train rows **154→389**; train **1200→1500**;
   **val/test frozen at 150** so the delta is clean.
4. **Retrained** `qwen_v2` with identical hyperparameters (only the data changed). Val loss
   **0.656→0.539** on the frozen val set.

## The numbers (qwen_v2 vs original, both snap-adjusted, same frozen 150-trial test)

| metric | orig | v2 | Δ |
|---|---|---|---|
| OVERALL structured | 0.925 | **0.930** | +0.005 |
| modality accuracy | 0.780 | 0.785 | +0.005 |
| **modality macro-F1** | 0.623 | **0.651** | **+0.028** (the target) |
| primary_endpoint_type accuracy | 0.913 | 0.926 | +0.013 |
| primary_endpoint_type macro-F1 | 0.933 | 0.902 | −0.031 |
| sponsor_type acc / macro-F1 | 0.980 / 0.969 | 1.000 / 1.000 | +0.031 |
| risk_flags set-F1 | 0.884 | 0.876 | −0.008 |
| valid JSON | 1.000 | 0.993 | −1 trial (one parse failure) |

Rare-class modality **recall**: ADC 0.40→0.60, radiotherapy 0.75→0.88; cell therapy / cancer
vaccine / oncolytic were already 1.00 (no headroom).

## Verdict: a statistical wash — keep the original as the reference

+0.005 overall is within noise for n=150. The augmentation lifted exactly the rare modalities that
were weak (ADC, radiotherapy) and made sponsor perfect, but cost a little on endpoint macro-F1 and
risk_flags and added one parse failure. Net: not a clear win.

**Decision:** the production reference stays **`adapters/qwen`** (the server is unchanged). `qwen_v2`
is retained (`adapters/qwen_v2`, gitignored) for its rare-modality + sponsor gains if those matter
more than the endpoint trade — promotion is a judgement call, not an obvious upgrade.

## Why the gain was small (the real lesson)

The model was already near-ceiling, and error-mining showed the *dominant* remaining modality error
is the `combination` definitional boundary — partly **irreducible teacher-label noise**. We did not
relabel the existing gold under a new convention (that would move goalposts vs the frozen test, and
distillation can't exceed the teacher anyway). So augmenting rare-class data helped precisely where
it could and no further. Two distillation truths, made concrete: **you can't beat the teacher**, and
**more data can't out-run label noise**. The loop itself (mine → categorize → targeted data → retrain
→ delta on a frozen test) is the reusable asset; iterating it further here would be completionism, not value.
