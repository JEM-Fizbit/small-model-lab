# CLAUDE.md — slm-lab

Guidance for AI coding agents (and humans) working in this repo. Design decisions live in [`docs/DECISIONS.md`](docs/DECISIONS.md); running history is in git.

> **New here?** Read the [README](README.md), then the live walk-through → https://jem-fizbit.github.io/slm-lab/

## What this is

A learn-by-doing lab for **building, fine-tuning, and distilling small language models**, paired with a useful biopharma POC. Two tracks share one env + eval harness:

- **Track A** (`notebooks/01_…`, `02_…`, `03_…`): a tiny GPT pretrained *from scratch* on Apple MLX — learning-focused, throwaway output quality by design. The plain-English walk-through is generated from these notebooks by `docs/walkthrough/build.py`.
- **Track B** (`track-b-trialscout/`): fine-tune/distill a small open model into **TrialScout** (clinical-trial record → structured JSON readout); ships as an MCP-callable expert.

## Learning-first principle (load-bearing)

This project exists to make the process **learnable — no black boxes**. Every phase ships: an annotated notebook (narrated *why* beside runnable code and live output), loss/eval curves, a `docs/DECISIONS.md` entry per modeling choice, and **no magic numbers** (hyperparameters in commented configs with "try X, watch Y" notes). Notebook outputs are committed on purpose — they ARE the learning trail.

## Commands

```bash
uv sync                  # install deps into .venv (Python 3.12)
uv run jupyter lab       # open the annotated notebooks
uv run ruff check .      # lint
```

## Gotchas

1. **Python pinned to 3.12** (not 3.14): MLX/torch wheels. `.python-version` = 3.12; `requires-python = ">=3.12,<3.13"`.
2. **Weights & data are gitignored** (`*.safetensors`, `*.gguf`, `data/raw/`, `data/gold/`, adapters) — regenerable from scripts, never committed. Notebooks (with outputs) ARE committed.
3. **Base-model choice is measured, not assumed** — Qwen3-4B vs Gemma 4 E2B is decided by the eval harness (see `docs/DECISIONS.md`).
4. **Teacher quality caps student quality** — Track B uses a strong teacher (Claude Sonnet) for gold labels.
