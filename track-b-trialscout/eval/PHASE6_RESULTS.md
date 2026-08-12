# Schema-v2 scorecard — TrialScout

All arms scored on the **same frozen 150-trial test set**, with the **same scorer**
(`eval/harness.py`) and the **same normalizer** (`schema/normalize.py`), under schema v2.

| field | Baseline (floor) | Untuned, no vocab | Untuned + enum list | Frontier zero-shot | v2 student | v3 student (PRODUCTION) |
|---|---|---|---|---|---|---|
| overall structured | 0.476 | 0.121 | 0.697 | 0.897 | 0.939 | 0.936 |
| valid output | — | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| phase | 0.447 | 0.440 | 0.987 | 1.000 | 1.000 | 1.000 |
| intervention_class | 0.827 | 0.027 | 0.640 | 0.933 | 0.940 | 0.947 |
| modalities (set-F1) | 0.330 | 0.007 | 0.695 | 0.859 | 0.854 | 0.888 |
| modalities (exact set) | 0.180 | 0.007 | 0.533 | 0.760 | 0.740 | 0.753 |
| modalities (macro-F1) | 0.042 | 0.001 | 0.582 | 0.805 | 0.569 | 0.660 |
| primary_endpoint_type | 0.380 | 0.320 | 0.640 | 0.933 | 0.933 | 0.927 |
| sponsor_type | 0.667 | 0.000 | 0.833 | 0.933 | 1.000 | 0.987 |
| est_readout | 0.040 | 0.000 | 0.420 | 0.827 | 0.987 | 0.987 |
| risk_flags (set-F1) | 0.643 | 0.055 | 0.662 | 0.794 | 0.860 | — |
| risk_flags_judgement (set-F1) | — | — | — | — | — | 0.815 |


### Where `modalities` goes wrong (fine-tuned student)

| error shape | count | share of errors |
|---|---|---|
| partial overlap | 11 | 30% |
| subset (predicted fewer) | 11 | 30% |
| superset (predicted extra) | 9 | 24% |
| disjoint | 6 | 16% |

Exact-set accuracy: **0.753**. Cardinality-only errors (right modalities, wrong count): **20** (54% of all errors).

This is the number that decides whether the list-valued field *resolved* v1's `combination` argument or merely *relocated* it. v1's benchmark: 20 of 34 modality errors involved `combination` on one side or the other.

### Per-modality recall — where the student's win runs out

| modality | n in gold | student | frontier zero-shot | frontier much better |
|---|---|---|---|---|
| targeted small molecule | 68 | 0.85 | 0.89 |  |
| cytotoxic chemotherapy | 51 | 0.88 | 0.86 |  |
| monoclonal antibody | 38 | 0.90 | 1.00 |  |
| hormonal/endocrine therapy | 10 | 0.90 | 1.00 |  |
| other protein or peptide therapeutic | 8 | 0.25 | 0.60 | yes |
| cancer vaccine | 7 | 1.00 | 0.86 |  |
| cell therapy | 7 | 0.86 | 1.00 |  |
| antibody-drug conjugate | 5 | 0.40 | 1.00 | yes |
| radiopharmaceutical | 4 | 1.00 | 1.00 |  |
| oncolytic virus | 3 | 0.33 | 1.00 | yes |
| bispecific/multispecific antibody | 2 | 0.50 | 0.50 |  |
| oligonucleotide/RNA therapeutic | 2 | 0.50 | 1.00 | yes |
| gene therapy | 1 | 1.00 | 0.50 |  |

> **Read the n column before this table.** Several of these classes have 1-5 gold examples, where one trial swings recall by 20-100 points. Measured on the properly-powered diagnostic set (ADR-0020, n=34-100 per class) the same model scores ADC **0.77** and oncolytic virus **0.88**, not the 0.40 and 0.33 shown here. These frozen-set rare-class figures are sampling noise and must not be quoted as capability. See `PHASE6_DIAGNOSTIC.md`.

## What is comparable to what

**Like-for-like.** Every column above shares a test set, a scorer and a schema. The
headline comparison the project cares about — **untuned Qwen (strict) vs fine-tuned
student** — is exactly apples-to-apples: the same open model, the same prompt, the same
parsing of its own JSON output. That delta is the value fine-tuning added.

**Not like-for-like.** "Untuned Qwen (judged)" gives the base model a Claude judge that
reads its prose and maps it to the fields. It is a *more generous* reading of the same
model, included because the earlier write-up used it; it is not the same measurement as
the strict column, and the student is not given that help.

**Not comparable to v1 at all.** The schema-v1 headline (0.922) came from six components
scoring `modality` by hard accuracy. This is seven components scoring `modalities` by
set-F1, which awards partial credit where v1 awarded none. The two numbers share a scale
and measure different things. The v1 figures remain reproducible in `eval/v1-frozen/`.

**The rare-class rows in the table below are NOT reliable.** Several classes have 1-8 gold
examples here, where one trial swings recall by 12-50 points. The trustworthy figures come from
the 1,444-trial natural held-out set (ADR-0022): ADC **0.91** not 0.40, bispecific **0.79** not
0.50, macro-F1 **0.737** not 0.660. This page's *headline* is sound -- 0.936 here against 0.932
there -- but its per-class detail is noise. See `PHASE6_DIAGNOSTIC.md`.

**Historic note on PRODUCTION columns.** `qwen_v2s_aug` scores lower here on
modalities macro-F1 (0.569 vs 0.653) yet is the promoted adapter. Frozen-set macro-F1 weights
every label equally across classes with n=1-5, so it is mostly sampling noise. On the
properly-powered diagnostic set the ordering reverses (0.689 vs 0.663) and the augmented adapter
wins every adequately-sampled rare class. See `PHASE6_DIAGNOSTIC.md` and ADR-0020. The two
columns are tied on the headline (0.939), which is the number this page is for.

**The frontier column is a scaffold ablation, not an independent referee.** Gold was
produced by the same model *with* decision rules and worked examples; this arm has the
schema and nothing else. It bounds what the prompt engineering was worth. It cannot tell
you whether the labels are right.
