# Anthropic Model Reference

> Model ID naming conventions, current inventory, and best practices for referencing Claude models in the Anthropic API.

**Applies to:** Anthropic Claude API, `@anthropic-ai/sdk`
**Last Updated:** 2026-10-10
**Version:** 1.12
**Roster verified:** 2026-10-10

> **Docs host:** the canonical model docs now live at `platform.claude.com/docs/en/...`; `docs.anthropic.com/en/...` 301-redirects there. Any automation that *fetches* the docs should target the canonical host directly — a scheduled job that depends on a redirect surviving is a latent failure.

> **Staleness guard — check this before you trust a role resolution.** If today is more than **45 days** after the *Roster verified* date above, treat this roster as suspect: say so when advising, and re-verify against `GET /v1/models` (or the docs) before recommending a model. Claude Code's default model changes without notice — the 2026-07-25 refresh found the roster had been silently missing Opus 5, the harness default, for weeks. The guard costs one date comparison at read time and no network call: **never** call the Models API on the advice path just to check freshness (that buys a repeated per-invocation round trip to track a monthly-cadence fact). Refresh on a schedule; read statically.
>
> **Second guard, same cost: is the model you are running on in this roster?** The harness tells every session its own model id. If that id is absent from the inventory below, the roster has missed a drop — say so and refresh, whatever the *Roster verified* date says. This is what caught the 2026-09 gap: Fable 5.1 shipped on 2026-09-01, the day of a verification pass that recorded "no model launched", and the date guard would have stayed green for another 26 days. It fired again on 2026-09-23 for Opus 5.5, one day after release.

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
- `claude-opus-5-5`
- `claude-fable-5-1`
- `claude-sonnet-5-5`
- `claude-sonnet-5`
- `claude-haiku-5-5`
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

> **The current generation has no dated variants.** For Fable 5.1/5, Mythos 5.1/5, Opus 5.5/5/4.8/4.7/4.6, Sonnet 5.5/5, Sonnet 4.6, and Haiku 5.5, the alias **is** the complete and only ID — appending a date suffix (`claude-sonnet-5-20260701`) is an invented string and 404s. Dated snapshots exist only for the 4.5-and-older models listed under Previous Generation. On Google Vertex AI, dated snapshots use an `@` separator (`claude-opus-4-5@20251101`), not a hyphen.

---

## Current Model Inventory

### Current Generation (September 2026)

| Model | ID (alias = complete ID) | Context | Max Output | $/1M in | $/1M out |
|-------|--------------------------|---------|------------|---------|----------|
| **Fable 5.1** (most capable GA) | `claude-fable-5-1` | 1M | 128k | $10 | $50 |
| **Mythos 5.1** (Project Glasswing only) | `claude-mythos-5-1` | 1M | 128k | $10 | $50 |
| Fable 5 (superseded by 5.1) | `claude-fable-5` | 1M | 128k | $10 | $50 |
| Mythos 5 (superseded by 5.1; Glasswing only) | `claude-mythos-5` | 1M | 128k | $10 | $50 |
| **Opus 5.5** (current Opus) | `claude-opus-5-5` | 1M | 128k | **$4** | **$20** |
| Opus 5 (superseded by 5.5) | `claude-opus-5` | 1M | 128k | $5 | $25 |
| **Opus 4.8** | `claude-opus-4-8` | 1M | 128k | $5 | $25 |
| **Opus 4.7** | `claude-opus-4-7` | 1M | 128k | $5 | $25 |
| **Sonnet 5.5** (current Sonnet) | `claude-sonnet-5-5` | 1M | 128k | **$2** | **$10** |
| Sonnet 5 (superseded by 5.5) | `claude-sonnet-5` | 1M | 128k | $2 | $10 |
| **Haiku 5.5** (current Haiku; ≤100k-token prompts) | `claude-haiku-5-5` | 1M | 128k | **$0.10** | **$0.50** |
| Haiku 4.5 (superseded by 5.5) | `claude-haiku-4-5` | 200k | 64k | $1 | $5 |

The docs' own *current* line-up is four models — **Fable 5.1, Opus 5.5, Sonnet 5.5, Haiku 5.5** — and they now name Opus 5.5, not Opus 5, as the place to start for most workloads. Fable 5, Opus 5, Sonnet 5, Haiku 4.5, Opus 4.8 and Opus 4.7 are listed there as *legacy (still available)*, and Mythos 5 is Glasswing-only; they stay in this priced table because they are active, callable and still appear in telemetry.

