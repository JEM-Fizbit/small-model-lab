# Getting started — run the tiny GPT yourself, from zero

This guide assumes **no prior coding experience**. It takes ~15 minutes and is free.

> Pairs with the plain-English **[walk-through](https://jem-fizbit.github.io/slm-lab/)**, which explains *how* the model works. This page is just *how to run it*.
>
> **Want gentler, conceptual primers first?** My public [AI Knowledge Hub](https://notion.so/718881b895cb4666a2fcfc1887b77566) has from-zero guides to the terminal, dependencies, and Jupyter notebooks.

## Do you even need to install anything?

**No — not to learn.** To understand the model, read the [walk-through](https://jem-fizbit.github.io/slm-lab/), or open the notebooks right here on GitHub: [`01`](../notebooks/01_tiny_gpt_from_scratch.ipynb), [`02`](../notebooks/02_tiny_gpt_tuned.ipynb), [`03`](../notebooks/03_tiny_gpt_chat.ipynb). They're saved **with their outputs**, so you can read the real code *and* see what it produced without running anything.

To **train and chat with your own model**, follow the steps below.

## What you need

- **An Apple-Silicon Mac** (M1, M2, M3, M4 — any Apple-chip Mac). The code uses Apple's **MLX**, which only runs on Apple Silicon. On Windows or Linux it won't run — but you can still read everything above.
- About **15 minutes** and ~1 GB of free space.
- **No paid accounts.** Track A (the tiny GPT) is entirely free. (Track B needs an API key for one step — ignore it.)

## Step 1 — Open the Terminal

The **Terminal** is a window where you type commands instead of clicking. Press **⌘ + Space**, type `Terminal`, press **Enter**. You'll paste a few lines below — press **Enter** after each.

## Step 2 — Install `uv` (one line)

`uv` is a small tool that sets up the correct Python and all the project's dependencies for you, so you never have to manage any of that yourself. Paste this and press Enter:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then **close and reopen** the Terminal so it picks up `uv`.

## Step 3 — Get the code

**Option A — with git** (if you have it):

```bash
git clone https://github.com/JEM-Fizbit/slm-lab.git
cd slm-lab
```

**Option B — no git:** on the [repo page](https://github.com/JEM-Fizbit/slm-lab), click the green **`Code ▾`** button → **Download ZIP**, unzip it, then in Terminal move into the folder, e.g.:

```bash
cd ~/Downloads/slm-lab-main
```

## Step 4 — Start Jupyter

```bash
uv run jupyter lab
```

The **first** run takes a couple of minutes (it's downloading Python and the libraries). Then a tab opens in your browser.

**What is this?** A **Jupyter notebook** is a single document where code, explanatory notes, and live results sit together, and you run it one chunk — a **"cell"** — at a time. It's the standard way people explore machine-learning code.

## Step 5 — Run a notebook

In the left sidebar, open **`notebooks/01_tiny_gpt_from_scratch.ipynb`**.

- **Run one cell:** click it, then press **Shift + Enter**. Its output appears right below.
- **Run everything:** menu **Run ▸ Run All Cells**.

Watch the loss fall and, at the end, the model generate text. Notebook `01` trains in ~5 minutes; **`02`** is the better model (~20 minutes) and saves itself when done.

## Step 6 — Chat with your model

Once `02` has finished (it saves the trained model), you can talk to it anytime — no retraining. Open a new Terminal tab in the project folder and run:

```bash
uv run python notebooks/chat.py
```

Type a **story opener** and watch it continue:

```
Once upon a time, there was a boy named Sam.
```

In-chat commands: `/temp 0.7` (creativity), `/tokens 200` (length cap), `/quit`.

⚠️ **It only tells little children's stories** — that's all it was ever trained on, so it *can't answer questions or hold a conversation*. Feed it story openers, not questions. (Why? See **"the corpus is the model"** in the [walk-through](https://jem-fizbit.github.io/slm-lab/) — it's the whole point.)

## Notes & common hiccups

- **Not on a Mac?** You can't run MLX, but you can read the notebooks (with outputs) on GitHub and the walk-through online — that's most of the value.
- **Track B (TrialScout)** needs an Anthropic API key for its labeling step — *not* needed for Track A. Only if you go there: `cp .env.example .env` and add your key.
- **Something broke?** Open an [issue](https://github.com/JEM-Fizbit/slm-lab/issues) with what you ran and the error.
