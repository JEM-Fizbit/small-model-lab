# Schema vs free-form extraction — a controlled A/B

**Question.** Does defining an explicit extraction schema beat deferring to the model on "what
matters"? We hold the **model constant** and vary **only the prompt**:

- **B — schema:** "return ONLY JSON with exactly these 7 fields …" (the production prompt).
- **A — free-form:** "write a short investor summary of this trial" — no field list, prose only.

Both outputs are scored **identically**: a neutral Claude-Sonnet judge reads **only the model's own
output text** (never the raw trial) and maps it to the 6 scored fields via forced tool-use; then
`snap_to_enum` + the same `harness.score` against the **same frozen 150-trial gold test set** as
`score_qwen.json`. The judge is the fairness control — it measures *"did the fact survive into the
output"*, not *"what is the right answer"*. If a summary omits the sponsor, the judge can't recover it.

**Model:** base `Qwen3-4B-Instruct-2507-4bit` — **NOT** the fine-tuned student (see caveat 1).
**Schema:** v2 (ADR-0017). Judge `claude-sonnet-4-6`, unchanged from v1 so the two arms stay comparable to each other.
Run: `eval/compare_schema_vs_freeform.py`, n=150, judge `claude-sonnet-4-6`, both arms parsed 150/150.

## Result — free-form still edges out schema overall; one field flips decisively the other way

*Re-run 2026-08-10 under schema v2 (ADR-0017). The v1 figures are in `eval/v1-frozen/` and in this
file's git history. Both arms were regenerated and re-judged; only the schema changed.*

| field | schema | free-form | winner | v1 verdict |
|---|---|---|---|---|
| **OVERALL structured** | **0.770** | **0.785** | free-form +0.015 | free-form +0.044 |
| phase | 0.933 | 0.980 | ~tie | ~tie |
| intervention_class | 0.920 | 0.920 | tie | *(new field)* |
| modalities (set-F1) | 0.780 | 0.838 | free-form +0.058 | **free-form +0.200** |
| primary_endpoint_type | 0.873 | 0.900 | ~tie | ~tie |
| sponsor_type | 0.273 | 0.867 | **free-form +0.594** | free-form +0.546 |
| **est_readout** | **0.927** | **0.213** | **schema +0.714** | schema +0.613 |
| risk_flags (set-F1) | 0.682 | 0.778 | free-form +0.096 | free-form +0.091 |

**Every v1 conclusion reproduces, and the sharpest one got sharper.** `est_readout` — the derived,
committed field — widened from a +0.61 schema win to **+0.714**. `sponsor_type` remains a large
free-form win. Overall, free-form still edges ahead, though the gap narrowed to within noise.

**The one real change: modality's free-form advantage largely evaporated, +0.200 → +0.058.** That is
worth dwelling on. In v1 the schema arm was forced to choose between ten modalities and
`combination`, a value that is not a modality (ADR-0016); free-form prose simply sidestepped the bad
category by describing the drugs in words. Fixing the taxonomy removed most of the schema arm's
handicap. **A large part of what looked like "prose beats schemas for this field" was really "this
particular schema was badly specified"** — the same finding as ADR-0016, arriving from a third
independent direction.

## Why (the mechanism — this is the real finding)

The base model in terse-JSON mode **dumps raw field values instead of the schema's vocabulary**:
it emits `sponsor_type: "INDUSTRY"`, `modality: "Vaccine"`, `phase: "PHASE1-PHASE2"` — none of which
are the controlled enums — so the judge maps them to `other` / a near-miss and the field scores 0.
The un-fine-tuned model can't *recall and classify into the enum in one shot*.

Free-form inverts the order: the model writes "*Enterome's* Phase 1/2 trial of EO2463 …", **surfacing
the raw entity** (sponsor name, drug, design) in prose, and the strong judge then classifies it
(Enterome → `biotech`). The summary acts as an elicitation/reasoning step; structuring is deferred to
a capable reader. For *lookup* facts that's a better division of labor than forcing a weak model to
self-structure.

**The exception is `est_readout` (0.83 vs 0.22) — and it's the kernel of truth in the original claim.**
The readout window is a **derived, committed** value (primary-completion date → "H1/H2 YYYY"). The
schema prompt makes the model commit a date the judge can convert; a free summary has no reason to
state a precise completion date, so the judge can't recover the half-year window. **Explicit schemas
matter most for derived/committed fields that a free summary won't volunteer.**

## Caveats (load-bearing — read before citing)

1. **This is the BASE model, not the deployed system.** The fine-tuned TrialScout student scores
   **0.939** schema'd on this same test set (`score_qwen_v2s.json`). Fine-tuning is precisely what teaches
   the model to emit the controlled vocabulary the base model fluffs. So *"schema beats free-form"*
   **is** true for the shipped product — but that contrast bundles **schema + fine-tuning**, not schema
   alone. This A/B isolates the prompt; it does not say fine-tuning is unnecessary.
2. **Part of free-form's win leans on the judge's entity knowledge** (knowing "Enterome" is a biotech).
   That's legitimate — surfacing the named entity *is* more useful than emitting a wrong terse class —
   but it means the free-form arm benefits from a strong downstream reader, not just the prose itself.
3. **n=150, single run, one base model.** Field-level deltas >~0.1 are directional; sub-0.05 gaps
   (phase, endpoint) are noise.

## Takeaway for the essay

Don't ground a clean "80 vs 95" on TrialScout — the controlled A/B doesn't support it and partly
inverts. The defensible, more interesting claims the data **does** support:

- For a **derived/committed** field (readout window), explicit schema **0.83 vs 0.22** free-form — a
  clean, large win in the predicted direction.
- For **lookup** facts (sponsor, modality), a free summary + a capable extractor **matched or beat**
  the schema'd base model — because the schema's value shows up only **after** the model has learned
  the vocabulary (fine-tuning: 0.939).
- The honest one-liner: *an explicit schema's payoff is largest for values the model must compute and
  commit, and for a model fine-tuned to the schema's vocabulary; for surfacing raw facts, "summarize
  it" plus a strong reader is surprisingly hard to beat.*