> **Haiku 5.5 has two rate cards, chosen per request by prompt length.** The table shows the base card. A request whose prompt is **over 100,000 tokens** (all input tokens, cache reads and writes included) is billed at **$0.50 / $2.50** for the whole request — cache hits included — and earlier requests keep the card they were billed at. Cache and batch multipliers apply to whichever card is in force. The JSON carries this as `long_context`; a consumer that ignores it under-reports a long-prompt Haiku 5.5 request **5x**, the unsafe direction.

> **Pricing notes — read before costing a run.**
>
> **Code must not transcribe this table.** The numbers are canonical as data in [`data/anthropic-pricing.json`](https://github.com/JEM-Fizbit/ai-knowledge/blob/main/protocols/data/anthropic-pricing.json) — read that file (knowhub syncs it to `docs/protocols/data/anthropic-pricing.json`) rather than copying rates into a fee card. It carries `verified_on`, the staleness rule, the cache and batch multipliers, and the list of consuming projects. This markdown table is for human readers and is held in step by `scripts/check-anthropic-pricing.py`; **the JSON wins if they disagree.** Four projects hand-copied these rates and by 2026-08-18 held three different wrong values between them — a rate table is a cache of someone else's decision, and an uncompared cache drifts.
>
> **Sonnet 5 is $2/$10 permanently.** The $2/$10 launched as introductory pricing "through 2026-08-31"; the scheduled 2026-09-01 rise to $3/$15 **was cancelled** and $2/$10 is now the standard price. This table said the opposite until 2026-08-14, which over-budgeted every Sonnet 5 estimate by ~50%. **Sonnet 4.6 ($3/$15) is therefore both older and 50% dearer than Sonnet 5 — never choose it for new work.**
>
> **Tokeniser change (4.7 and later).** Current-family models emit **~30% more tokens for the same text** than 4.6-and-earlier, so a headline $/token comparison across that boundary overstates the saving. Measured on 40 identical requests (small-model-lab, 2026-08-14): Sonnet 4.6 $0.39 vs Sonnet 5 $0.49 at then-identical prices — **+26%**. Sonnet 5's effective rate vs a 4.6-era baseline is therefore ~$2.52/$12.60: still cheaper than Sonnet 4.6, by ~16% rather than the headline 33%.
>
> **Cache and batch multipliers** (apply to the input rate): 5-minute cache **write ×1.25**, 1-hour cache **write ×2**, cache **read ×0.1** — **except Fable 5.1 / Mythos 5.1, which read cache at ×0.025** ($0.25/MTok, a quarter of Fable 5's rate), **and Opus 5.5 and Sonnet 5.5 at ×0.05** ($0.20/MTok and $0.10/MTok; Opus 5.5 reads cache at the same price as Sonnet 5, Sonnet 5.5 at half). The JSON carries all three as a per-model `multiplier_overrides.cache_read`. (Sonnet 5.5's override was missed on the 2026-10-01 pass and added 2026-10-10 — a table copied in that window over-reports its cache reads 2x.) Haiku 5.5 uses the standard multipliers on whichever of its two rate cards applies. On a long agentic session, where re-reading the cached prefix is most of the input bill, those overrides move cost more than the headline rates do. The **Batch API is 50% off both directions** — free money for any asynchronous bulk job, and routinely forgotten.
>
> **Effort dominates cost on output-heavy jobs.** Where output tokens are most of the bill, `output_config.effort` moves spend further than model choice does. Measured on a structured-extraction job: Sonnet 5 at `effort: low` cost **37% less** than `medium` and agreed with it **0.985** — while Opus 5, at 2.5× the price, agreed only **0.962**. Probe effort before assuming a bigger model is the upgrade.

**Mythos 5.1** is the capability/pricing twin of Fable 5.1, reachable **only** through Project Glasswing participation (it succeeds Mythos 5, which succeeded the invitation-only `claude-mythos-preview`). Treat `claude-fable-5-1` as the frontier ID unless the org is actually enrolled.

> **API-shape notes (current family).** Fable 5.1/5, Mythos 5.1/5, Opus 5.5/5/4.8/4.7, and Sonnet 5 use **adaptive thinking only** (`thinking: {type: "adaptive"}`); `budget_tokens` and the sampling params `temperature`/`top_p`/`top_k` are removed and return 400. Assistant-turn prefills 400 on all of these. Control depth via `output_config: {effort: "low"|"medium"|"high"|"xhigh"|"max"}`.
>
> **Opus 5 specifics** (two breaking changes vs Opus 4.8, otherwise drop-in at the same price): thinking is **on by default** — omitting `thinking` now runs adaptive, so a route sized tightly around its answer can truncate (`max_tokens` caps thinking + text together); and `thinking: {type: "disabled"}` is accepted **only at effort `high` or below** (400 at `xhigh`/`max`, validated per request). Also: prompt-cache minimum drops to **512 tokens** (1024 on Opus 4.8), it sits in a **separate rate-limit bucket** from the combined Opus 4.x pool, and fast mode (`speed: "fast"`) is Claude-API-only.
>
> **Opus 5.5 is not a drop-in for Opus 5 — four breaking changes** (same 1M context, 128k output and tokeniser; cheaper). (1) **Thinking can't be disabled:** `thinking: {type: "disabled"}` and `{type: "enabled", budget_tokens}` both 400 at every effort level — omit `thinking` and lower `effort` instead. (2) **Forced tool use 400s**, as on Fable 5.1 — so the default Opus now breaks the forced-`tool_choice` pattern in `ANTHROPIC_STRUCTURED_OUTPUT_TOOLUSE.md` as well; use `auto` + `strict: true`, or `output_config.format`. (3) **Preserved thinking:** only Fable 5.1 / Mythos 5.1 on the Claude API read its thinking blocks (a fallback to Opus 5 runs without them); it reads Opus 5-and-earlier blocks but not Fable or Mythos ones; editing anything before a block 400s on accounts created on or after 2026-08-31, as on Fable 5.1. (4) **Computer use only via `computer_toolset_20260801`** on the Claude API and Google Cloud (`computer_20251124` 400s; Bedrock still accepts it). Non-failing shifts: **default effort is `medium`** (Opus 5: `high`) and it thinks more per turn at any given level, so set effort explicitly and re-sweep rather than carry an Opus 5 setting over; text between tool calls now arrives as progress-update `thinking` blocks, empty unless `thinking.display` is `"updates"` (beta) or `"summarized"`. Also: 512-token cache minimum; fast mode $8/$40, Claude API only.
>
> **Haiku 5.5 is not a drop-in for Haiku 4.5 — five breaking changes** (1M context and 128k output, up from 200k/64k; the 4.7-generation tokeniser, so the same text costs ~30% more tokens; `effort` now supported, **default `medium`**). (1) **`budget_tokens` 400s** — adaptive thinking only, and it is **on by default**: a response can begin with `thinking` blocks, so read content by `type` not position, and a `max_tokens` sized for a one-word answer can be consumed by thinking — raise the cap or lower `effort` (`disabled` is still accepted at `high` or below; `between_tools` is Sonnet 5.5-only and 400s here). (2) **Non-default `temperature` / `top_p` / `top_k` 400** — the `temperature: 0` on a classification route is the common casualty; drop it and constrain with structured outputs or an enum-valued tool. (3) **Assistant prefill 400s.** (4) **Computer use only via `computer_toolset_20260801`** on the Claude API and Google Cloud. (5) **Preserved thinking:** editing anything before a replayed thinking block 400s on accounts created on or after 2026-08-31; its blocks are read by Opus 5.5 and Sonnet 5.5 and stay with the account that produced them. **Forced `tool_choice` still works** (unlike Opus 5.5 / Sonnet 5.5 / Fable 5.1) and skips thinking, so the forced-tool extraction pattern in `ANTHROPIC_STRUCTURED_OUTPUT_TOOLUSE.md` carries over — a small `max_tokens` is safe on those routes. **Refusals are new** (HTTP 200, `stop_reason: "refusal"`; categories `cyber`, `bio`, `frontier_llm`, `general_harms`) and **there is no server-side fallback** — sending `fallbacks` returns a 400 or leaves the decline in place; handle it client-side. Also: 512-token cache minimum (4,096 on Haiku 4.5), so short prompts now cache; thinking blocks from earlier turns are kept by default; its own rate-limit row. Migrate with the `claude-api` skill's `migrate` checklist, then re-count prompts and re-sweep `effort` (`low` for classification, extraction and routing) on the route's own evals.
>
> **Fable / Mythos specifics (5 and 5.1):** thinking is always on — an explicit `thinking: {type: "disabled"}` returns 400 (omit the param); requires **30-day data retention** (every request 400s under ZDR unless Anthropic has expressly authorised it).
>
> **Fable 5.1 is not a drop-in for Fable 5 — three breaking changes.** (1) **Forced tool use 400s:** `tool_choice: {type: "any"}` or `{type: "tool", name}` returns `invalid_request_error` (`auto` and `none` are fine; token counting validates the same way). For schema-valid JSON keep `tool_choice: auto` with `strict: true`, or use native structured outputs (`output_config.format`); to make it call a tool, say so in the prompt. **Any forced-`tool_choice` extraction route breaks if pointed at 5.1** — that is the default pattern in `ANTHROPIC_STRUCTURED_OUTPUT_TOOLUSE.md`. (2) **Thinking blocks are one-directional:** 5.1 reads earlier models' blocks, no earlier model reads 5.1's — a router or fallback that switches away mid-conversation silently drops them (reported only with beta `thinking-binding-controls-2026-08-01`). (3) **Editing anything before a 5.1 thinking block invalidates it** (system prompt, tools, an earlier turn, an injected-then-removed reminder): 400 `The block is bound to a different conversation` on accounts created on or after 2026-08-31, recorded-only on older accounts unless `thinking.block_binding.prefix_mismatch_behavior` is set. Treat the conversation as append-only; Claude Code, claude.ai, Managed Agents and the Agent SDK already do. Mythos 5.1 does not run check (3).
>
> **Fable 5.1 behaviour shifts worth a prompt line:** parallel tool calls are more variable (add a one-line batching instruction in custom agent loops), fewer progress updates between tool calls (`thinking.display: "updates"`, beta), more whole-file rewrites for small edits, and less retrieval at `low` effort. Output text carries Anthropic's statistical watermark.
>
> **Refusals on Fable 5.1/5, Mythos 5.1/5, Opus 5.5 and Opus 5:** safety classifiers can decline a request as a **successful HTTP 200** with `stop_reason: "refusal"` — check `stop_reason` before reading `content[0]`, and prefer `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`) over pinning a fallback model. Permitted fallback targets for Fable 5.1 are Opus 5 and Opus 4.8. Opus 5.5 adds `bio` and `reasoning_extraction` categories to `cyber`; server-side fallback never retries a `reasoning_extraction` decline (it comes back to you). In Claude Code, bio-flagged requests on Fable 5.1/5 and Opus 5.5 re-run on Opus 5 and cyber-flagged ones on Opus 4.8.

