# Decision Log (ADRs)

Locked design decisions with rationale. Newest at top. This file is also part of the **learning trail** — each entry explains not just *what* we chose but *why*, so the reasoning isn't a black box.

---

## ADR-0005 — Python pinned to 3.12

**Decision:** Pin the project venv to Python 3.12 (`.python-version`, `requires-python = ">=3.12,<3.13"`), independent of the system 3.14.
**Why:** MLX and torch wheels don't yet ship for 3.14. Pinning avoids a class of "no matching distribution" install failures. System Python is untouched.
**Revisit when:** MLX publishes 3.14 wheels.

## ADR-0004 — Observability is a first-class deliverable, not a bolt-on

**Decision:** Every phase ships an annotated notebook + live loss/eval curves + a decision-log entry, and hyperparameters live in commented configs (no magic numbers).
**Why:** The project's primary goal is John learning the process. A working model with an opaque build fails the actual objective. This raises per-phase effort slightly and is worth it.

## ADR-0003 — Distillation loop as the "recursive training" analog

**Decision:** Get utility via a teacher→student distillation loop: Claude generates gold labels → train SLM → Claude-as-judge scores → mine failures → targeted new data → retrain.
**Why:** It's the practical, honest version of the "recursively train a model" eval idea. It's also the most reliable way to make a small model genuinely good at a narrow task. **Teacher quality caps student quality** — so we use a strong teacher (Sonnet), not a cheap one.

## ADR-0002 — Base model chosen by measurement, not faith (Qwen3-4B vs Gemma 4 E2B)

**Decision:** Fine-tune BOTH Qwen3-4B-Instruct-2507 (primary) and Gemma 4 E2B (head-to-head) on the same data and pick the winner via the eval harness.
**Why:** Benchmarks (mid-2026) suggest Qwen3 is the stronger *fine-tuning* base — Qwen3-4B-Instruct-2507 reportedly matches a 120B+ teacher on 8/9 benchmarks, which is exactly our distillation thesis. Gemma 4 E2B is now Apache-2.0, lighter (~2B memory footprint via per-layer embeddings), and the better on-device citizen for the Phase-5 local deployment. The A/B is cheap (same harness) and is itself a key learning moment: model choice is a measured decision, not a religious one. Superseded Qwen2.5-1.5B (the original suggestion) as stale.

## ADR-0001 — Domain & task: biopharma clinical-trial readout

**Decision:** The useful POC (Track B / "TrialScout") is a narrow structured task: clinical-trial record → structured investor-relevant readout (phase, indication, modality, endpoint type, sponsor type, est. readout window, risk flags, short note). Narrowed initially to **oncology**.
**Why:** Cleanest free + public-domain data (ClinicalTrials.gov, openFDA, SEC EDGAR); sits at the bio ∩ pharma ∩ investing intersection of John's interests; structured-in/structured-out is the shape where small models genuinely win; and Claude is a strong teacher for it, making gold-label generation cheap. The "model of experts / chief of staff" idea is the *deployment frame* (Phase 5: TrialScout as one callable expert), not the training domain.
