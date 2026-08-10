# Schema-v2 scorecard — TrialScout

All arms scored on the **same frozen 150-trial test set**, with the **same scorer**
(`eval/harness.py`) and the **same normalizer** (`schema/normalize.py`), under schema v2.

| field | Baseline (floor) | Untuned, no vocab | Untuned + enum list | Frontier zero-shot | Fine-tuned student |
|---|---|---|---|---|---|
| overall structured | 0.476 | 0.121 | 0.697 | 0.897 | 0.939 |
| valid output | — | 1.000 | 1.000 | 1.000 | 1.000 |
| phase | 0.447 | 0.440 | 0.987 | 1.000 | 1.000 |
| intervention_class | 0.827 | 0.027 | 0.640 | 0.933 | 0.927 |
| modalities (set-F1) | 0.330 | 0.007 | 0.695 | 0.859 | 0.870 |
| modalities (exact set) | 0.180 | 0.007 | 0.533 | 0.760 | 0.780 |
| modalities (macro-F1) | 0.042 | 0.001 | 0.582 | 0.805 | 0.653 |
| primary_endpoint_type | 0.380 | 0.320 | 0.640 | 0.933 | 0.927 |
| sponsor_type | 0.667 | 0.000 | 0.833 | 0.933 | 0.993 |
| est_readout | 0.040 | 0.000 | 0.420 | 0.827 | 0.980 |
| risk_flags (set-F1) | 0.643 | 0.055 | 0.662 | 0.794 | 0.876 |


### Where `modalities` goes wrong (fine-tuned student)

| error shape | count | share of errors |
|---|---|---|
| disjoint | 11 | 33% |
| partial overlap | 10 | 30% |
| subset (predicted fewer) | 9 | 27% |
| superset (predicted extra) | 3 | 9% |

Exact-set accuracy: **0.780**. Cardinality-only errors (right modalities, wrong count): **12** (36% of all errors).

This is the number that decides whether the list-valued field *resolved* v1's `combination` argument or merely *relocated* it. v1's benchmark: 20 of 34 modality errors involved `combination` on one side or the other.

### Per-modality recall — where the student's win runs out

| modality | n in gold | student | frontier zero-shot | frontier much better |
|---|---|---|---|---|
| targeted small molecule | 63 | 0.82 | 0.89 |  |
| cytotoxic chemotherapy | 49 | 0.98 | 0.86 |  |
| monoclonal antibody | 35 | 0.91 | 1.00 |  |
| other protein or peptide therapeutic | 10 | 0.20 | 0.60 | yes |
| hormonal/endocrine therapy | 8 | 0.88 | 1.00 |  |
| cancer vaccine | 7 | 0.86 | 0.86 |  |
| cell therapy | 7 | 0.86 | 1.00 |  |
| antibody-drug conjugate | 5 | 0.40 | 1.00 | yes |
| radiopharmaceutical | 4 | 0.75 | 1.00 | yes |
| oncolytic virus | 3 | 0.33 | 1.00 | yes |
| bispecific/multispecific antibody | 2 | 0.00 | 0.50 | yes |
| gene therapy | 2 | 0.50 | 0.50 |  |
| oligonucleotide/RNA therapeutic | 1 | 1.00 | 1.00 |  |
| other | 1 | 0.00 | 1.00 | yes |

The student beats the frontier arm on the overall score and loses badly on the rare classes. Its macro-F1 (which weights every label equally) is **below** the frontier arm's for exactly this reason, while its set-F1 (which follows the frequency distribution) is above. Read together: distillation transferred the *conventions* — the H1/H2 rule, the sponsor taxonomy, the chemo-vs-targeted split — but not the *pharmacology*. 1,192 training examples contain only a handful of each rare drug class, and the student cannot learn from what it has barely seen. This is ADR-0016's second half, confirmed: the remainder of this field's weakness is rarity, not ambiguity, and rarity is fixable with targeted data.

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

**The frontier column is a scaffold ablation, not an independent referee.** Gold was
produced by the same model *with* decision rules and worked examples; this arm has the
schema and nothing else. It bounds what the prompt engineering was worth. It cannot tell
you whether the labels are right.