### Role resolution (single source of truth for MODEL_EFFORT_SELECTION roles)

This table is **the one place** role→id resolution lives. The `MODEL_EFFORT_SELECTION.md` rubric (and the `model-effort-selection` skill) reference roles only; resolve them here at use time. Role leadership is a judgment call re-made on every refresh (capability × cost × harness defaults) — not "newest = frontier".

| Role | Resolves to (2026-10-10) | Why |
|---|---|---|
| **frontier-reasoning** | **Fable 5.1 (`claude-fable-5-1`)** — unchanged | The deliberate escalation above the harness default for the hardest careful solo reasoning: architecture/spec, security, thorny debugging. The docs and the harness still put it there (`best` → Fable 5.1; the docs send you to it when Opus 5.5 at higher effort still falls short). **Its margin is now thin:** Anthropic says Opus 5.5 performs at Fable 5.1's level on most work, and it outscores Fable 5.1 on every launch benchmark (Terminal-Bench 4.0 66.4% vs 55.8%) at 40% of the per-token price. Escalate after Opus 5.5 at `xhigh` has fallen short, not by reflex. |
| **balanced-generalist** | **Opus 5.5 (`claude-opus-5-5`)** — was Opus 5 | Claude Code's `default` and `opus` alias on every plan from v2.1.280, and the docs' starting point for most workloads. Ahead of Opus 5 on every published benchmark, 20% cheaper per token ($4/$20; cache reads $0.20 vs $0.50), and about 40% cheaper per task by Anthropic's figures. Economical base for workflow/fan-out fleets and general main-loop work. |
| **cheap-workhorse** | Sonnet 5 (`claude-sonnet-5`) | Opt-in only: genuinely fungible mechanical subagent stages at real volume. The case for opting in has narrowed: Opus 5.5 is now 2× Sonnet's per-token rate (Opus 5 was 2.5×) and reads cache at the same $0.20, so on cache-heavy agentic stages the saving is small. |
| **cheapest** | **Haiku 5.5 (`claude-haiku-5-5`)** — was Haiku 4.5 | Classification, extraction, routing, sub-agents and bulk work. The docs' current Haiku and its stated successor: $0.10/$0.50 on prompts up to 100k tokens (a tenth of Haiku 4.5's per-token rate, ~7x cheaper per request after the tokeniser change), 1M context, 128k output, `effort` support, and substantially better instruction following and sub-agent behaviour. Haiku 4.5 stays active (retirement commitment to 2026-10-15 only; no deprecation notice yet) as the pin for code that sends `temperature` or `budget_tokens`. |

