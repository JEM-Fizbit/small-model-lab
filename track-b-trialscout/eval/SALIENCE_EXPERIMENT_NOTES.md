# Salience experiment — running notes (for the article)

Working notes on testing the claim: *a generic LLM asked to free-form summarize and
self-select the salient features will miss what a domain expert deems important; an
expert-designed extraction schema injects that judgment and gets closer to the correct
answer.* (The illustrative "~80% free-form vs ~95% schema" claim.)

All runs are on the **base** model (`Qwen3-4B-Instruct-2507-4bit`, no fine-tuning) — the claim
is about *generic* LLMs. Fine-tuning would bake in the very domain judgment we hypothesize the
model lacks, so it's excluded by design.

---

## The conceptual distinction this experiment turns on

Three different things one could measure; they are easy to conflate:

1. **Information recoverability** — can a strong reader dig the needed facts out of the output?
   Flatters free-form: a capable judge mines structure from prose, and can classify entities the
   model merely name-dropped (e.g. "Enterome" → biotech) using outside knowledge.
2. **Salience capture** — when the model chooses what to say, does it *volunteer* the
   expert-critical facts, or omit/bury them? Omissions are penalized; no rescue.
3. **Schema validity** — is the expert schema the right definition of "what matters"? *Granted,
   not tested.* The claim presupposes the schema encodes domain judgment.

The claim is about **(2)**. 

## Round 1 (flawed) — what NOT to do, and why it's instructive

`compare_schema_vs_freeform.py` scored **both** arms by having a strong Claude judge re-extract the
7 schema fields from each output and grading against the same gold. Result: free-form *beat* schema
overall (0.755 vs 0.711, n=150, base model).

Why that does not test the claim:
- It **graded the free-form arm against the schema too** — so it presupposed the schema as ground
  truth in *both* arms and could never ask whether self-chosen salience differs from the schema.
- It **let the judge rescue free-form**: credit was given for facts that were merely *recoverable*
  (a named sponsor the judge classified from its own knowledge), not facts the model *judged
  important enough to state*. That measures **(1) recoverability**, not **(2) salience**.
- The one signal that leaked through and *did* point at the claim — `est_readout` 0.83 → 0.22, the
  model omitting the readout window when left to choose — was **averaged away** in the aggregate.

Meta-note worth keeping for the article: reaching for the tractable proxy (field-recovery accuracy,
harness already built) over the salient measurement (does free-form miss what matters) is *itself*
an instance of the failure mode the claim describes — optimizing the measurable over the meaningful
with no judgment about which is which.

## Round 2 (this run) — measuring salience capture

Same raw model outputs as Round 1 (reused verbatim — only the scoring changes, so the measurement
regime is the sole variable). The free-form output is judged **conservatively, gold-blind, no
rescue**:

- The judge sees **only the writeup** (never the trial record, never the gold answer) and extracts
  each field **only if the writeup explicitly states it or an unambiguous paraphrase**.
- **No entity classification from outside knowledge**: if the summary names a sponsor/drug but does
  not state its *type/class*, that field is `NOT_STATED` (an omission), not a rescue.
- Each field resolves to one of: **stated-correct / stated-wrong / not-stated (omitted)**.

The schema arm goes through the *same* extractor for symmetry (its JSON states the values, so it
rarely omits; its failures are wrong-value/wrong-vocab). Both arms then score with the same
`harness.score` so the headline numbers stay comparable to Round 1's 0.711 / 0.755.

The decisive quantity is the **omission decomposition** of free-form's errors: if the claim holds,
free-form's accuracy gap vs schema should be driven by *not-stated* (the model didn't know to
include it), concentrated in the **judgment-heavy** fields (risk_flags, est_readout, modality),
while the schema arm's coverage of those is ~complete because it was explicitly asked.

### Measurement pitfalls hit along the way (each is itself article material)

Getting a *fair* salience measurement took three tries, and the failures mirror the thesis:

