# slm-lab

A learn-by-doing lab for **building, fine-tuning, and distilling small language models** on Apple Silicon — paired with a useful biopharma proof-of-concept.

Two tracks, one shared environment and eval harness:

- **Track A — from scratch** (`notebooks/01_…`, `02_…`): pretrain a tiny GPT on Apple MLX to *understand* every layer — tokenizer, attention, training loop, sampling. Output is throwaway-quality by design; the point is comprehension. Once trained, **save the model and chat with it** (no retraining) via `notebooks/03_tiny_gpt_chat.ipynb` or the terminal REPL `notebooks/chat.py`.
- **Track B — TrialScout** (`track-b-trialscout/`): distill/fine-tune a small open model (Qwen3-4B vs Gemma 4 E2B, decided by eval) that turns a **clinical-trial record into a structured, investor-relevant readout**. Ships as an MCP-callable "expert."

## Why this exists

Learning, with utility as the target. A small model won't be a good general analyst — but it *can* be excellent at one narrow, structured task. TrialScout is that task. Every phase is built to be **observable**: annotated notebooks, live loss curves, a decision log, and no magic numbers — so the process is learnable, not a black box.

## Quick start

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

See `BACKLOG.md` for live work and `docs/DECISIONS.md` for locked design decisions. Phase plan: (1) tiny GPT from scratch → (2) trial data pipeline → (3) LoRA fine-tune → (4) recursive eval loop → (5) package as MCP expert.

## License

Personal project — John E. Milad. Base models are Apache-2.0; data sources are public-domain.