**What moved this refresh (2026-10-10):** only `cheapest` (Haiku 4.5 → Haiku 5.5), and all three criteria point the same way. *Capability:* the first Haiku-class model with adaptive thinking and `effort`, a 1M window, and (per Anthropic) markedly better instruction following and sub-agent work. *Cost:* $0.10/$0.50 against $1/$5 on the base card; the >100k-token card ($0.50/$2.50) is still half Haiku 4.5's rate. *Harness:* Claude Code's `haiku` alias resolves to it. As with the Opus 5.5 promotion, **this is not a licence to swap `claude-haiku-4-5` → `claude-haiku-5-5` in code** — five breaking changes (above), and the `temperature: 0` + `content[0].text` shape common on classification routes breaks twice. The other three seats were re-read and left: `cheap-workhorse` stays Sonnet 5 (the Sonnet 5.5 judgement is still the owner's, per 1.11), and the Haiku 5.5 launch narrows the case for it further — many "mechanical subagent" stages now fit Haiku 5.5 at a twentieth of the price.

*Previous refresh (2026-09-23):* only `balanced-generalist` (Opus 5 → Opus 5.5), and all three criteria point the same way. *Capability:* ahead of Opus 5 on every launch benchmark (Terminal-Bench 4.0 66.4% vs 52.3%, OSWorld 2.0 81.8% vs 74.0%); per the prompting guide, Opus 5.5 at `medium` matches or beats Opus 5 at `high` on coding and knowledge work, in fewer tokens and with >30% faster output. *Cost:* $4/$20 against $5/$25, cache reads at ×0.05. *Harness:* Claude Code resolves `default` and `opus` to Opus 5.5 from v2.1.280, and the docs now list Opus 5 as legacy. The four breaking API changes above do not bite this role — Claude Code keeps the conversation append-only and never forces `tool_choice` — but they do bite application code: **the role promotion is not a licence to swap `claude-opus-5` → `claude-opus-5-5` in code.** That is a migration with its own checklist (the `claude-api` skill's `migrate`), and forced-`tool_choice` extraction routes break outright. Opus 5 stays active until at least 2027-07-24 as the pin for such code. `frontier-reasoning` was consciously re-decided and stays Fable 5.1 (see its row); the two cheaper seats are unchanged.

*Previous refresh (2026-09-20):* `frontier-reasoning` Fable 5 → Fable 5.1 — stated successor at the same $10/$50 with cache reads at a quarter of the price, and what the harness `fable`/`best` aliases resolve to. Not a licence to swap `claude-fable-5` → `claude-fable-5-1` in code (three breaking changes); Fable 5 stays active until at least 2027-06-09.

### Previous Generation (still available)

| Model | Short Alias | Pinned ID | Context |
|-------|-------------|-----------|---------|
| Opus 4.6 | `claude-opus-4-6` | (alias only) | 1M |
| Sonnet 4.6 | `claude-sonnet-4-6` | (alias only) | 1M |
| Opus 4.5 | `claude-opus-4-5` | `claude-opus-4-5-20251101` | 200k |

### Deprecated (scheduled for retirement)

| Model | ID | Retirement Date |
|-------|----|-----------------|
| Mythos Preview | `claude-mythos-preview` | TBD — migrate to `claude-mythos-5` (Glasswing only) |
| Sonnet 4.5 | `claude-sonnet-4-5-20250929` | 2026-11-30 (deprecated 2026-09-30) — migrate to `claude-sonnet-5-5` |

### Retired (404 on use)

Opus 4.1 (2026-08-05), Sonnet 4 and Opus 4 (2026-06-15), Haiku 3 (2026-04-20), Sonnet 3.7 and Haiku 3.5 (2026-02-19), Opus 3 (2026-01-05), both Sonnet 3.5 snapshots (2025-10-28), Sonnet 3 and Claude 2.x (2025-07-21). Replacements: → `claude-sonnet-5-5`, `claude-haiku-5-5`, or `claude-opus-5-5` by tier (`claude-opus-5` where code still forces `tool_choice` or disables thinking; `claude-haiku-4-5` where it still sends `temperature` or `budget_tokens`).

> **Note:** This inventory is a point-in-time snapshot, refreshed monthly and on model drops. For live capability data (context window, max output, per-feature support) query the Models API — `client.models.retrieve("claude-opus-5-5")` returns `max_input_tokens`, `max_tokens`, and a `capabilities` tree — rather than trusting this table. Verify current models at [Anthropic's model docs](https://platform.claude.com/docs/en/docs/about-claude/models).

---

## Quick Start

```typescript
import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic();

// Use short alias — recommended
const response = await anthropic.messages.create({
  model: "claude-opus-5-5",
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
export const FAST_MODEL = "claude-haiku-5-5";
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
| 1.12 | 2026-10-10 | Roster refresh on a model drop. **Added Claude Haiku 5.5** (`claude-haiku-5-5`, released 2026-10-07 — six days after the 1.11 pass): 1M context, 128k output, adaptive thinking with `effort` (default `medium`), and **two rate cards by prompt length** — $0.10/$0.50 up to 100k prompt tokens, $0.50/$2.50 above, standard cache/batch multipliers on either — verified against platform.claude.com (models overview, pricing, model-deprecations and the Haiku 5.5 model page). `data/anthropic-pricing.json` gained the entry with a new per-model `long_context` block (threshold + second card) and a `units.note` rule that a consumer ignoring it under-reports 5x, the unsafe direction; Haiku 4.5 stays current and priced, marked superseded (docs: active, retirement commitment to 2026-10-15, no notice yet). Added the **Haiku 5.5 API-shape note** (five breaking changes vs Haiku 4.5: `budget_tokens`, non-default sampling params, prefill, computer-use toolset, preserved thinking; thinking on by default; forced `tool_choice` still accepted; refusals with **no server-side fallback**; 512-token cache minimum). **Role-leadership call: `cheapest` Haiku 4.5 → Haiku 5.5**, with the same not-a-licence-to-swap caveat as the Opus 5.5 promotion; the other seats re-read and left. **Correction found on the same pass: Sonnet 5.5 cache reads are ×0.05 ($0.10), not the standard ×0.1 as 1.11 recorded** — override added to the JSON and the cache paragraph; a consumer that copied 1.11 over-reports Sonnet 5.5 cache reads 2x. `claude-haiku-5-5` added to the short-alias examples, the no-dated-variant enumeration, the retired-models replacement line and the `FAST_MODEL` example. Triggered by the estate-wide Haiku audit of 2026-10-10 (three production repos on Haiku 4.5, six holding reference data). |
| 1.11 | 2026-10-01 | Monthly roster verification. **Added Claude Sonnet 5.5** (`claude-sonnet-5-5`, released 2026-09-28 — three days after the 1.10 pass, so neither staleness guard had fired): 1M context, 128k output, $2/$10, cache reads $0.20 at the standard ×0.1, batch $1/$5 — verified against platform.claude.com (models overview, pricing, model-deprecations and the Sonnet 5.5 model page). Sonnet 5 stays in the priced table at the same $2/$10, marked superseded (docs: legacy, active until at least 2027-06-30), and the docs' current line-up line was corrected from *Fable 5.1, Opus 5.5, Sonnet 5, Haiku 4.5* to seat Sonnet 5.5 in the Sonnet slot. `claude-sonnet-5-5` added to the no-dated-variant enumeration and the short-alias examples. **Sonnet 4.5 moved from Previous Generation (still available) to Deprecated** — deprecated 2026-09-30, retirement 2026-11-30, replacement `claude-sonnet-5-5`; the file was listing a deprecated model as still-available. `data/anthropic-pricing.json` gained a `claude-sonnet-5-5` entry and Sonnet 4.5's status moved to `deprecated`; a consumer table without the new row must raise or fall back to the Sonnet family rate ($3/$15, over-reporting 50%) per the unknown-model policy until it adds it. Every other ID, context, max-output and price re-verified unchanged; no new retirements. **Not changed, raised for the owner instead:** the Role resolution table is untouched — `cheap-workhorse` still resolves to Sonnet 5 and Sonnet 5.5 is a judgement call, and the Sonnet 5.5 API-shape notes (five breaking changes vs Sonnet 5) are proposed in the monthly roster-review issue rather than authored here. |
| 1.10 | 2026-09-23 | **Early refresh — the second staleness guard fired again.** Claude Code sessions (and, the same day, the ERS cloud routines) were running on `claude-opus-5-5`, absent from this roster, one day after its 2026-09-22 release. **Added Opus 5.5:** 1M context, 128k output, $4/$20, cache reads $0.20 (×0.05, a new per-model override), fast mode $8/$40 — verified against platform.claude.com (models overview, pricing, what's-new and migration pages) and code.claude.com model-config, not against the bundled `claude-api` skill's cache (whose figures turned out right). Opus 5 stays in the priced table, marked superseded (docs: legacy, active until at least 2027-07-24). **Role-leadership call: `balanced-generalist` Opus 5 → Opus 5.5** on capability × cost × harness; `frontier-reasoning` re-decided and kept on Fable 5.1 with a thin-margin note; cheaper seats unchanged. Added the Opus 5.5 API-shape notes: four breaking changes, the loudest again being that **forced `tool_choice` 400s** — now on the default Opus, so it reaches the default pattern in `ANTHROPIC_STRUCTURED_OUTPUT_TOOLUSE.md` — plus the `medium` effort default. `data/anthropic-pricing.json` gained a `claude-opus-5-5` entry; a consumer table without it must raise or fall back to the Opus family rate ($5/$25, over-reporting 25%) per the unknown-model policy until it adds the row. **Downstream, not ported in this change:** the ERS-adapted copies of this file, `MODEL_EFFORT_SELECTION.md` and `data/anthropic-pricing.json` in ersg-workspace-ops are still at the 2026-09-20 (v1.9) port; the monthly `ers-content-audit` refreshes them, and this row records what they owe. Every other ID, context, max-output and price re-verified unchanged; no new deprecations or retirements. |
| 1.9 | 2026-09-20 | **Early refresh — the roster had missed a model drop.** A Claude Code session found itself running on `claude-fable-5-1`, absent from this inventory. **Added Fable 5.1 and Mythos 5.1** (released 2026-09-01: 1M context, 128k output, $10/$50 — all verified against the docs, not memory); Fable 5 and Mythos 5 stay in the priced table, marked superseded (the docs list them, with Opus 4.8/4.7, as legacy-but-active). **Role-leadership call: `frontier-reasoning` Fable 5 → Fable 5.1**, reasoned on capability × cost × harness rather than recency; the other three seats are unchanged. **The cache-read multiplier is no longer uniform:** 5.1 reads cache at ×0.025, so `data/anthropic-pricing.json` gained an optional per-model `multiplier_overrides` (additive — consumers applying the global ×0.1 over-report 5.1 cache reads 4×, the safe direction). Added the 5.1 API-shape notes — three breaking changes, the loudest being that **forced `tool_choice` now 400s**, which collides with the default pattern in `ANTHROPIC_STRUCTURED_OUTPUT_TOOLUSE.md` — and a second, free staleness guard: *is the model you are running on in the roster?* Root cause of the miss: 5.1 shipped on the day of the 1.8 verification, which recorded "no model launched", and the 45-day date guard cannot see a drop that lands just after a refresh. Every other ID, context, max-output and price re-verified unchanged; no new retirements. |
| 1.8 | 2026-09-01 | Monthly roster verification. The Current Model Inventory needed no change — no model launched since 1.7, and every model ID, context, max-output, and pricing value matches the docs (Fable 5 $10/$50, Opus 5 $5/$25, Sonnet 5 $2/$10, Haiku 4.5 $1/$5; `data/anthropic-pricing.json` reconciles clean). One mechanical correction: **Opus 4.1 moved from Deprecated to Retired** — its 2026-08-05 retirement date has passed and the docs now list `claude-opus-4-1-20250805` as Retired, so the Deprecated table was asserting a future retirement for a model that already 404s. Mythos Preview remains the only deprecated model. Also brought the document footer's version stamp (still reading 1.5 / 2026-07-26) into line with the header. Role resolution table untouched. |
| 1.5 | 2026-07-26 | Monthly roster verification. The Current Model Inventory needed no change — no model launched or retired since 1.4, and every pricing, context, and max-output value matches the docs. Mechanical corrections elsewhere: **dateless IDs are pinned snapshots, not evergreen pointers** — the "alias always resolves to the latest snapshot" claim is true only for pre-4.6 models, so the Model-ID-Format paragraph, the alias-vs-pinned table, and the behaviour-drift troubleshooting entry were corrected (drift on a current-gen ID is *serving infrastructure* — router, safety classifiers, sampling — not a silent weight swap). Fixed **Opus 4.5 and Sonnet 4.5 context: 1M → 200k** (the full 1M window is a 4.6-and-later feature). Deprecations trued up: **Sonnet 4 and Opus 4 retired 2026-06-15** and **Haiku 3 retired 2026-04-20** (listed as pending-with-TBD and with a wrong 04-19 date) moved to Retired, leaving Opus 4.1 as the only deprecated model; added `claude-mythos-preview` (now deprecated, migrate to `claude-mythos-5`). Role resolution table untouched. |
| 1.7 | 2026-08-18 | **Prices are now canonical as data, not prose.** Added [`data/anthropic-pricing.json`](https://github.com/JEM-Fizbit/ai-knowledge/blob/main/protocols/data/anthropic-pricing.json) — per-model-id rates plus `verified_on`, the staleness rule, cache/batch multipliers, an explicit unknown-model policy, and the list of consuming projects — and `scripts/check-anthropic-pricing.py`, which reconciles it against the markdown table and applies the staleness guard. Motivation: an audit of the estate on 2026-08-18 found the same rates hand-copied into four repos in three different states of wrongness — pharma-signal-poc at Opus $15/$75 (3x, two generations stale), Social-Creator-Claude and aigent-alpha both at Sonnet 5 $3/$15 (50% high, on the cancelled-reversion premise this protocol corrected in 1.6). The 1.6 correction reached the protocol and none of the code, because markdown cannot be imported. Each consumer now reads the JSON and is audited by `knowhub-doctor.sh`, which was extended to cover non-markdown managed outputs. |
| 1.6 | 2026-08-14 | Corrected the **Sonnet 5 price to a permanent $2/$10** — the scheduled 2026-09-01 rise to $3/$15 was cancelled, and this table asserting otherwise over-budgeted every Sonnet 5 estimate by ~50% while making the older, dearer Sonnet 4.6 look competitive. Added a **Pricing notes** block: the 4.7+ tokeniser emitting ~30% more tokens (measured +26%), cache/batch multipliers incl. the routinely-forgotten 50% Batch API discount, and the finding that **`effort` outweighs model choice on output-heavy jobs** (low vs medium: −37% cost, 0.985 agreement; Opus 5 at 2.5× the price agreed only 0.962). |
| 1.4 | 2026-07-25 | Added the **`Roster verified` date + 45-day staleness guard** in the header. Detection, not propagation, was the gap the 1.3 refresh exposed: role indirection meant one edit reached the skill, plugin, and ERS mirror with zero edits to any of them, but the roster itself sat weeks stale with the harness default missing and nothing surfaced it. The guard is deliberately read-time-only (a date comparison on a file already being read) — recorded the rule that the Models API must **not** be called on the advice path, since a live lookup is an extra inference turn per invocation to track a monthly-cadence fact, and can supply neither pricing nor role leadership. |
| 1.3 | 2026-07-25 | Roster refresh. **Added Opus 5** (missing entirely — the current Opus and the Claude Code main-loop default) and **Mythos 5** (Glasswing-only twin of Fable 5). **Role-leadership call: `balanced-generalist` Opus 4.8 → Opus 5** (harness default + strictly better at the same $5/$25; Fable 5 keeps frontier-reasoning). Added a pricing column so the capability×cost half of the judgment is auditable in-table. Corrected the pinned-ID guidance: the current generation has **no** dated variants (the alias is the complete ID) — removed three invented/wrong pinned IDs (`claude-opus-4-6-20250918`, `claude-sonnet-4-6-20250929`, and Sonnet 4.5 mislabelled with Sonnet 4's `20250514` date), added the Vertex `@`-separator note and a date-suffix anti-pattern. Added Opus 5 API-shape notes (thinking on by default; disabled-thinking capped at effort ≤ `high`; 512-token cache minimum; separate rate-limit bucket), a refusal/`fallbacks: "default"` note, deprecations (Opus 4.1 retires 2026-08-05), and a retired-models line. |
| 1.2 | 2026-07-11 | Added Role-resolution table as the single source of truth for MODEL_EFFORT_SELECTION roles; promoted Fable 5 to frontier-reasoning (most capable GA model), Opus 4.8 to balanced-generalist. |
| 1.1 | 2026-07-03 | Refreshed inventory — Fable 5, Opus 4.8/4.7, Sonnet 5 now current; 4.6 family moved to previous-gen. Added current-family API-shape notes (adaptive thinking only; `budget_tokens`/sampling params removed; effort parameter). Updated examples to current model IDs. |
| 1.0 | 2026-03-28 | Initial release — model ID format, current inventory, anti-patterns |

---

**Protocol Version**: 1.12
**Last Updated**: 2026-10-10
**Original Source**: Social-Creator-Claude project (production incident from using invalid `-latest` aliases)
