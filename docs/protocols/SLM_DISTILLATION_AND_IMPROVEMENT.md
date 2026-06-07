# SLM Distillation & Improvement

> Distill a frontier teacher (Claude) into a small local model for a narrow task, evaluate it honestly, and improve it with an error-mining loop — including the ceilings that govern how far it can go.

**Applies to:** Apple MLX / `mlx-lm` LoRA (or any SFT stack) · Anthropic Claude as teacher/judge · eval-first ML workflows
**Last Updated:** 2026-06-08
**Version:** 1.0
**Original Source:** `slm-lab/track-b-trialscout/` (TrialScout — Qwen3-4B distilled to 0.93 on a clinical-trial readout task)

---

## Overview

For a **narrow, well-defined task** (extract / classify / reformat), a small local model can *match* a frontier teacher at a fraction of the cost/latency, running locally and free. The lever is **distillation = automating the labeling**: the teacher writes the gold answers; the student learns to reproduce them (SFT). This protocol covers the full arc — pick the task, distill, eval honestly, improve — plus the two ceilings that decide when to stop.

### Key benefits
- Cheap, local, private inference on a task you'd otherwise pay a frontier API for.
- An eval harness that tells you *honestly* whether it works (and when it's plateaued).

---

## When to Use

| Scenario | Distill an SLM? |
|----------|-----------------|
| Narrow, structured task (extraction, classification, fixed-schema output) | **Yes** — the spike SLMs win on |
| High call volume where a frontier API is costly | **Yes** — distill the narrow sub-tasks; keep the frontier model for the creative/reasoning ones |
| Hard open-ended reasoning / synthesis | **No** — the student caps *below* the teacher; you'd ship a downgrade |
| Need to *exceed* a strong model | **No** — distillation can't beat the teacher (see Ceilings → use a verifier loop instead) |
| Privacy/offline requirement on a narrow task | **Yes** |

---

## Core Concepts

- **SFT vs RLHF vs RLAIF.** SFT/distillation = imitate the teacher's *answer* (this protocol). RLHF = optimize a reward from human preference rankings. RLAIF/Constitutional = an *AI* gives that feedback. The "replace human reinforcement with Claude" instinct is RLAIF; distillation is the simpler, cheaper lever.
- **Distillation compresses & localizes existing intelligence — it doesn't create more.** You harvest one spike of the teacher's jagged frontier and stamp it into a small model.
- **Two ceilings (load-bearing):**
  1. **Teacher quality caps student quality — you cannot beat the teacher.** A weak teacher silently ceilings the whole project; use a strong one (Sonnet/Opus) for gold labels.
  2. **You cannot out-data label noise.** Where the teacher's own labels are inconsistent (genuinely ambiguous cases), more training data doesn't help — that's a definitional/ground-truth problem, fixed by sharpening the task spec, not by volume.

---

## Implementation (the pipeline)

1. **Lock the task + output schema.** A tight JSON schema with enums. Hand-craft a few gold fixtures.
2. **Base model by measurement, not faith.** A/B candidate base models on the eval; don't hardcode a winner.
3. **Generate gold labels (teacher distillation), safely** — this spends money, so gate it:
   - **Forced tool-use** so every label is schema-valid; **prompt-cache** the static prefix (rules + few-shot) to slash cost.
   - **Hard $ cap** (abort before a call that would exceed it).
   - **Pilot gate**: label 10 first; if <8/10 valid, abort before the bulk run.
   - **Incremental + resumable** writes (a crash loses nothing).
   - `temperature=0` for label consistency.
4. **Eval-first — a first-class deliverable, not a bolt-on:**
   - Golden set from **real** data; per-field structured metrics (accuracy + **macro-F1**) + a judge for free-text.
   - A **baseline** (majority-class floor) — this is how you *know* the model learned something.
   - A **frozen** val/test split — never changes, so deltas across experiments are comparable.
5. **Fine-tune** (LoRA): mask the prompt (loss on the target only); keep hyperparameters fixed across experiments so only *data* varies.
6. **Score vs baseline; report per-field deltas.** Re-run the eval whenever prompt/model/schema changes.
7. **Validate-tiny before every long/expensive run** (training, $-spend): smoke-test on a handful first.

---

## The improvement loop (error-mining)

When the headline metric stalls, **mine the errors and categorize them** — they're rarely one problem:

| Failure mode | Fix | Cost |
|---|---|---|
| **Enum drift** (casing, out-of-vocab) | Deterministic **snap-to-enum** normalizer (exact → case-insensitive → 'other' bucket) | Free, no retrain |
| **Rare-class / long-tail** gaps (low macro-F1, high accuracy) | **Targeted generation** — fetch + teacher-label more of the rare classes; **append to TRAIN only**, freeze val/test | Modest |
| **Definitional / ambiguity** (teacher itself inconsistent) | Sharpen the schema definition; relabel — but see ceilings | Varies |

Then **retrain (identical hyperparameters) → re-eval on the frozen test → report the delta.**

**What the loop teaches (and its limits):**
- `accuracy` vs `macro-F1`: a big gap means a *rare-class* problem (the model is fine on common classes). Target macro-F1, not the headline.
- A near-ceiling model barely moves on the headline even when you fix the right thing — be honest that the gain is marginal.
- **Don't relabel the test set to chase a number** — that moves the goalposts and breaks comparability. Augment *train*, hold test frozen.

---

## The verifier ceiling — how to actually exceed the teacher

Distillation plateaus at the teacher. The **only** way a trained model becomes *more capable than its supervisor* is to learn from a **cheap, non-gameable verifier** instead of a teacher:

- **code** → run the tests; **math** → check the answer; **games** → win/lose; **reality** → real-world outcomes.
- A verifier provides *ground truth*, not a smarter model's opinion — so the student can surpass any teacher (AlphaZero-style).
- **Without a verifier, self-training on your own outputs collapses** into amplifying the model's own noise (model collapse / reward hacking). Re-running a distillation loop against a *static teacher* is a wash — it just echoes the teacher's biases. (Confirmed empirically in slm-lab Phase 4.)
- The buildable version: a **STaR-style loop** — model proposes → verifier keeps only correct outputs → those become new training data → retrain → repeat. Self-improves with zero human labels because the verifier is the ground truth.

This is the bridge from "distill a narrow expert" (this protocol) to "self-improving model" (a verifier-grounded next step).

---

## Anti-Patterns

```text
❌ Reshuffle all data into new train/val/test when adding examples → the test set changes,
   every prior score becomes incomparable.
✅ Augment TRAIN only; freeze val/test for a clean delta.

❌ No baseline → you can't tell if the model learned anything.
✅ Majority-class floor as the reference point.

❌ Uncapped, unwatched teacher API spend.
✅ Hard $ cap + 10-item pilot gate + resumable writes.

❌ Keep distilling harder to "beat" a strong teacher.
✅ Accept the ceiling; switch to a verifier loop if you need to exceed it.

❌ Chase the headline metric when the residual error is teacher label noise.
✅ Sharpen the task definition (or stop) — more data won't fix ambiguity.
```

---

## Troubleshooting

**Student plateaus well below "perfect."** Check whether the residual errors are *ambiguous cases the teacher labels inconsistently*. If so, it's a label-noise ceiling — fix the schema definition, not the data volume.

**macro-F1 ≪ accuracy.** Rare-class problem. Augment the long tail (train-only) or accept the class imbalance.

**Costs ballooning on labeling.** Ensure the static prefix is prompt-cached and you're using forced tool-use (short, schema-valid outputs); cap and pilot-gate.

---

## Resources

- Reference implementation: `slm-lab/track-b-trialscout/` — `train/make_gold.py` (cost-capped teacher), `train/{format_for_mlx,run_phase3}.py`, `eval/{harness,infer_and_score}.py`, `schema/normalize.py` (snap-to-enum), `eval/PHASE4_RESULTS.md` (the error-mining write-up).
- [`AI_EVALS.md`](AI_EVALS.md) — golden-set regression evals (the eval discipline this builds on).
- [`AI_OBSERVABILITY.md`](AI_OBSERVABILITY.md) — tracing/observability for AI pipelines.
- [`LOCAL_MODEL_MCP_EXPERT.md`](LOCAL_MODEL_MCP_EXPERT.md) — how to *serve* the model you distilled.
- [`ANTHROPIC_MODEL_REFERENCE.md`](ANTHROPIC_MODEL_REFERENCE.md) — choosing the teacher/judge model.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-06-08 | Initial release. Extracted from slm-lab/TrialScout (distillation + Phase 4 error-mining + verifier insight). |

---

**Protocol Version**: 1.0
**Last Updated**: 2026-06-08
**Original Source**: slm-lab (track-b-trialscout)
