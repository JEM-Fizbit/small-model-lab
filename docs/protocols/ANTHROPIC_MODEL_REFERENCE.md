# Anthropic Model Reference

> Model ID naming conventions, current inventory, and best practices for referencing Claude models in the Anthropic API.

**Applies to:** Anthropic Claude API, `@anthropic-ai/sdk`
**Last Updated:** 2026-08-18
**Version:** 1.7
**Roster verified:** 2026-08-14

> **Docs host:** the canonical model docs now live at `platform.claude.com/docs/en/...`; `docs.anthropic.com/en/...` 301-redirects there. Any automation that *fetches* the docs should target the canonical host directly — a scheduled job that depends on a redirect surviving is a latent failure.

> **Staleness guard — check this before you trust a role resolution.** If today is more than **45 days** after the *Roster verified* date above, treat this roster as suspect: say so when advising, and re-verify against `GET /v1/models` (or the docs) before recommending a model. Claude Code's default model changes without notice — the 2026-07-25 refresh found the roster had been silently missing Opus 5, the harness default, for weeks. The guard costs one date comparison at read time and no network call: **never** call the Models API on the advice path just to check freshness (that buys a repeated per-invocation round trip to track a monthly-cadence fact). Refresh on a schedule; read statically.

---

## Table of Contents

