# Decision Log (ADRs)

Locked design decisions with rationale. Newest at top. This file is also part of the **learning trail** — each entry explains not just *what* we chose but *why*, so the reasoning isn't a black box.

---

## ADR-0017 — Schema v2: `modalities` is a list, `intervention_class` is a field, and the v1 measurement is committed

*Decided 2026-08-10. Implements the fix ADR-0016 recorded but deliberately did not make, and goes
further than it proposed: designing the replacement surfaced two defects worse than the one we set
out to fix.*

**Decision:** Replace the single-valued `modality` enum with a list-valued **`modalities`**, drawn
from a 14-value taxonomy anchored on published industry conventions, and add a scalar
**`intervention_class`**. Drop `combination` entirely. Move external-beam radiotherapy out of the
modality vocabulary and split `radiopharmaceutical` in as a real drug modality. Regenerate gold
under the new schema rather than relabelling the old (ADR-0011's rule: relabelling moves goalposts).
Commit the v1 measurement as a frozen, runnable record.

### The two defects we didn't know about

ADR-0016 diagnosed `combination`. Checking the corpus against ClinicalTrials.gov intervention types
while designing the replacement found worse:

- **117 of 1,500 trials (7.8%) have no drug intervention at all** — no `DRUG`, `BIOLOGICAL`,
  `GENETIC` or `COMBINATION_PRODUCT`. (That is the mechanical count from the intervention types.
  The regenerated gold puts the true figure more than twice as high — **251, 16.8%** — because many
  trials carry a `DRUG` that is not *anticancer* therapy: antiemetics, a PET tracer, a skin cream.
  See the Outcome below.) They are surgical-technique trials, radiotherapy-fractionation
  trials, devices, behavioural and supportive-care studies. Real examples the teacher was obliged to
  assign a *drug modality* to: *laparoscopic D2 radical gastrectomy*, *pancreaticojejunal
  anastomosis*, *hyperbaric oxygen*, *chlorhexidine skin cleanser*, *cutting scalp hair*. The
  question has no correct answer for these, so the teacher invented one. 63 landed in `other`, 45 in
  `radiotherapy`.
- **`radiotherapy` conflated two unrelated things.** 65% of that bucket is external-beam technique —
  not a drug, no asset, no P&L — mixed with genuine radiopharmaceuticals (*Ultratrace Iobenguane
  I-131*). To an analyst those could not be further apart.

A third issue is utility rather than correctness: 61 of the 599 `small molecule` rows were
cytotoxic-chemotherapy-only regimens. Chemically correct, commercially useless — nobody in the
industry files carboplatin and a patented targeted inhibitor under one heading.

**So `combination` was the visible symptom of a broader fault: the field collapsed three orthogonal
axes into one.** What kind of molecule (modality), how many agents (combination), and what kind of
intervention (drug vs procedure vs device vs radiation) are separate questions everywhere in the
industry, and were one question here.

### Why this taxonomy, and not one we invented

The v1 enum was designed from first principles, which is how it acquired a value that isn't a
modality. The replacement is anchored on how the industry actually classifies:

- the **small-molecule / biologic** split that organises regulatory pathways (CDER NME vs BLA) and
  the [BIO/Citeline/QLS success-rate work](https://www.bio.org/clinical-development-success-rates-and-contributing-factors-2011-2020);
- **biologic subtypes** as formalised by [WHO INN nomenclature](https://www.who.int/publications/m/item/inn-22-542) —
  `-tug` monospecific, `-bart` engineered constant regions, `-ment` fragments, `-mig`
  bispecific/multispecific;
- the **ATMP classes** [EMA defines in law](https://www.ema.europa.eu/en/human-regulatory-overview/advanced-therapy-medicinal-products-overview) —
  gene therapy, somatic cell therapy, tissue-engineered, combined;
- the emerging buckets analysts track separately — ADCs, multispecifics, cell and gene therapy at
  [35% of oncology trials per IQVIA](https://www.iqvia.com/insights/the-iqvia-institute/reports-and-publications/reports/global-trends-in-r-and-d-2025),
  plus radioligand therapy, which [*Nature Reviews Drug Discovery* treats as its own modality](https://www.nature.com/articles/d41573-025-00096-w)
  precisely because it is a systemic tumour-seeking molecule, the opposite of irradiating a field
  from outside the body.

Two values were added on evidence from this corpus rather than from the literature:
`hormonal/endocrine therapy` (41 trials — more common here than `bispecific`, which already had a
value) and `oligonucleotide/RNA therapeutic` (only 4 trials, kept because it is a top-tier modality
industry-wide and the vocabulary should outlive this dataset). Protein degraders (2 trials) were
*not* given a value; they are small molecules and fold into `targeted small molecule`.

**Rule-reducibility was a design constraint, not an afterthought.** The classification keys on three
signals present in the record: CT.gov's controlled `intervention.type` vocabulary, INN stems, and
explicit class words. Testing the stems against the corpus found they match **21% of unique
intervention names** (`-mab` 412, `-tinib` 201, `-zomib` 31, ADC stems 22) — decisive where present,
absent four times in five. So they are written into the teacher rule as tiebreakers, not as the
classifier.

### Why not `agent_count` or `primary_agent`

ADR-0016 floated both. Neither survives contact with the problem it is meant to solve.
**`agent_count`** recreates the original ambiguity under a new name: counting agents means deciding
which are investigational and which are backbone, and whether a placebo or an imaging tracer counts
— the same judgement, relocated, and now scored as if it were a fact. **`primary_agent`** would be
free text, so it needs a judge to score, and it duplicates information the caller already has: the
agent names are in the record they passed in.

`intervention_class` is the opposite kind of field, which is why it earned a place. It maps from a
controlled vocabulary already in the input, it answers the first question an analyst actually asks
("is there an asset here?"), and it is what lets `modalities: []` mean *no drug* rather than
*the model didn't answer*.

### Design details that are load-bearing

- **The list is explicitly unordered and alphabetically sorted**, in gold, in the normalizer and at
  inference. The tempting alternative — lead agent first — smuggles the "which one is primary?"
  judgement back in as list order, where set-F1 would not score it. An unscored assertion is worse
  than no assertion.
- **Backbone and comparator agents are included.** A trial of an ADC plus carboplatin returns both.
  This is the clause that removes the judgement: no one has to decide what the "real" agent is.
- **Scoring reuses `risk_flags`' set-F1.** No new machinery. The consequence is stated wherever the
  number appears: set-F1 gives partial credit where v1's accuracy gave none, so a v2 overall and a
  v1 overall are **different measurements that share a scale**, not an improvement.
- **A missing `modalities` key scores zero; an explicit `[]` is a valid answer.** Both look like an
  empty list to `.get(field, [])`, and conflating them would hand free marks to a broken output on
  exactly the 8% of trials that have no drug.

### The latent trap this also fixed

The 80/10/10 split was produced by `random.Random(42).shuffle()` over rows read back from
`all.jsonl` — a file written in `ThreadPoolExecutor` **completion order**. It looks deterministic and
is not: every fresh teacher run silently reshuffles the corpus into a different "frozen" test set.
Nobody would have noticed; the docs would still have said 150 held-out trials. The assignment is now
committed as `data/splits.json` and read, never re-derived.

### Committing the v1 record — a deliberate exception to the no-data rule

`.gitignore` excludes datasets because they are *regenerable from scripts*. The v1 gold is not, for
two independent reasons: the split was never reproducible (above), and the teacher moves (ADR-0018).
Meanwhile the v1 figures are cited on the public walk-through and in outside writing, and were
**checkable by nobody** — gold and adapters are gitignored, so a reader could not recompute 0.922 at
all.

`eval/v1-frozen/` therefore commits 316 KB: the 150-trial test gold, the raw predictions, the v1
harness, schema and normalizer, and `verify_v1.py`, which re-derives the entire published table and
exits non-zero on drift. No model, adapter, API key or network needed. The adapter itself stays
local, with its SHA-256 in `MANIFEST.json`. Recomputing the scores from the predictions needs only
what is committed; regenerating the predictions needs the adapter.

This makes the published numbers *more* verifiable than before the change, which is the standard a
schema migration on a teaching artifact should meet.

### Outcome (measured 2026-08-10)

Gold regenerated (1,492/1,500 valid, $11.87), student retrained on the identical v1 recipe
(1,192 rows, 700 iters, seed 0; val loss 0.656 → **0.570**), everything re-scored on the **same
150 test trials** — the pinned split held, so the trials are identical to v1's.

| arm | overall | what it isolates |
|---|---|---|
| majority floor | 0.476 | always guess the most common value |
| untuned Qwen, training prompt | 0.121 | never told the enum vocabularies |
| untuned Qwen + enum list | 0.697 | same model, menu supplied, nothing else |
| frontier zero-shot (Sonnet 5) | 0.897 | frontier, schema only, no scaffold |
| **fine-tuned student** | **0.939** | valid JSON 1.000 |

**Telling the base model the allowed values is worth +0.576** (0.121 → 0.697) — more than everything
fine-tuning adds on top (+0.242). Most of what reads as "the small model can't do this" was "nobody
told it what the answers may be." Independent corroboration that 0.697 is the right number for that
arm: v1's published untuned figure, obtained by a completely different route (a Claude judge reading
the model's prose), was 0.711.

**The student beats the frontier arm, 0.939 vs 0.897** — but the win is entirely convention-following
on common cases, and it inverts on the tail. Macro-F1 over modality labels: student **0.653**,
frontier **0.805**. ADC recall 0.40 vs 1.00, oncolytic virus 0.33 vs 1.00, bispecific 0.00 vs 0.50.
Distillation transferred the *conventions* — the H1/H2 rule, the sponsor taxonomy, the
chemo-vs-targeted split — and not the *pharmacology*, because 1,192 examples contain only a handful
of each rare class. "A 4B model beats a frontier model" is true of the average and false of the tail.

**Was the ambiguity fixed or relocated?** Fixed, about two-thirds of it. Modality errors that are a
*how-many* dispute fell from **20 of 34 (59%)** under v1 to **12 of 33 (36%)**. The strictest
comparable measure, exact-set accuracy, is 0.780 against v1's 0.773 — while answering a harder
question on a corpus where 16.8% of trials now correctly return an empty list.

**What the regeneration cost elsewhere.** Measured against v1 gold on the same 1,492 trials: `phase`
0.995, `sponsor_type` 0.985, `est_readout` 0.977 — stable. `primary_endpoint_type` 0.905.
`risk_flags` **0.298 exact / set-F1 0.837** — it moved enormously, for teacher reasons rather than
schema reasons (ADR-0018).

**An unplanned finding.** The `other` bucket of `intervention_class` exposed ~12 trials in the corpus
that are not oncology at all — asthma, oral contraceptives, PCOS fertility studies. v1 hid them by
assigning each a drug modality. A data-pull defect, logged rather than fixed here.


---

## ADR-0019 — Rare-modality augmentation failed again, and this time we know why: the test set can't see it

*Decided 2026-08-10, immediately after ADR-0017. Second attempt at the same experiment ADR-0011
ran under schema v1, with the confound removed and a frontier control added.*

**Decision:** Do **not** promote `adapters/qwen_v2s_aug`. The production reference stays
`adapters/qwen_v2s`. The relabelled 299-trial augment is kept (`data/gold/augment_rare.jsonl`,
Sonnet 5, schema v2, $2.46) because it is sound data and the next experiment needs it.

**The setup.** ADR-0017 left `modalities` strong on common classes and weak on rare ones — ADC recall
0.40, oncolytic virus 0.33, bispecific 0.00 — while the frontier model scored 1.00 on the first two
from the same records. That control is what made this worth running: the signal is provably in the
input, so a failure to learn it is about training, not about the data being uninformative. The 300
rare-modality trials from ADR-0011 were relabelled under v2 and merged into train only
(1,192 → 1,491 rows). Val/test frozen, hyperparameters identical, seed identical. Only the data moved.

**Result: nothing.** Overall **0.939 → 0.939**. Val loss did improve (0.570 → 0.460, and still
descending at iteration 700 where the un-augmented run had turned upward at 600), so the extra data
was learnable — it just did not land where it was aimed.

| | no augment | +augment | frontier |
|---|---|---|---|
| overall | 0.939 | 0.939 | 0.897 |
| modalities set-F1 | 0.870 | 0.854 | 0.859 |
| modalities exact-set | 0.780 | 0.740 | 0.760 |
| **modalities macro-F1** | 0.653 | **0.569** | 0.805 |

| modality | train rows | test n | recall before | after | frontier |
|---|---|---|---|---|---|
| antibody-drug conjugate | 32 → 74 | 5 | 0.40 | 0.40 | 1.00 |
| oncolytic virus | 12 → 63 | 3 | 0.33 | 0.33 | 1.00 |
| bispecific | 29 → 79 | 2 | 0.00 | 0.00 | 0.50 |
| other protein or peptide | 106 → 127 | 10 | 0.20 | **0.50** | 0.60 |

**The mechanism, measured rather than guessed.** The obvious hypothesis was distribution shift — a
training set over-weighted toward rare classes making the model trigger-happy. That is **not** what
happened: net rare-class predictions changed by **+0**. What changed was precision on the classes
that got more data. ADC predictions went 2 → 4 while true positives stayed at 2 (precision
1.00 → 0.50); oncolytic 1 → 2, true positives stayed 1. **More examples of a class taught the model
that the class exists more often, not how to recognise it.** Recall could not move because correct
answers did not increase — only wrong ones did.

**The finding that actually matters, and it is methodological.** This experiment cannot resolve what
it was built to measure. The frozen test set holds **5 ADCs, 3 oncolytic viruses and 2 bispecifics**,
so one trial is worth 20, 33 and 50 recall points respectively. "0.40 → 0.40" is 2/5 both times. We
cannot distinguish *no effect* from *a real effect* at these sample sizes, and no amount of extra
**training** data changes that, because the constraint is **test** support.

The one class that did move is the tell: `other protein or peptide therapeutic` has **n=10**, the
largest test support among the weak classes, and it is the only one that showed a clear improvement
(recall 0.20 → 0.50, precision 0.29 → 0.62). That is consistent with augmentation working and being
invisible everywhere the test set is too thin to show it.

A prediction was registered before the run and was **wrong in the informative direction**: oncolytic
virus and bispecific were expected to gain most (5.2× and 2.7× more data) and `other protein or
peptide` to stay flat because its problem was definitional rather than scarcity. The opposite
happened, and the reason is test-set support, not the quality of the reasoning about the categories.

**Consequences.**

- ADR-0011 reached "rare-class augmentation is a wash" and attributed it to teacher-label noise.
  ADR-0016 attributed the remainder to rarity. Both were reasoning about a measurement that was
  never sensitive enough to answer the question. **The wash was in the instrument.**
- Measuring tail performance needs a **rare-class-enriched diagnostic set**, held separately from the
  headline test set, which must stay frozen and representative. Roughly 30–50 trials per rare class,
  teacher-labelled once, scored as a named diagnostic rather than folded into the overall. That is
  the actual next experiment.
- `other protein or peptide therapeutic` remains a badly-drawn category (127 training rows, recall
  0.50, the worst ratio of support to performance in the schema). Splitting it — fusion protein /
  cytokine / enzyme — is a schema-v3 candidate.
- The general lesson, and it generalises past this repo: **before running an experiment to improve a
  metric, check whether the metric can move.** A frozen representative test set is the right
  instrument for a headline score and the wrong one for a long tail, and the failure mode is
  indistinguishable from "the intervention didn't work."

---

## ADR-0018 — Teacher upgraded to Sonnet 5; determinism became something we measure, not request

*Decided 2026-08-10, during the schema-v2 regeneration (ADR-0017).*

**Decision:** The teacher is now **`claude-sonnet-5`**, replacing `claude-sonnet-4-6`. The request
shape is per-model and the cost cap reads per-model pricing. Label stability is no longer asserted
from `temperature=0` — it is **measured** by relabelling the same trials twice and reporting the
agreement.

**Why change a teacher mid-project.** ADR-0007 did not choose *Sonnet 4.6*; it chose *a strong
teacher*, on the ADR-0003 principle that teacher quality caps student quality. In June 2026 that
resolved to Sonnet 4.6 because it was the best available. Applying the same rule in August 2026
gives Sonnet 5. Keeping 4.6 would have been fidelity to an accident of timing rather than to the
decision — and on a project whose central claim is *a small fine-tuned model approaching frontier
performance*, a teacher one generation behind quietly weakens the claim every month it ages. Gold
was being regenerated anyway for the schema change, which made this the one cheap moment: doing it
later means paying for a second full teacher run.

**What it cost in code.** The current model family removed the sampling parameters — `temperature=0`
now returns HTTP 400 — and adaptive thinking shares the `max_tokens` budget with the response, so the
old 700-token ceiling could truncate a readout before the tool call was emitted. Request shape moved
into one `request_kwargs()` function, and `PRICING` became per-model. That second part matters more
than it looks: the cap aborts a paid run when the *running estimate* reaches it, so an over-stated
price halts a job partway through. Accurate beats conservative for a guardrail that can misfire.

**The determinism question, answered with data instead of a parameter.** ADR-0007 justified
`temperature=0` as "makes labels consistent". With no such knob available, the honest move is to
measure. Two runs over the same 40 boundary-stressed trials:

| field | Sonnet 4.6, temp 0 | Sonnet 5, no temp knob |
|---|---|---|
| `intervention_class` | 40/40 | 40/40 |
| `modalities` | 38/40 exact · set-F1 0.988 | **39/40 exact** · set-F1 0.975 |
| `est_readout` (vs the stated rule) | 36/36 | 36/36 |
| phase / endpoint / sponsor | 40/40 | 40/40 |

Losing `temperature` cost nothing measurable. The knob was never what produced the stability.

**The finding worth keeping: a better model followed the rule less.** Sonnet 5 initially mapped
`2014-05-21` to `"H2 2014"`. May is nowhere near the June boundary — it was overriding the explicit
*months 01–06 → H1* instruction with its own domain reasoning, adding a realistic lag between trial
completion and results being reported. Raising effort from `low` to `medium` made it do this
**consistently** rather than intermittently: more thinking produced a more confidently
non-compliant answer. The fix was one sentence ("a MECHANICAL mapping, not a forecast; do not add a
reporting lag"), verified at 36/36 across two runs.

The generalisable version, and it is the same lesson as ADR-0016 from the other direction: **when a
capable model disagrees with your spec, check whether it is wrong or whether your spec is
under-written.** Here the model's reading was arguably the more useful one; it was wrong only
because our scorer defines correctness as the mechanical mapping. An instruction that survives a
weaker model can fail against a stronger one, because a stronger model is likelier to notice that
your rule is a simplification and to improve on it.

**A second finding, unrelated but surfaced by the same probe: `risk_flags` is the noisiest field in
the schema, and nothing in the repo said so.** Teacher self-consistency is only ~28/40 exact
(set-F1 ~0.93) for *both* teachers, and cross-teacher agreement is 12/40 (set-F1 0.801). It is
published at 0.884 — meaning the student is graded against a target that disagrees with itself about
as much as the student disagrees with it. That is not caused by the teacher change; the teacher
change is only how it became visible. Recorded here rather than buried because any future reading of
`risk_flags` 0.88 should know the ceiling is not 1.0.

**Consequences.**

- Gold is now Sonnet 5 output; `eval/v1-frozen/` remains Sonnet 4.6 output and is labelled as such.
- The frontier comparator (`eval/frontier_arm.py`) uses the same model as the teacher, which makes it
  a clean *scaffold ablation* — same model, schema only, no rules or worked examples — rather than an
  independent referee. It bounds what the prompt engineering is worth; it cannot validate the labels.
- `PRICING` in `make_gold.py` carries Sonnet 5's introductory rate and **must be updated after
  2026-08-31**, when it reverts to $3/$15.
- The Phase-4 rare-modality augment (ADR-0011) was **not** relabelled. It remains v1-convention,
  Sonnet 4.6 data, and `format_for_mlx.py` now refuses to merge it rather than silently training on
  two conventions at once.

---

## ADR-0016 — The `modality` enum was mis-specified: most of its residual error is ours, not the model's

*Recorded 2026-08-08, while fact-checking an essay against this repo. Refines ADR-0011, which
attributed the `combination` boundary to "partly irreducible teacher-label noise" — accurate as far as
it went, but it located the fault in the labelling rather than in the schema that forced it.*

**Decision:** Record that `modality` as specified is not fit for reuse, and that any production use of
this readout schema should make the field list-valued before anything else is tuned. The shipped
artifacts are **not** changed: gold stays frozen, `adapters/qwen` remains the reference, and the
published numbers stand.

**What's wrong.** The enum mixes two different kinds of thing: ten genuine modalities (`small molecule`,
`monoclonal antibody`, `antibody-drug conjugate`, …) plus `combination`, which is not a modality but a
statement about *how many* modalities are present. The rule patching that seam — *"use `combination`
only when two distinct modalities are co-equal"* — asks for a judgement that is not a property of the
drug. Most oncology trials test more than one agent, so the question is live on a large share of the
corpus and has no stable answer.

**The evidence.** On the frozen 150-trial test set, `adapters/qwen` makes 34 modality errors. **Eleven of
them — a third — are that single boundary, and they run in both directions**: 6 × gold `combination` →
predicted `small molecule`, 5 × the reverse.

> **Correction (2026-08-10, while implementing the fix).** Eleven is the count for the
> `combination ↔ small molecule` pair alone. Counting every error with `combination` on *either*
> side, it is **20 of 34 — 59%, not a third**: add 4 × gold `combination` → `monoclonal antibody`,
> 2 × the reverse, and 3 others. The entry understated its own case. Reproduce with
> `eval/v1-frozen/` (`gold_test.jsonl` vs `preds_qwen.jsonl`).

Two worked cases show why neither side is obviously wrong:

- **NCT00496301** — gemcitabine + capecitabine + sorafenib. Three drugs, but all one modality, so gold
  says `small molecule`; the model said `combination`, applying the everyday sense of the word.
- **NCT02406781** — pembrolizumab (antibody) + cyclophosphamide (small molecule). Two modalities, so gold
  says `combination`; the model said `small molecule`.

**NCT05063604** (citalopram vs psychotherapy) appears to be a *teacher* error in the other direction:
gold `combination`, where psychotherapy is not a drug modality at all. The student was marked wrong for
being right.

**Why this matters beyond this field.** A share of what presented as model error was specification error.
The teacher wasn't careless; it was over-constrained by a schema that admitted no correct answer, and the
student then reproduced the inconsistency faithfully — which is exactly what distillation is supposed to
do. The generalisable check: **when a model contradicts itself at a category boundary, test whether your
own taxonomy drew that boundary before concluding the model is weak.**

**Separately — and don't conflate the two — the rest of `modality`'s weakness is rarity, not ambiguity.**
Macro-F1 (0.57) sits far below accuracy (0.773) because of the long tail: ADC n=5 recall 0.40, monoclonal
antibody n=10 recall 0.50, gene therapy n=1 recall 0.00, while cell therapy (6/6), cancer vaccine (5/5)
and oncolytic virus (1/1) are perfect. That half **is** fixable with data, and ADR-0011's Phase-4 run
showed it — ADC 0.40→0.60 — even though the overall score was a wash.

**The fix, when it's wanted:** `modalities: ["small molecule", "monoclonal antibody"]` as a list, dropping
`combination` entirely; add `primary_agent` or an agent count separately if the readout needs it. **Do not
retro-label the existing gold** — that moves goalposts against a frozen test set. A schema change means
regenerating gold and re-running the eval end to end, which is why this is recorded as a decision rather
than done in passing.

### Outcome (2026-08-10) — acted on, and the diagnosis was two-thirds right

Superseded in full by **ADR-0017**, which rebuilt the field, and **ADR-0018**, which changed the
teacher. What this entry got right, wrong, and missed:

- **Right, and confirmed:** `combination` was a specification error, not model weakness. Removing it
  cut *how-many* disputes from 59% of modality errors to 36%. Roughly two-thirds of what ADR-0011
  called "irreducible teacher-label noise" was our own schema.
- **Right, and still unfixed:** the rarity half. ADC recall is **0.40 — identical to v1**, bispecific
  0.00, oncolytic virus 0.33. The frontier model scores 1.00 on the first and third, which proves
  these are learnable and that the gap is training data, not a ceiling. Exactly as this entry
  predicted, and the obvious next move.
- **Understated:** the evidence, corrected inline above — 20 of 34 errors, not eleven.
- **Missed entirely, and worse than what it found:** `modality` was being asked of trials with no
  drug. **251 of 1,492 (16.8%)** test a surgical technique, a radiotherapy schedule, a device or
  supportive care, and the schema forced a drug modality onto every one. `radiotherapy` was also
  65% external-beam technique — not a drug modality at all — mixed with real radiopharmaceuticals.
  This entry looked hard at one bad enum value and did not ask whether the field was being asked of
  the right trials.

The generalisable lesson survives intact and gains a second half. The original: *when a model
contradicts itself at a category boundary, test whether your own taxonomy drew that boundary.* The
addition: *and check whether the question applies to every row you are asking it of.*


---

## ADR-0015 — Two repos: a public teaching artifact, a private workshop nested inside it

*Decided 2026-06-08; recorded here 2026-08-04. The split was documented in `CLAUDE.md`,
`AGENTS.md` and the private README but never in this log — which made "why are there two
repos?" a question you had to answer from three files.*

**Decision:** Split the project across two repositories on the second day of its life.
Public **`small-model-lab`** holds the teaching artifact: `notebooks/`, the
`docs/walkthrough/` builder and site, the Track B pipeline, this decision log, `README.md`.
Private **`small-model-lab-private`** holds the working scaffolding: the live `BACKLOG.md`
(including business and strategy notes), `HANDOFF.md`, the full agent contract with personal
framing, and `specs/`. The private repo is cloned into `_private/` **inside** the public
working tree and gitignored there, so the two live together on disk with independent
histories.

**Why split at all — audience, not secrecy.** Nothing in the private repo is confidential in
an interesting way. It is simply *for a different reader*. The public repo is a **product**
someone lands on from a link and reads end to end; the private one is the **workshop** —
what to build next, why it might matter commercially, where the last session stopped. That
material makes the public artifact worse, not better: it dates instantly, it presumes
context the reader does not have, and it turns a clean teaching resource into somebody's
project-management residue.

**Why nested rather than a sibling directory.** Co-location without leakage. An agent (or a
returning human) resuming work reads `_private/HANDOFF.md` and `_private/BACKLOG.md` from
the same working directory as the code they describe, with no second checkout to know about
and no relative paths climbing out of the tree. `.gitignore` guarantees the public repo can
never carry it. The cost is one non-obvious rule: `_private/` is a separate repo and must be
committed from inside it.

**Why so early.** 2026-06-08 was two days after project init and four days before the first
public promotion. Separating cleanly is trivial at that point and progressively harder
afterwards: the same day, the public history had to be **rewritten** to purge internal
content that had already accumulated across its first commits. Doing it once, before anyone
was watching, is why it stayed cheap.

**Consequences, including the one that bites.**

- **Absolute local paths are forbidden in the public repo** — they identify a person and a
  machine. This is enforced socially rather than mechanically, and it has failed at least
  once since: notebook 02's save cell printed `/Users/…` into a committed output (fixed in
  the same session that recorded this ADR).
- **`git status` at the public root does not see the private repo.** Uncommitted private
  work is invisible from where you normally check, so "is everything committed?" is two
  questions, not one. This caught us on 2026-08-04: session notes sat untracked in
  `_private/` while the public tree reported clean.
- **Decisions live public, status lives private.** This log is deliberately public — the
  *why* trail is part of the teaching artifact. Anything mutable (what's next, what's
  blocked) belongs in `_private/BACKLOG.md` instead.

**Alternative not taken:** a single repo with a private branch or a scrubbing pre-commit
hook. Both put internal content one mistake away from publication, and neither survives a
`git push --all`. Two histories cannot leak into each other by accident.

## ADR-0014 — Retrained the Track A checkpoint and regenerated every derived artifact

**Decision:** Reversed ADR-0013's "do not retrain". Retrained Track A on the repaired,
seeded data path (2026-08-04) and regenerated all twelve derived surfaces. Added
`scripts/regenerate_track_a.py` to do it in the right order, `TRACK_A_MANIFEST.json` to
record provenance, and generators for the three figures that had none.

**Why the reversal:** ADR-0013 declined the retrain on a cost estimate of "six artifacts".
Measuring instead of estimating found **twelve**, and — the actual finding — **three of them
rendered real measurements with no script behind them** (`PROBS_SVG`, `TEMP_SVG`,
`ATTENTION_SVG`), plus a fourth (`TOKENIZE_SVG`) showing real token ids and a verbatim
generated story pasted into the prose. Those cannot go stale *loudly*; they just quietly
become false. That is a worse property for a learn-by-doing repo than any amount of
regeneration work, and it argued for fixing the tooling now rather than accumulating more
hand-typed measurements.

**What the retrain bought.** Mojibake emitted in generated samples: **1/40 → 0/40**; the 28
mojibake merges are gone and the vocabulary now contains merges for *real* curly punctuation
instead. Quality is unchanged — bits-per-byte on 300 held-out stories (offset 30,000, unseen
by both, normalised so the different tokenizers are comparable) goes **0.6509 → 0.6526**,
0.3%, well inside run-to-run noise. Notebook 02's own run improved slightly (val 2.214 →
2.168). So: the artifact is gone and nothing was paid for it.

**What survived, and what had to be re-picked.** Two figures encode *editorial* claims that a
retrain can silently break, so both are now checked on every run rather than assumed:

- `GENLOOP_SVG` exists to show sampling refusing the favourite. Seed 3 still does it
  (` boy` at 19.5% over ` girl` at 72.5%) and lands on the same closing sentence, so the
  narrative is unchanged. `gen_generation_trace.py --hunt` re-derives a seed when it breaks;
  the script now **exits rather than emit a figure that contradicts its own caption**.
- `ATTENTION_SVG` claims layer 2 / head 4 tracks the sentence's referent. It still does
  (dragon 43%, clear of `it` at 27%), so the subtitle is unchanged — but only 2 of 36 heads
  qualify now, and against an interim checkpoint the qualifying head was a different one
  entirely. `--hunt` re-picks it; the script refuses to run if the claim is false.

**The ordering hazard, now enforced.** Notebook 02 and `train_v2_checkpoint.py` write to the
same checkpoint path but train different models (the notebook has no `<|endstory|>` token).
Running them in the wrong order silently ships a checkpoint that never stops generating —
which happened once during this work. Cell 19's markdown documented it; nothing enforced it.
`regenerate_track_a.py --derived` now **refuses to run against a checkpoint with no
end-of-story token**, and `--all` runs notebook 02 first by construction.

**Two bugs found by building the generators**, both pre-existing and now fixed: `TEMP_SVG`
drew the top 5 chunks but pooled "everything else" as `100 − top 6`, so its panels summed to
99.1% and 97.0% instead of 100%; and notebook 02's save cell printed an **absolute local
path** into a committed output, which this public repo forbids.

**Reproducibility caveat, restated because it is easy to over-claim:** the manifest's hashes
detect staleness, they are not byte-equality tests. Same seed ⇒ same experiment, not the same
bytes (ADR-0013).

## ADR-0013 — Repair TinyStories' mojibake and seed the trainer; do NOT retrain the committed checkpoint

> **Partly superseded by [ADR-0014](#adr-0014--retrained-the-track-a-checkpoint-and-regenerated-every-derived-artifact).**
> The data-path decisions below stand. The "do not retrain" call was reversed on 2026-08-04 once the
> full artifact inventory (ten surfaces, three with no generator) was actually measured rather than
> estimated. Factual corrections to the mojibake count and the reproducibility claim are inline below.

**Decision:** Track A's data path now (a) repairs double-encoded UTF-8 in the TinyStories text on
load and (b) seeds both RNGs the run depends on (`SEED = 1337`, `--seed` on the script). Applied in
`notebooks/train_v2_checkpoint.py` and mirrored into notebook 02 (cells 4 and 10). **The committed
`tiny_gpt_v2` checkpoint was NOT retrained**, so it — and every artifact derived from it — still
carries the mojibake. Retrain opportunistically, the next time something else already forces one.

**Why (the bug):** ~7.5% of TinyStories stories ship mojibaked — `daddyâ€™s tie` where `daddy's tie`
was meant — because the text was UTF-8 bytes decoded as CP1252 somewhere upstream. This is *not* our
loader: `train_v2_checkpoint.py` reads `ex["text"]` straight from `load_dataset` with no re-encoding,
and the tokenizer's decoder round-trips valid text cleanly. It arrives broken. At that prevalence the
byte-pairs recur often enough for the BPE to spend **28 of its 8,192 tokens** on mojibake fragments —
dedicated merges for the mangled forms of `"Mommy`, `"Hello` and ` couldn'` — and the model duly
emits them at generation time. Fixing the data is strictly better than post-processing the output:
the vocabulary is the thing being corrupted.

> **On counting mojibake tokens.** An earlier revision of this ADR said *73*. That number came from
> matching mojibake bytes against the raw **ByteLevel token strings**, where the byte `â` also begins
> every legitimate curly quote — so it swept up tokens that were fine. Counting tokens whose
> **decoded text** is mojibake gives **28**. Even that is approximate: mojibake spans several tokens
> and its characters (`–`, `—`, `'`) overlap real punctuation, so no purely lexical count is exact.
> The unambiguous measure is behavioural — mojibake emitted in generated samples, **1/40 → 0/40**
> after the fix. A useful confirmation that the repair worked rather than merely hid the problem:
> the retrained vocabulary now contains merges for *real* curly punctuation (`.”`, `,”`, ` “`) that
> the old one lacked.

**Why the repair is shaped the way it is:** most of the damage is *lossy*, not merely scrambled. A
right double quote (U+201D) is UTF-8 `E2 80 9D`, and CP1252 has no mapping for `0x9D`, so that byte
was dropped upstream — leaving a bare `â€` that no round-trip can reverse. That lossy variant is 5.5%
of stories against 2% losslessly reversible, so the repair restores the dropped byte first, then
reverses the encoding. It is deliberately conservative: any string that doesn't round-trip cleanly is
returned untouched, because corrupting good text is worse than leaving the bug in. Verified against
3,000 real upstream stories — **226 repaired, 2,774 byte-identical, 0 clean strings modified,
0 mojibake missed** — plus a unit table covering legitimate accents (`café`, `naïve`, `Zoë`), real
curly quotes, emoji, and empty input.

**Why seeding matters more than the mojibake:** the trainer had **no seeding at all** — neither
`mx.random.seed` (weight init) nor `np.random.seed` (batch order). A rerun therefore produced a
*different* model, which means the committed notebook outputs, loss curves and walk-through figures
could never be reproduced from the code that claims to generate them. For a repo whose stated
principle is "learnable — no black boxes," an unreproducible trainer is the more serious defect.

**What the seed actually buys — and what it does not.** Verified across fresh processes: the same
seed gives an identical weight-init fingerprint and identical batch indices, and a different seed
diverges. But seeding does **not** make the checkpoint bit-identical on Apple's GPU. Measured: two
seeded runs of 20 real optimizer steps agree to 10 decimal places on the first steps and then drift
in the last decimals, ending with different weights; the same test pinned to `mx.cpu` is bitwise
identical across runs. The cause is Metal kernels accumulating in nondeterministic order, not the
RNG. So the honest claim is **same seed ⇒ same experiment, not the same bytes**: curves, behaviour
and conclusions reproduce; a hash does not. Anything that needs byte-equality (a checksum test, a
"regenerate and expect an empty diff" CI gate) must not be built on this.

**What a retrain costs — the real inventory.** An earlier revision of this ADR said "six committed
artifacts". That undercounted. **Ten** surfaces derive from the checkpoint, in three tiers:

| tier | surface | regeneration |
|---|---|---|
| script-driven | notebook 03 outputs | execute cells 0–6 (cell 7 is an interactive REPL — must stay unexecuted) |
| script-driven | `WE_MATRIX_SVG` (`content_concepts.py`) | `gen_embedding_matrix.py` emits the whole SVG |
| script-driven | `DOMAIN_LIMIT_PROBE_RESULTS.md` | `gen_domain_limit_probe.py` — data auto, **verdict prose hand-written** |
| execution | notebook 02 outputs | execute the notebook (~45 min) |
| execution | `loss_curve_tuned.png` | notebook 02's plotting cell |
| semi-manual | `GENLOOP_SVG` (`content.py`) | generator prints JSON only; the 27k-char SVG is hand-assembled, and its seed is chosen to make a specific teaching point |
| **no generator** | `PROBS_SVG` | 6 hand-transcribed measured values |
| **no generator** | `TEMP_SVG` | 10 values, at two temperatures |
| **no generator** | `ATTENTION_SVG` | 6 values from **layer 2 of 6, head 4 of 6** (stated in the figure's own subtitle; 0-indexed layer 1 / head 3 in code) |
| root | the checkpoint itself | `train_v2_checkpoint.py` |

The last three are the trap: they render real measurements with no script behind them, so a retrain
silently falsifies them and nothing fails loudly. Any future retrain must regenerate all ten.

**Ordering hazard (documented, not enforced).** Notebook 02's save cell writes to the *same* path as
`train_v2_checkpoint.py` but trains without the `<|endstory|>` token, so running the notebook after
the producer downgrades the shipped checkpoint and silently disables stop-at-story-end everywhere.
Cell 19's markdown already warns about this and prescribes the fix (re-run the producer afterward) —
so the correct order is **notebook 02 first, producer second**, then regenerate everything else.

**Bonus, kept on purpose:** the mojibake is an unusually good teaching artifact for Part 1's own
thesis — the corpus is the model, down to its defects — so the probe results document it rather than
quietly erasing it.

## ADR-0012 — Renamed the project: slm-lab → small-model-lab

**Decision:** Renamed the repo, site, and all branding from `slm-lab` to `small-model-lab` on 2026-06-12, the day before first public promotion.
**Why:** [kengz/SLM-Lab](https://github.com/kengz/SLM-Lab) is an established, actively-maintained deep-RL framework (1.4k★, companion library to *Foundations of Deep Reinforcement Learning*, arXiv:1912.12482) that owns the name "SLM Lab" in machine learning — including search. Sharing the exact name in the same field guaranteed permanent ambiguity and an unwinnable SEO position, and the day before launch was the last cheap moment to fix it. Bonus: `small-model-lab` is self-explanatory to the non-specialist audience this walk-through targets, which `slm-lab` never was. GitHub redirects the old repo URLs; the old GitHub Pages URL does not redirect (nothing external linked it yet).

## ADR-0011 — Phase 4 error-mining loop: ran the loop, marginal gain, keep the original adapter

**Decision:** Ran the B6 recursive loop (mine errors → targeted data → retrain). Shipped the free
deterministic **snap-to-enum** normalizer (off-schema preds 4→0; overall 0.922→0.925). Then augmented
**train only** with 300 Sonnet-labeled rare-modality trials (+$2.76, no test leakage, val/test frozen),
clarified the `combination` rule, and retrained `qwen_v2`. Result is a **statistical wash**
(overall 0.925→0.930, within n=150 noise): modality macro-F1 +0.028 and sponsor → perfect, offset by
endpoint macro-F1 −0.031, risk_flags −0.008, and one new parse failure. **Production reference stays
`adapters/qwen`**; `qwen_v2` is retained but not promoted. Full numbers in `eval/PHASE4_RESULTS.md`.

**Why:** Error-mining correctly diagnosed modality's low macro-F1 as a long-tail problem, but the
*dominant* residual error is the `combination` definitional boundary — partly irreducible teacher-label
noise. We deliberately did **not** relabel existing gold under a new convention: that moves goalposts vs
the frozen test, and distillation can't exceed the teacher regardless. So rare-class augmentation helped
exactly where it had headroom (ADC 0.40→0.60, radiotherapy 0.75→0.88; others already perfect) and no
further. Keep-the-snap normalizer is a clear keep (reliability); promoting `qwen_v2` is a judgement call,
not an obvious upgrade, so the known-good adapter remains the reference. The reusable asset is the loop
itself, not this iteration's delta — iterating again here would be completionism, not value.

## ADR-0010 — Package TrialScout as a local FastMCP stdio server (Phase 5 / B7)

**Decision:** Ship the winner (Qwen3-4B + LoRA) as a Python **FastMCP stdio** server at `track-b-trialscout/serve/trial_readout_server.py`, exposing two flat-schema tools — `trial_readout(nct_id, …)` (fetches from ClinicalTrials.gov v2, then reads out) and `trial_readout_from_record(record, …)` (offline). The server imports the *exact* training prompt (`build_prompt`) and record shape (`compact`) to avoid train/serve drift, injects `nct_id` (the model was trained to omit it), and validates every output against `schema/trial_readout.schema.json`. Registered for Claude Code via a project-scoped `.mcp.json`.

**Why:**
- **Python, not TypeScript** (against the MCP-builder skill's general default): the server must run the MLX model *in-process*, which is Python-only — a TS server would need an IPC hop to a Python worker for zero benefit here.
- **stdio, not HTTP:** single local user, runs as a subprocess of the client, no network surface, no auth to manage. HTTP would add deployment + DNS-rebinding concerns for nothing.
- **Flat tool schemas** (`nct_id`/`response_format` at top level) rather than the skill's nested-Pydantic-model arg, because the nested form forces the calling model to wrap every call in a `params` object — a real ergonomics cost for the first "callable expert."
- **Reuse over reimplementation:** importing `build_prompt`/`compact` guarantees the contract can't silently drift from what produced the 0.922 score; schema validation on each call keeps it a glass box.
- Lazy single model load (instant startup; first call ≈10 s), heavy work in a worker thread, logs to stderr only (stdout is the MCP channel). A `--selftest NCT…` path proves fetch→infer→validate end-to-end without a client (validate-tiny-before-the-long-run).

This is the first node in the model-of-experts vision: a narrow fine-tuned model exposed as a tool a larger orchestrator can call. Next candidates (B6 error-mining to lift the model; a second expert + a router) build on this surface.

## ADR-0009 — Base model resolved: Qwen3-4B (ADR-0002 closed)

**Decision:** Qwen3-4B-Instruct is the TrialScout base model. The measured A/B (ADR-0002) is closed.
**Why:** Fine-tuned Qwen scored **0.922** overall-structured on the held-out test set (vs 0.368 baseline; valid JSON 1.0; phase 1.0, est_readout 0.99). Gemma 4 E2B could not be fine-tuned via `mlx_lm.lora` — the only MLX-hub build is the multimodal (vision+text) checkpoint, whose nested `language_model.*` weights the LoRA targeting rejects (`140 parameters not in model`); no text-only Gemma 4 E2B 4-bit exists yet. Qwen's near-ceiling score makes the decision robust regardless. Completing the Gemma arm is optional and parked.

## ADR-0008 — Unattended distillation is cost-capped + pilot-gated

**Decision:** `make_gold.py` enforces a hard dollar cap (aborts before a call that would exceed it), runs a 10-trial pilot and aborts the bulk run if <8/10 are schema-valid, and writes incrementally (resumable). Run unattended overnight with a $25 authorization (internal cap $24).
**Why:** Spending money on an external API without a human watching demands guardrails. The cap bounds worst-case spend; the pilot gate prevents burning the budget on a broken prompt; incremental+resumable writes mean a crash loses nothing. Prompt caching kept realistic spend to ~$14 for 1,500 trials.

## ADR-0007 — Teacher = Claude Sonnet via forced tool-use + prompt caching

**Decision:** Gold labels are generated by `claude-sonnet-4-6` with `tool_choice` forced to the schema (the model *must* return a schema-valid object), temperature 0, and the static prefix (rules + few-shot + tool schema) prompt-cached.
**Why:** Forced tool-use guarantees valid structured output — no fragile free-text JSON parsing. Temp 0 makes labels consistent. Caching the ~1.5k-token prefix cuts per-call cost ~10×. Sonnet (not Haiku) because **teacher quality caps student quality** (ADR-0003) — the bottleneck worth paying for.

## ADR-0006 — TrialScout output schema & oncology-only scope

**Decision:** The task is one oncology trial → a fixed JSON readout (`phase`, `indication`, `modality`, `primary_endpoint_type`, `sponsor_type`, `est_readout`, `risk_flags[]`, `investor_note`) with controlled vocabularies. Source: ClinicalTrials.gov v2, interventional + phased trials only.
**Why:** A tight schema with enums is exactly the structured-in/structured-out shape where a small fine-tuned model beats a generic one, and it makes deterministic eval (per-field accuracy/F1) possible. Oncology-only keeps the distribution narrow so a 1–4B model can actually master it. Free `investor_note` is the one open field — scored by Claude-as-judge, not exact match.

---

## ADR-0005 — Python pinned to 3.12

**Decision:** Pin the project venv to Python 3.12 (`.python-version`, `requires-python = ">=3.12,<3.13"`), independent of the system 3.14.
**Why:** MLX and torch wheels don't yet ship for 3.14. Pinning avoids a class of "no matching distribution" install failures. System Python is untouched.
**Revisit when:** MLX publishes 3.14 wheels.

## ADR-0004 — Observability is a first-class deliverable, not a bolt-on

**Decision:** Every phase ships an annotated notebook + live loss/eval curves + a decision-log entry, and hyperparameters live in commented configs (no magic numbers).
**Why:** The project's primary goal is learning the process. A working model with an opaque build fails the actual objective. This raises per-phase effort slightly and is worth it.

## ADR-0003 — Distillation loop as the "recursive training" analog

**Decision:** Get utility via a teacher→student distillation loop: Claude generates gold labels → train SLM → Claude-as-judge scores → mine failures → targeted new data → retrain.
**Why:** It's the practical, honest version of the "recursively train a model" eval idea. It's also the most reliable way to make a small model genuinely good at a narrow task. **Teacher quality caps student quality** — so we use a strong teacher (Sonnet), not a cheap one.

## ADR-0002 — Base model chosen by measurement, not faith (Qwen3-4B vs Gemma 4 E2B)

**Decision:** Fine-tune BOTH Qwen3-4B-Instruct-2507 (primary) and Gemma 4 E2B (head-to-head) on the same data and pick the winner via the eval harness.
**Why:** Benchmarks (mid-2026) suggest Qwen3 is the stronger *fine-tuning* base — Qwen3-4B-Instruct-2507 reportedly matches a 120B+ teacher on 8/9 benchmarks, which is exactly our distillation thesis. Gemma 4 E2B is now Apache-2.0, lighter (~2B memory footprint via per-layer embeddings), and the better on-device citizen for the Phase-5 local deployment. The A/B is cheap (same harness) and is itself a key learning moment: model choice is a measured decision, not a religious one. Superseded Qwen2.5-1.5B (the original suggestion) as stale.

## ADR-0001 — Domain & task: biopharma clinical-trial readout

**Decision:** The useful POC (Track B / "TrialScout") is a narrow structured task: clinical-trial record → structured investor-relevant readout (phase, indication, modality, endpoint type, sponsor type, est. readout window, risk flags, short note). Narrowed initially to **oncology**.
**Why:** Cleanest free + public-domain data (ClinicalTrials.gov, openFDA, SEC EDGAR); sits at the bio ∩ pharma ∩ investing intersection of my interests; structured-in/structured-out is the shape where small models genuinely win; and Claude is a strong teacher for it, making gold-label generation cheap. The "model of experts / chief of staff" idea is the *deployment frame* (Phase 5: TrialScout as one callable expert), not the training domain.