1. **Scoring the schema JSON with a prose extractor** marked stated-but-wrong-vocab values
   (`"sponsor_type":"INDUSTRY"`, `"est_readout":"2029-05-30"`) as *omissions*. Wrong: the schema
   arm *did* address those fields. Fix → normalize any stated value (incl. date→half-year)
   instead of dropping it; omission applies only to truly-absent fields.
2. **A lenient normalizer "rescued" the free-form arm**: told to "capture what the output conveys,"
   the judge classified *named entities* from its own knowledge ("Enterome" → biotech) even though
   the prose never stated a type. This inflated free-form `sponsor_type` from 0.42 → 0.75. Caught by
   auditing "correct" cases against the raw prose (no type-cue words present).
3. **Resolution** — for the entity/derived fields, trust a **deterministic, judge-free surface
   check** (does the prose physically contain a year / a sponsor-type word?) over any judge. An
   automated reader keeps wanting to *supply* the missing judgment — the exact failure the schema
   exists to prevent.

### Results — Round 2 (base Qwen3-4B, n=150)

**Judge-free surface omission on the free-form prose (the robust core finding):**

| field | free-form OMITS it (no surface mention) | schema addresses it |
|---|---|---|
| readout window (`est_readout`) | **92%** (138/150) | 100% (JSON always emits the field) |
| sponsor **type** (`sponsor_type`) | **62%** (93/150 — names the sponsor, never its type) | 100% |

**Normalized accuracy (same normalizer both arms; entity fields judge-sensitive — see pitfall 2):**

| field | schema acc | free-form acc | free-form failure mode |
|---|---|---|---|
| overall | 0.57 | 0.66 | — |
| phase | 0.95 | 0.98 | ~none (lookup) |
| primary_endpoint_type | 0.85 | 0.89 | ~none (usually stated) |
| modality | 0.36 | 0.68* | 0% wrong but **53% omitted** in strict run |
| sponsor_type | **0.07** | 0.75* | **62% omitted** (deterministic); schema **93% wrong-vocab** |
| est_readout | **0.67** | **0.04** | **92–95% omitted** |
| risk_flags (set-F1) | 0.51 | 0.62 | discusses risks 94%, but flags differ |

\* judge-inflated by entity rescue; the deterministic omission rates above are the trustworthy figures.

### Synthesis (for the article)

1. **The thesis holds in its mechanism, and the proof is judge-independent.** Asked to summarize and
   self-select salience, the generic model **silently drops the decision-critical fields** — the
   readout window (92% of the time) and the sponsor's type (62%). It writes fluent investor narrative
   ("high-potential early-stage opportunity") while omitting *when it reads out* and *who's funding it
   at what risk profile* — exactly the fields a domain expert pre-commits in a schema. The schema's
   first benefit is **coverage**: it forbids the silent omission.

2. **But the simple "80 vs 95" accuracy ordering does NOT hold for a generic model — and the reason
   is the deeper point.** Forcing the schema makes the model *address* every field, yet the generic
   base model then *answers the judgment fields wrong* (sponsor_type 0.07, modality 0.36) because it
   lacks the controlled vocabulary and domain rules — it emits "INDUSTRY", "Vaccine", a raw date.
   Net, the schema arm (0.57) does not beat free-form (0.66) overall on a generic model. **The schema
   forces the question; the generic model still can't answer it.**

3. **The schema is necessary but not sufficient — the missing piece is exactly the human domain
   judgment.** The 95%-style number appears only when that judgment is *baked into the model*: the
   fine-tuned student scores **0.922** schema'd on this same test set. So the expert schema encodes
   *what* matters (and demonstrably the model won't volunteer it); getting it *right* additionally
   needs encoding *how to answer* — the expert-in-the-loop vocabulary/rules, then distillation. That
   is the argument for the whole TrialScout pipeline, not just the prompt.

**One-line for the essay:** a generic LLM left to "summarize what matters" silently omits the
decision-critical, judgment-heavy fields (readout window 92%, sponsor type 62%); an expert schema
closes that coverage gap by construction — but on a *generic* model it trades omissions for
wrong-vocabulary answers, so the schema's full accuracy payoff only lands once the expert's domain
judgment is trained into the model.