- [Overview](#overview)
- [Model ID Format](#model-id-format)
- [Current Model Inventory](#current-model-inventory)
- [Quick Start](#quick-start)
- [When to Use Short Alias vs Pinned ID](#when-to-use-short-alias-vs-pinned-id)
- [Anti-Patterns](#anti-patterns)
- [Troubleshooting](#troubleshooting)
- [Resources](#resources)

---

## Overview

Anthropic models use a specific naming convention for API model IDs. Getting this wrong causes silent runtime failures (the API returns an error, but if error handling is weak, the user sees nothing). This protocol documents the valid formats and current model inventory to prevent production incidents.

### Key Benefits

- Avoid invalid model ID errors that break AI features
- Know when to use short aliases vs pinned date IDs
- Quick reference for current model inventory

---

## Model ID Format

Every Claude model has two valid ID forms:

### 1. Short alias (recommended for most use cases)

```
claude-{tier}-{version}
```

Examples:
- `claude-opus-5`
- `claude-fable-5`
- `claude-sonnet-5`
- `claude-haiku-4-5`

For the 4.6 generation and later (every ID listed above), the dateless form **is** the canonical model ID and maps to one fixed snapshot — it is **not** an evergreen pointer. Anthropic never updates the weights behind an existing ID; an updated model ships under a *new* ID. The alias-resolves-to-latest behaviour applies **only** to pre-4.6 models (e.g. `claude-haiku-4-5`), where the dateless form is a genuine convenience pointer to the most recent dated snapshot for that minor version.

### 2. Pinned date ID (for reproducibility — older models only)

```
claude-{tier}-{version}-{YYYYMMDD}
```

Examples:
- `claude-haiku-4-5-20251001`
- `claude-opus-4-5-20251101`
- `claude-sonnet-4-5-20250929`

Pinned IDs lock to a specific model snapshot. Use these when you need deterministic behavior across deployments.

> **The current generation has no dated variants.** For Fable 5, Mythos 5, Opus 5/4.8/4.7/4.6, Sonnet 5, and Sonnet 4.6, the alias **is** the complete and only ID — appending a date suffix (`claude-sonnet-5-20260701`) is an invented string and 404s. Dated snapshots exist only for the 4.5-and-older models listed under Previous Generation. On Google Vertex AI, dated snapshots use an `@` separator (`claude-opus-4-5@20251101`), not a hyphen.

---

## Current Model Inventory

### Current Generation (July 2026)

| Model | ID (alias = complete ID) | Context | Max Output | $/1M in | $/1M out |
|-------|--------------------------|---------|------------|---------|----------|
| **Fable 5** (most capable GA) | `claude-fable-5` | 1M | 128k | $10 | $50 |
| **Mythos 5** (Project Glasswing only) | `claude-mythos-5` | 1M | 128k | $10 | $50 |
| **Opus 5** (current Opus) | `claude-opus-5` | 1M | 128k | $5 | $25 |
| **Opus 4.8** | `claude-opus-4-8` | 1M | 128k | $5 | $25 |
| **Opus 4.7** | `claude-opus-4-7` | 1M | 128k | $5 | $25 |
| **Sonnet 5** | `claude-sonnet-5` | 1M | 128k | **$2** | **$10** |
| **Haiku 4.5** | `claude-haiku-4-5` | 200k | 64k | $1 | $5 |

> **Pricing notes — read before costing a run.**
>
> **Code must not transcribe this table.** The numbers are canonical as data in [`data/anthropic-pricing.json`](https://github.com/JEM-Fizbit/ai-knowledge/blob/main/protocols/data/anthropic-pricing.json) — read that file (knowhub syncs it to `docs/protocols/data/anthropic-pricing.json`) rather than copying rates into a fee card. It carries `verified_on`, the staleness rule, the cache and batch multipliers, and the list of consuming projects. This markdown table is for human readers and is held in step by `scripts/check-anthropic-pricing.py`; **the JSON wins if they disagree.** Four projects hand-copied these rates and by 2026-08-18 held three different wrong values between them — a rate table is a cache of someone else's decision, and an uncompared cache drifts.
>
> **Sonnet 5 is $2/$10 permanently.** The $2/$10 launched as introductory pricing "through 2026-08-31"; the scheduled 2026-09-01 rise to $3/$15 **was cancelled** and $2/$10 is now the standard price. This table said the opposite until 2026-08-14, which over-budgeted every Sonnet 5 estimate by ~50%. **Sonnet 4.6 ($3/$15) is therefore both older and 50% dearer than Sonnet 5 — never choose it for new work.**
>
> **Tokeniser change (4.7 and later).** Current-family models emit **~30% more tokens for the same text** than 4.6-and-earlier, so a headline $/token comparison across that boundary overstates the saving. Measured on 40 identical requests (small-model-lab, 2026-08-14): Sonnet 4.6 $0.39 vs Sonnet 5 $0.49 at then-identical prices — **+26%**. Sonnet 5's effective rate vs a 4.6-era baseline is therefore ~$2.52/$12.60: still cheaper than Sonnet 4.6, by ~16% rather than the headline 33%.
>
> **Cache and batch multipliers** (apply to the input rate): 5-minute cache **write ×1.25**, 1-hour cache **write ×2**, cache **read ×0.1**. The **Batch API is 50% off both directions** — free money for any asynchronous bulk job, and routinely forgotten.
>
> **Effort dominates cost on output-heavy jobs.** Where output tokens are most of the bill, `output_config.effort` moves spend further than model choice does. Measured on a structured-extraction job: Sonnet 5 at `effort: low` cost **37% less** than `medium` and agreed with it **0.985** — while Opus 5, at 2.5× the price, agreed only **0.962**. Probe effort before assuming a bigger model is the upgrade.

**Mythos 5** is the capability/pricing twin of Fable 5, reachable **only** through Project Glasswing participation (it succeeds the invitation-only `claude-mythos-preview`). Treat `claude-fable-5` as the frontier ID unless the org is actually enrolled.

> **API-shape notes (current family).** Fable 5, Mythos 5, Opus 5/4.8/4.7, and Sonnet 5 use **adaptive thinking only** (`thinking: {type: "adaptive"}`); `budget_tokens` and the sampling params `temperature`/`top_p`/`top_k` are removed and return 400. Assistant-turn prefills 400 on all of these. Control depth via `output_config: {effort: "low"|"medium"|"high"|"xhigh"|"max"}`.
>
> **Opus 5 specifics** (two breaking changes vs Opus 4.8, otherwise drop-in at the same price): thinking is **on by default** — omitting `thinking` now runs adaptive, so a route sized tightly around its answer can truncate (`max_tokens` caps thinking + text together); and `thinking: {type: "disabled"}` is accepted **only at effort `high` or below** (400 at `xhigh`/`max`, validated per request). Also: prompt-cache minimum drops to **512 tokens** (1024 on Opus 4.8), it sits in a **separate rate-limit bucket** from the combined Opus 4.x pool, and fast mode (`speed: "fast"`) is Claude-API-only.
>
> **Fable 5 / Mythos 5 specifics:** thinking is always on — an explicit `thinking: {type: "disabled"}` returns 400 (omit the param); requires **30-day data retention** (every request 400s under ZDR).
>
> **Refusals on Fable 5 / Mythos 5 / Opus 5:** safety classifiers can decline a request as a **successful HTTP 200** with `stop_reason: "refusal"` — check `stop_reason` before reading `content[0]`, and prefer `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`) over pinning a fallback model.

### Role resolution (single source of truth for MODEL_EFFORT_SELECTION roles)

This table is **the one place** role→id resolution lives. The `MODEL_EFFORT_SELECTION.md` rubric (and the `model-effort-selection` skill) reference roles only; resolve them here at use time. Role leadership is a judgment call re-made on every refresh (capability × cost × harness defaults) — not "newest = frontier".

| Role | Resolves to (2026-07-25) | Why |
|---|---|---|
| **frontier-reasoning** | Fable 5 (`claude-fable-5`) | Still the most capable GA model and a deliberate escalation *above* the harness default — hardest careful solo reasoning: architecture/spec, security, thorny debugging. Costs 2× Opus-tier and always thinks, so it is a choice, not a default. |
| **balanced-generalist** | **Opus 5 (`claude-opus-5`)** — was Opus 4.8 | The Claude Code main-loop default and a drop-in step-change over 4.8 at identical pricing ($5/$25): strongest agentic-coding and long-horizon tier below Fable, half Fable's cost. Economical base for workflow/fan-out fleets and general main-loop work. |
| **cheap-workhorse** | Sonnet 5 (`claude-sonnet-5`) | Opt-in only: genuinely fungible mechanical subagent stages at real volume. Now near-Opus on coding/agentic work, which widens where the opt-in is defensible. |
| **cheapest** | Haiku 4.5 (`claude-haiku-4-5`) | Trivial / bulk work only. |

**What moved this refresh:** only `balanced-generalist` (Opus 4.8 → Opus 5). Opus 5 takes the seat because all three refresh criteria point the same way — it is the harness default, it is strictly better than 4.8 on the work that seat does, and it costs the same. Fable 5 keeps frontier-reasoning: Opus 5 is a step-change *within* the Opus tier, not a replacement for the tier above it. Opus 4.8 stays a valid fallback target (and is where Opus 5's cyber-category refusals route).

### Previous Generation (still available)

| Model | Short Alias | Pinned ID | Context |
|-------|-------------|-----------|---------|
| Opus 4.6 | `claude-opus-4-6` | (alias only) | 1M |
| Sonnet 4.6 | `claude-sonnet-4-6` | (alias only) | 1M |
| Opus 4.5 | `claude-opus-4-5` | `claude-opus-4-5-20251101` | 200k |
| Sonnet 4.5 | `claude-sonnet-4-5` | `claude-sonnet-4-5-20250929` | 200k |

### Deprecated (scheduled for retirement)

| Model | ID | Retirement Date |
|-------|----|-----------------|
| Opus 4.1 | `claude-opus-4-1` | **2026-08-05** — migrate to `claude-opus-5` |
| Mythos Preview | `claude-mythos-preview` | TBD — migrate to `claude-mythos-5` (Glasswing only) |

### Retired (404 on use)

Sonnet 4 and Opus 4 (2026-06-15), Haiku 3 (2026-04-20), Sonnet 3.7 and Haiku 3.5 (2026-02-19), Opus 3 (2026-01-05), both Sonnet 3.5 snapshots (2025-10-28), Sonnet 3 and Claude 2.x (2025-07-21). Replacements: → `claude-sonnet-5`, `claude-haiku-4-5`, or `claude-opus-5` by tier.

> **Note:** This inventory is a point-in-time snapshot, refreshed monthly and on model drops. For live capability data (context window, max output, per-feature support) query the Models API — `client.models.retrieve("claude-opus-5")` returns `max_input_tokens`, `max_tokens`, and a `capabilities` tree — rather than trusting this table. Verify current models at [Anthropic's model docs](https://platform.claude.com/docs/en/docs/about-claude/models).

---

## Quick Start

```typescript
import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic();

// Use short alias — recommended
const response = await anthropic.messages.create({
  model: "claude-opus-5",
  max_tokens: 1024,
  messages: [{ role: "user", content: "Hello!" }],
});
```

---

## When to Use Short Alias vs Pinned ID

| Scenario | Recommendation |
|----------|---------------|
| Production app, general use | **Short alias** — auto-upgrades within tier |
| Evaluation benchmarks | **Pinned ID** — reproducible results |
| Cost-sensitive batch processing | **Pinned ID** — predictable pricing |
| Prototype / development | **Short alias** — always latest |
| Regulated / audited systems | **Pinned ID** — traceability |

> **This choice only exists for pre-4.6 models.** From the 4.6 generation on there is no alias-vs-pinned decision to make: the dateless ID *is* the pinned snapshot, so every row above collapses to "use the ID". Reproducibility across deployments is automatic — behaviour changes only when *you* change the ID string, never underneath you.

---

## Anti-Patterns

### `-latest` suffix does not exist

```typescript
// WRONG — this model ID does not exist and will cause an API error
const model = "claude-sonnet-4-5-latest";

// CORRECT — use the short alias (no suffix)
const model = "claude-sonnet-4-5";
```

### Date-suffixing a current-generation alias

```typescript
// WRONG — no dated snapshot exists for the current generation; this 404s
const model = "claude-opus-5-20260701";

// CORRECT — the alias IS the complete ID
const model = "claude-opus-5";
```

### Guessing model IDs

```typescript
// WRONG — invented version number
const model = "claude-sonnet-4-9";

// CORRECT — verify against Anthropic docs before using
const model = "claude-sonnet-5";
```

### Hardcoding model IDs in many files

```typescript
// WRONG — model ID scattered across codebase
// file1.ts: model: "claude-sonnet-4-6"
// file2.ts: model: "claude-sonnet-4-6"
// file3.ts: model: "claude-sonnet-4-6"

// BETTER — centralize in a constants file
// constants.ts
export const CHAT_MODEL = "claude-sonnet-5";
export const FAST_MODEL = "claude-haiku-4-5";
```

### Not handling model errors

```typescript
// WRONG — silent failure if model ID is invalid
try {
  const response = await anthropic.messages.create({ model, ... });
} catch {
  // silently swallowed
}

// CORRECT — surface the error
try {
  const response = await anthropic.messages.create({ model, ... });
} catch (err) {
  console.error(`[ai] API error: ${err.message}`);
  throw err; // or return error to user
}
```

---

## Troubleshooting

### Problem: "model not found" or "invalid model" API error

**Cause:** The model ID string doesn't match any valid Anthropic model. Common mistakes: `-latest` suffix, wrong version number, typo in tier name.

**Solution:** Check the [current model inventory](#current-model-inventory) above. Use the exact short alias or pinned ID. When in doubt, check [Anthropic's model page](https://platform.claude.com/docs/en/docs/about-claude/models).

### Problem: AI features silently broken after model upgrade

**Cause:** Invalid model ID causes API errors, but the error isn't surfaced to the user due to weak error handling in the SSE stream or catch blocks.

**Solution:** Always surface API errors to the user. In SSE streaming, ensure error events aren't overwritten by post-stream cleanup code. Test model ID changes in development before deploying.

### Problem: Unexpected behavior change after deployment

**Cause:** For a **pre-4.6 model**, a short alias that auto-upgraded to a new snapshot with different behavior. For a **4.6-generation-or-later ID** this cannot be the cause — those IDs are fixed snapshots and Anthropic does not update their weights. There the likely cause is a **serving-infrastructure** change around the model (request router, safety classifiers, sampling logic), which can shift observable behavior with the ID and weights unchanged.

**Solution:** On a pre-4.6 model, switch to the pinned date ID for that model. On current-generation IDs there is nothing to pin — re-baseline your evals and treat the drift as infrastructure, not a silent model swap.

---

## Resources

- [Anthropic Models Documentation](https://platform.claude.com/docs/en/docs/about-claude/models)
- [Anthropic API Reference](https://platform.claude.com/docs/en/api)
- [Model Deprecation Schedule](https://platform.claude.com/docs/en/docs/about-claude/models#model-deprecations)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.5 | 2026-07-26 | Monthly roster verification. The Current Model Inventory needed no change — no model launched or retired since 1.4, and every pricing, context, and max-output value matches the docs. Mechanical corrections elsewhere: **dateless IDs are pinned snapshots, not evergreen pointers** — the "alias always resolves to the latest snapshot" claim is true only for pre-4.6 models, so the Model-ID-Format paragraph, the alias-vs-pinned table, and the behaviour-drift troubleshooting entry were corrected (drift on a current-gen ID is *serving infrastructure* — router, safety classifiers, sampling — not a silent weight swap). Fixed **Opus 4.5 and Sonnet 4.5 context: 1M → 200k** (the full 1M window is a 4.6-and-later feature). Deprecations trued up: **Sonnet 4 and Opus 4 retired 2026-06-15** and **Haiku 3 retired 2026-04-20** (listed as pending-with-TBD and with a wrong 04-19 date) moved to Retired, leaving Opus 4.1 as the only deprecated model; added `claude-mythos-preview` (now deprecated, migrate to `claude-mythos-5`). Role resolution table untouched. |
| 1.7 | 2026-08-18 | **Prices are now canonical as data, not prose.** Added [`data/anthropic-pricing.json`](https://github.com/JEM-Fizbit/ai-knowledge/blob/main/protocols/data/anthropic-pricing.json) — per-model-id rates plus `verified_on`, the staleness rule, cache/batch multipliers, an explicit unknown-model policy, and the list of consuming projects — and `scripts/check-anthropic-pricing.py`, which reconciles it against the markdown table and applies the staleness guard. Motivation: an audit of the estate on 2026-08-18 found the same rates hand-copied into four repos in three different states of wrongness — pharma-signal-poc at Opus $15/$75 (3x, two generations stale), Social-Creator-Claude and aigent-alpha both at Sonnet 5 $3/$15 (50% high, on the cancelled-reversion premise this protocol corrected in 1.6). The 1.6 correction reached the protocol and none of the code, because markdown cannot be imported. Each consumer now reads the JSON and is audited by `knowhub-doctor.sh`, which was extended to cover non-markdown managed outputs. |
| 1.6 | 2026-08-14 | Corrected the **Sonnet 5 price to a permanent $2/$10** — the scheduled 2026-09-01 rise to $3/$15 was cancelled, and this table asserting otherwise over-budgeted every Sonnet 5 estimate by ~50% while making the older, dearer Sonnet 4.6 look competitive. Added a **Pricing notes** block: the 4.7+ tokeniser emitting ~30% more tokens (measured +26%), cache/batch multipliers incl. the routinely-forgotten 50% Batch API discount, and the finding that **`effort` outweighs model choice on output-heavy jobs** (low vs medium: −37% cost, 0.985 agreement; Opus 5 at 2.5× the price agreed only 0.962). |
| 1.4 | 2026-07-25 | Added the **`Roster verified` date + 45-day staleness guard** in the header. Detection, not propagation, was the gap the 1.3 refresh exposed: role indirection meant one edit reached the skill, plugin, and ERS mirror with zero edits to any of them, but the roster itself sat weeks stale with the harness default missing and nothing surfaced it. The guard is deliberately read-time-only (a date comparison on a file already being read) — recorded the rule that the Models API must **not** be called on the advice path, since a live lookup is an extra inference turn per invocation to track a monthly-cadence fact, and can supply neither pricing nor role leadership. |
| 1.3 | 2026-07-25 | Roster refresh. **Added Opus 5** (missing entirely — the current Opus and the Claude Code main-loop default) and **Mythos 5** (Glasswing-only twin of Fable 5). **Role-leadership call: `balanced-generalist` Opus 4.8 → Opus 5** (harness default + strictly better at the same $5/$25; Fable 5 keeps frontier-reasoning). Added a pricing column so the capability×cost half of the judgment is auditable in-table. Corrected the pinned-ID guidance: the current generation has **no** dated variants (the alias is the complete ID) — removed three invented/wrong pinned IDs (`claude-opus-4-6-20250918`, `claude-sonnet-4-6-20250929`, and Sonnet 4.5 mislabelled with Sonnet 4's `20250514` date), added the Vertex `@`-separator note and a date-suffix anti-pattern. Added Opus 5 API-shape notes (thinking on by default; disabled-thinking capped at effort ≤ `high`; 512-token cache minimum; separate rate-limit bucket), a refusal/`fallbacks: "default"` note, deprecations (Opus 4.1 retires 2026-08-05), and a retired-models line. |
| 1.2 | 2026-07-11 | Added Role-resolution table as the single source of truth for MODEL_EFFORT_SELECTION roles; promoted Fable 5 to frontier-reasoning (most capable GA model), Opus 4.8 to balanced-generalist. |
| 1.1 | 2026-07-03 | Refreshed inventory — Fable 5, Opus 4.8/4.7, Sonnet 5 now current; 4.6 family moved to previous-gen. Added current-family API-shape notes (adaptive thinking only; `budget_tokens`/sampling params removed; effort parameter). Updated examples to current model IDs. |
| 1.0 | 2026-03-28 | Initial release — model ID format, current inventory, anti-patterns |

---

**Protocol Version**: 1.5
**Last Updated**: 2026-07-26
**Original Source**: Social-Creator-Claude project (production incident from using invalid `-latest` aliases)
