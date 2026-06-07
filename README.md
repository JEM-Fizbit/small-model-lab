# slm-lab

A learn-by-doing lab for **building, fine-tuning, and distilling small language models** on Apple Silicon — paired with a useful biopharma proof-of-concept.

Two tracks, one shared environment and eval harness:

- **Track A — from scratch** (`notebooks/01_…`, `02_…`): pretrain a tiny GPT on Apple MLX to *understand* every layer — tokenizer, attention, training loop, sampling. Output is throwaway-quality by design; the point is comprehension.
- **Track B — TrialScout** (`track-b-trialscout/`): distill/fine-tune a small open model (Qwen3-4B vs Gemma 4 E2B, decided by eval) that turns a **clinical-trial record into a structured, investor-relevant readout**. Ships as an MCP-callable "expert."

## Why this exists

Learning, with utility as the target. A small model won't be a good general analyst — but it *can* be excellent at one narrow, structured task. TrialScout is that task. Every phase is built to be **observable**: annotated notebooks, live loss curves, a decision log, and no magic numbers — so the process is learnable, not a black box.

## Quick start

```bash
uv sync                 # create .venv (Python 3.12) and install deps
cp .env.example .env    # fill ANTHROPIC_API_KEY before Track B Phase 2 (not needed for Track A)
uv run jupyter lab      # open the annotated notebooks in notebooks/
```

## Tech stack

| Area | Choice |
|------|--------|
| Compute | Apple Silicon (M5, 24GB), local-first |
| Framework | Apple MLX + `mlx-lm` |
| Base models | Qwen3-4B-Instruct-2507 / Gemma 4 E2B (Apache-2.0) |
| Teacher / judge | Anthropic Claude (Sonnet) |
| Data | ClinicalTrials.gov, openFDA, SEC EDGAR (public-domain) |

## Roadmap

See `BACKLOG.md` for live work and `docs/DECISIONS.md` for locked design decisions. Phase plan: (1) tiny GPT from scratch → (2) trial data pipeline → (3) LoRA fine-tune → (4) recursive eval loop → (5) package as MCP expert.

## License

Personal project — John E. Milad. Base models are Apache-2.0; data sources are public-domain.
