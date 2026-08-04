# Decision Log (ADRs)

Locked design decisions with rationale. Newest at top. This file is also part of the **learning trail** — each entry explains not just *what* we chose but *why*, so the reasoning isn't a black box.

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
