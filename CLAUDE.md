# CLAUDE.md — small-model-lab

Guidance for AI coding agents (and humans) working in this repo. Design decisions live in [`docs/DECISIONS.md`](docs/DECISIONS.md); running history is in git.

> **New here?** Read the [README](README.md), then the live walk-through → https://jem-fizbit.github.io/small-model-lab/
> **Before running commands:** read [`docs/TOOLING.md`](docs/TOOLING.md) for runtime assumptions, artifact policy, and script safety categories.

## What this is

A learn-by-doing lab for **building, fine-tuning, and distilling small language models**, paired with a useful biopharma POC. Two tracks share one env + eval harness:

- **Track A** (`notebooks/01_…`, `02_…`, `03_…`): a tiny GPT pretrained *from scratch* on Apple MLX — learning-focused, throwaway output quality by design. The plain-English walk-through is generated from these notebooks by `docs/walkthrough/build.py`.
- **Track B** (`track-b-trialscout/`): fine-tune/distill a small open model into **TrialScout** (clinical-trial record → structured JSON readout); ships as an MCP-callable expert.

## Protocol Triggers

Read the matching protocol before working in its domain (synced from ai-knowledge via knowhub; `docs/protocols/` is overwritten on sync):

- ClinicalTrials.gov API work -> docs/protocols/CLINICALTRIALS_GOV_API.md
- Packaging a local model as an MCP-callable expert -> docs/protocols/LOCAL_MODEL_MCP_EXPERT.md
- Small-LM fine-tuning / distillation / improvement -> docs/protocols/SLM_DISTILLATION_AND_IMPROVEMENT.md

## Repository layout — public / private split (read before committing)

This repo is **public**. Internal/personal material lives in a separate **private** repo, [`JEM-Fizbit/small-model-lab-private`](https://github.com/JEM-Fizbit/small-model-lab-private), cloned into `_private/` here (gitignored — present locally, never pushed to this repo).

- **Public (this repo):** the learning content — `notebooks/`, the `docs/walkthrough/` builder, the Track B pipeline (`track-b-trialscout/`), `docs/DECISIONS.md` (the *why* trail), `README.md`, `docs/GETTING_STARTED.md`.
- **Private (`_private/`):** the live `BACKLOG.md`, `HANDOFF.md` (status / "resume here"), the full agent contract (`_private/CLAUDE.md`, with personal context), and `specs/`. Edit and version these *inside* `_private/` — it is its own git repo (`cd _private && git add/commit/push`).

**Rules when working here:**
- **Do not commit personal/internal content to this public repo** — no live backlog, status/handoff notes, business strategy, absolute home paths (`/Users/…`, `~/Projects/…`), or references to private repos. That content belongs in `_private/`.
- **Resuming, or looking for status / the task list?** Read **`_private/HANDOFF.md`** and **`_private/BACKLOG.md`** (local, gitignored — not visible on GitHub).
- The git **history was rewritten (2026-06-08)** to purge such content from all commits — don't reintroduce it.
- `.mcp.json` is gitignored (local, per-user path); copy `.mcp.json.example` and set your path.

## Learning-first principle (load-bearing)

This project exists to make the process **learnable — no black boxes**. Every phase ships: an annotated notebook (narrated *why* beside runnable code and live output), loss/eval curves, a `docs/DECISIONS.md` entry per modeling choice, and **no magic numbers** (hyperparameters in commented configs with "try X, watch Y" notes). Notebook outputs are committed on purpose — they ARE the learning trail.

## Commands

```bash
uv sync                  # install deps into .venv (Python 3.12)
uv run jupyter lab       # open the annotated notebooks
uv run ruff check .      # lint
```

`uv run` can synchronize the environment if it is missing or stale. For docs/metadata-only work, prefer `git diff --check` and `uv lock --check`; see [`docs/TOOLING.md`](docs/TOOLING.md).

## Gotchas

1. **Python pinned to 3.12** (not 3.14): MLX/torch wheels. `.python-version` = 3.12; `requires-python = ">=3.12,<3.13"`.
2. **Weights & data are gitignored** (`*.safetensors`, `*.gguf`, `data/raw/`, `data/gold/`, adapters) — regenerable from scripts, never committed. Notebooks (with outputs) ARE committed.
3. **Base-model choice is measured, not assumed** — Qwen3-4B vs Gemma 4 E2B is decided by the eval harness (see `docs/DECISIONS.md`).
4. **Teacher quality caps student quality** — Track B uses a strong teacher (Claude Sonnet) for gold labels.
