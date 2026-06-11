# small-model-lab

A learn-by-doing lab for **building, fine-tuning, and distilling small language models** on Apple Silicon — paired with a useful biopharma proof-of-concept.

> 📖 **Start here → [the small-model-lab walk-through](https://jem-fizbit.github.io/small-model-lab/)** — an interactive, plain-English guide in three parts: **Part 0 · Concepts** explains how a language model works (no code, with diagrams); **Part 1 · Pre-training** builds a tiny GPT from scratch; **Part 2 · Post-training** fine-tunes a real model into a useful expert (TrialScout). No prior Python required to read along.

Two tracks, one shared environment and eval harness:

- **Track A — from scratch** (`notebooks/01_…`, `02_…`): pretrain a tiny GPT on Apple MLX to *understand* every layer — tokenizer, attention, training loop, sampling. Output is throwaway-quality by design; the point is comprehension. Once trained, **save the model and chat with it** (no retraining) via `notebooks/03_tiny_gpt_chat.ipynb` or the terminal REPL `notebooks/chat.py`.
- **Track B — TrialScout** (`track-b-trialscout/`): distill/fine-tune a small open model (Qwen3-4B vs Gemma 4 E2B, decided by eval) that turns a **clinical-trial record into a structured, investor-relevant readout**. Ships as an MCP-callable "expert."

## Why this exists

Learning, with utility as the target. A small model won't be a good general analyst — but it *can* be excellent at one narrow, structured task. TrialScout is that task. Every phase is built to be **observable**: annotated notebooks, live loss curves, a decision log, and no magic numbers — so the process is learnable, not a black box.

## Quick start

> **New to this?** See **[Getting Started](docs/GETTING_STARTED.md)** for a from-zero walkthrough — installing tools, what a Jupyter notebook is, and how to run cells, with no prior coding assumed. (Even gentler conceptual primers — terminal, dependencies, Jupyter — live in my [AI Knowledge Hub](https://possible-meeting-f8b.notion.site/AI-Knowledge-Hub-718881b895cb4666a2fcfc1887b77566).)
>
> **Requires an Apple-Silicon Mac** (the from-scratch model uses Apple [MLX](https://github.com/ml-explore/mlx), which is Apple-only). First [install `uv`](https://docs.astral.sh/uv/getting-started/installation/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`), then:

```bash
uv sync                 # create .venv (Python 3.12) and install deps
cp .env.example .env    # fill ANTHROPIC_API_KEY before Track B Phase 2 (not needed for Track A)
uv run jupyter lab      # open the annotated notebooks in notebooks/
```

Chat with the from-scratch GPT (Track A) — train once, then talk to it anytime:

```bash
uv run python notebooks/train_v2_checkpoint.py   # one-time, ~16 min → saves notebooks/checkpoints/tiny_gpt_v2/
uv run python notebooks/chat.py                  # loads in ~1s; type story openers. /temp /tokens /stop /quit
```

(`Run All` on `notebooks/02_tiny_gpt_tuned.ipynb` also saves the checkpoint, at the "9.5 Save" cell.)

**Using the chat REPL.** It's a *TinyStories* model — it continues text, it doesn't answer questions. Feed it story-shaped openers with capitalized names (`Once upon a time, there was a boy named Chester.`), not fragments or questions. In-prompt commands (each prints the resulting state):

| Command | Effect |
|---------|--------|
| `/temp 0.7` | sampling temperature — low (~0.5) safe/repetitive, high (~1.1) wild |
| `/tokens 300` | **max** tokens per reply (a cap; the story usually ends on its own first) |
| `/stop` | toggle stopping at the end-of-story token on/off (on by default) |
| `/quit` | exit |

**Story length & the end-of-story token.** The model is trained with a dedicated end-of-text token (`<|endstory|>`, the same trick as GPT-2's `<|endoftext|>`): during training each story is followed by this token, so the model learns to emit it when a story is complete, and generation **stops there** — giving naturally varying, self-contained stories rather than a fixed-length wall of text. `/tokens` is just a safety cap. Toggle `/stop` **off** (or launch `chat.py --no-stop`) to ignore the token and keep generating, which rolls on into new stories. (Earlier checkpoints lacked this token because training joined stories with `\n\n` — also the paragraph break *inside* nearly every story — so there was no boundary to stop on; the producer now inserts a real one. See `notebooks/train_v2_checkpoint.py`.)

## Tech stack

| Area | Choice |
|------|--------|
| Compute | Apple Silicon (M5, 24GB), local-first |
| Framework | Apple MLX + `mlx-lm` |
| Base models | Qwen3-4B-Instruct-2507 / Gemma 4 E2B (Apache-2.0) |
| Teacher / judge | Anthropic Claude (Sonnet) |
| Data | ClinicalTrials.gov, openFDA, SEC EDGAR (public-domain) |

## Roadmap

See `docs/DECISIONS.md` for the locked design decisions (the *why* trail). Phase plan: (1) tiny GPT from scratch → (2) trial data pipeline → (3) LoRA fine-tune → (4) recursive eval loop → (5) package as MCP expert.

## License

[MIT](LICENSE) © 2026 John E. Milad. Use it, learn from it, build on it.

## Acknowledgments

This lab stands on open work:

- **[nanoGPT](https://github.com/karpathy/nanoGPT)** (Andrej Karpathy, MIT) — the from-scratch GPT in Track A follows its architecture and spirit.
- **[Apple MLX](https://github.com/ml-explore/mlx)** + `mlx-lm` (MIT) — the local-first training/inference framework.
- **[TinyStories](https://huggingface.co/datasets/roneneldan/TinyStories)** (Eldan & Li, Microsoft Research; CDLA-Sharing-1.0) — the tiny corpus Track A learns from. *(Not redistributed here — fetched at runtime; only a short sample appears in the notebooks.)*
- Track B base models — **Qwen3-4B** (Apache-2.0) and **Gemma 4 E2B** (Gemma Terms of Use) — each under its own license.
- The walk-through page is built with **[Pygments](https://pygments.org/)** (BSD) and **[Jinja2](https://palletsprojects.com/p/jinja/)** (BSD).

Track B's clinical-trial / regulatory data comes from public-domain sources: ClinicalTrials.gov, openFDA, and SEC EDGAR.
