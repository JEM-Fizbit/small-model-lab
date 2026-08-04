"""gen_domain_limit_probe.py — measure what the Track A model ACTUALLY does off-corpus.

Part 1 § "The honest ceiling" claims the tiny GPT "only tells toddler stories, because
TinyStories is the entire world it ever saw" — and the usual shorthand for that is
"ask it the capital of France and you get 'once upon a time'." That shorthand had never
been run. This script runs it, and writes every sample down verbatim, including the ones
that contradict the claim.

Design (this is a measurement, so the protocol is fixed before the run, not after):

  * Three prompts, held at the SAME sampling settings:
      - `question`  — an instruction-shaped question. The model is a BASE completion model,
                      never instruction-tuned, so this is the unfair-but-obvious phrasing.
      - `statement` — the same fact as a sentence to be continued. This is the phrasing a
                      base LM is actually built for, and the fair test of factual recall.
      - `control`   — a fairy-tale-shaped SENTENCE STEM, deliberately the same grammatical
                      shape as `statement` (an incomplete sentence to continue), so the only
                      variable between them is DOMAIN, not prompt form. A canonical
                      "Once upon a time" opener would have confounded shape with domain.
  * Sampling settings are the library/notebook defaults, not tuned for this probe
    (see TEMPERATURE / MAX_NEW_TOKENS / STOP_AT_EOS below).
  * Sampling goes through `tiny_gpt.stream` — the real code path `chat.py` and the notebook
    use. Nothing is reimplemented here, so this measures the shipped sampler.
  * The marker tests below are crude lexical checks, declared up front so they can't be
    tuned to flatter a conclusion. The verbatim text is the real evidence; the markers just
    make the table skimmable.

    uv run python docs/walkthrough/gen_domain_limit_probe.py

Writes DOMAIN_LIMIT_PROBE_RESULTS.md next to this file (regenerate; don't hand-edit it).
"""
import re
import sys
from datetime import date
from pathlib import Path

import mlx.core as mx
from mlx.utils import tree_flatten

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "notebooks"))
import tiny_gpt  # noqa: E402

# --- what we run against -------------------------------------------------------
# The only Track A checkpoint that exists on disk: the TUNED model from notebook 02
# (8k byte-level BPE, 17.05M params). Notebook 01's char-level "v1" model is trained
# inline and never saved, so there is no v1 checkpoint to compare against.
CKPT = REPO / "notebooks" / "checkpoints" / "tiny_gpt_v2"
OUT = Path(__file__).resolve().parent / "DOMAIN_LIMIT_PROBE_RESULTS.md"

# --- sampling settings (all defaults — nothing here was tuned for this probe) ---
TEMPERATURE = 0.8      # tiny_gpt.generate() default, and chat.py's default
MAX_NEW_TOKENS = 200   # tiny_gpt.generate() default (a cap; eos usually fires first)
TOP_K = None           # the sampler has NO top-k: tiny_gpt.stream samples with
                       # mx.random.categorical over the full temperature-scaled
                       # logit vector. Recorded as None rather than invented.
STOP_AT_EOS = True     # library default: stop when the model emits <|endstory|>
N_SAMPLES = 5          # samples per prompt

# Seed is fixed for reproducibility and was chosen BEFORE any output was seen —
# picking a seed after reading the samples would be cherry-picking, which is the one
# thing this probe exists to avoid. Sample i of every prompt uses SEED + i, so the
# same RNG stream start is shared across prompts (a control) and each individual
# sample is reproducible on its own.
SEED = 0

PROMPTS = [
    ("question",  "What is the capital of France?"),
    ("statement", "The capital of France is"),
    ("control",   "Once upon a time there was a little girl who"),
]

# --- marker tests (declared before the run; crude by design) -------------------
# Does the continuation OPEN with fairy-tale framing? Tested against the first
# OPENER_WINDOW_CHARS characters only — the essay's claim is about how it opens.
STORY_OPENERS = ("once upon a time", "one day", "there was a", "there lived", "there once")
OPENER_WINDOW_CHARS = 60
# Children's-story register anywhere in the continuation (vocabulary, not framing).
CHILD_REGISTER = ("little girl", "little boy", "mom", "mum", "dad", "happily ever after",
                  "once upon a time", "one day", "play", "toy", "happy", "smile")
# The direct factual test for the France prompts: does the right answer ever appear?
FACT_MARKERS = ("paris",)
# The literal phrase the essay's shorthand predicts, tested anywhere in the continuation
# (not just the opener window) — this is the exact claim under test.
CLAIM_PHRASE = "once upon a time"
# Does the model ever pick the prompt's subject back up, or does it just drop it?
SUBJECT_MARKERS = ("france", "capital")


def hits(text, markers):
    low = text.lower()
    return [m for m in markers if m in low]


def fence(text):
    """A code fence longer than the longest backtick run in `text`, so nothing leaks."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def run():
    model, tok, cfg = tiny_gpt.load(str(CKPT))
    n_params = sum(v.size for _, v in tree_flatten(model.parameters()))
    results = []
    for kind, prompt in PROMPTS:
        samples = []
        for i in range(N_SAMPLES):
            mx.random.seed(SEED + i)
            cont = "".join(tiny_gpt.stream(model, tok, cfg, prompt,
                                           n_new=MAX_NEW_TOKENS,
                                           temperature=TEMPERATURE,
                                           stop_at_eos=STOP_AT_EOS))
            # Re-encoding the continuation is an approximation of the emitted token
            # count (BPE round-trip is not guaranteed identical), so the stop reason
            # below is labelled "inferred" in the report rather than asserted.
            n_tok = len(tok.encode(cont).ids)
            samples.append({
                "seed": SEED + i,
                "continuation": cont,
                "chars": len(cont),
                "approx_tokens": n_tok,
                "hit_cap": n_tok >= MAX_NEW_TOKENS,
                "opens_story": bool(hits(cont[:OPENER_WINDOW_CHARS], STORY_OPENERS)),
                "claim_phrase": CLAIM_PHRASE in cont.lower(),
                "register": hits(cont, CHILD_REGISTER),
                "fact": hits(cont, FACT_MARKERS),
                "subject": hits(cont, SUBJECT_MARKERS),
            })
        results.append({"kind": kind, "prompt": prompt, "samples": samples})
    return results, n_params, cfg


# --- the verdict ---------------------------------------------------------------
# Written AFTER the first run, from the samples below; re-stated here so one command
# regenerates the whole report and the prose can never drift from the data it describes.
# Tied to SEED — if you change the seed or the settings above, re-read and rewrite this.
VERDICT = """
**No. The model never opens with "Once upon a time" on either France prompt — 0 of 10
samples.** It also never says "Paris" (0/10), and never picks the words "France" or
"capital" back up after the prompt (0/10): it drops the subject on the very next token and
does not return to it.

What it actually does is continue the prompt as TinyStories prose — and the two phrasings
fail in visibly different ways:

- **`The capital of France is`** — it finishes the sentence with a story-register predicate
  and moves on: *"is going on a faraway journey"*, *"is special."*, *"is fixed!"*,
  *"is fun."*, *"is better than before and its original size."* All five then run on into a
  small story populated by TinyStories regulars (Tim, Sam, Timmy, Mr. Smith), and all five
  terminate cleanly at `<|endstory|>`. Fairy-tale framing does show up here, but as
  *register*, not as an opener: sample 1 closes with "And they all lived happily ever
  after," and sample 4 pivots straight into "One day, …".
- **`What is the capital of France?`** — the more degraded of the two. The model reads the
  question as **a line of dialogue inside a scene already in progress** and carries the
  scene on: four of the five samples emit a closing quotation mark that no opening quote
  ever matched, and sample 2 attributes the question to a character outright —
  *`France?â€ Tom said, pointing to a book on the wall`* (that `â€` is a mangled closing
  curly quote — see "Also observed"). None answers. 2 of 5 never reach an
  end-of-story token at all and run to the 200-token cap, against 0 of 5 for the statement
  form: the question mark actively destabilises it.

The control (`Once upon a time there was a little girl who`) returns coherent, on-genre
toddler fiction in 5/5 samples, every one of them containing "One day". So the contrast is
not story-mode versus some other mode — it is **fluent** versus **unanchored**.

Which means the claim's substance holds and its wording does not. The model doesn't *reach
for* a fairy-tale opener when it's out of its depth, because there is no other mode for it
to switch out of. It is always already mid-story; a question about France is just more story
to continue.
""".strip()

SIDE_OBSERVATION = """
The model also reproduces its corpus's **encoding bugs**. `â€œ` appears mid-sentence in two
samples (question sample 2, control sample 5). This is not a fault in this script or in the
tokenizer's decoder — valid curly quotes round-trip through it cleanly. It is upstream:
**~2% of TinyStories stories ship with double-encoded UTF-8** (sampling 3,000 stories from
the published train split gives 60 hits, e.g. `daddyâ€™s tie` where `daddy's tie` was meant),
and `train_v2_checkpoint.py` reads `ex["text"]` straight from `load_dataset` without
re-encoding, so it inherits them as-is.

At that rate the byte-pairs recur often enough for the BPE to spend **73 of its 8,192
tokens** on mojibake fragments — including dedicated merges for `œMommy`, `œHello`,
` couldnâ` and `€™` (that is, `"Mommy`, `"Hello` and ` couldn'` as the corpus mis-encodes
them). Roughly 0.9% of the vocabulary is modelling a text-encoding bug rather than English.

It is a sharper version of the point the section is already making: the corpus is the model,
down to its defects.

*Since this run:* the data path now repairs the mojibake on load and seeds its RNGs
(`docs/DECISIONS.md` ADR-0013). This checkpoint predates both, so the samples above still
show the artifact — retraining would re-roll every figure derived from it, which is why it
has not been done yet.
""".strip()


def report(results, n_params, cfg):
    ck = CKPT.relative_to(REPO)
    topk_note = str(TOP_K) if TOP_K is not None else (
        "**none** — the sampler has no top-k; it samples over the full "
        "temperature-scaled distribution")
    L = [
        "# What the tiny GPT actually does off-corpus — the \"capital of France\" probe",
        "",
        "<!-- GENERATED FILE — do not hand-edit. -->",
        "<!-- Regenerate: uv run python docs/walkthrough/gen_domain_limit_probe.py -->",
        "",
        "**Question.** Part 1 § \"The honest ceiling\" says the model \"*only* tells toddler",
        "stories, because TinyStories is the entire world it ever saw,\" and the shorthand for",
        "that claim is \"ask it the capital of France and you get *once upon a time*.\" Is that",
        "true of the actual checkpoint? Every sample generated is reproduced below verbatim,",
        "untidied, including any that contradict the claim.",
        "",
        f"Run: `docs/walkthrough/gen_domain_limit_probe.py`, {date.today().isoformat()}.",
        "",
        "## Run configuration",
        "",
        "| setting | value |",
        "|---|---|",
        f"| checkpoint | `{ck}` (the tuned notebook-02 model — the only Track A checkpoint on disk) |",
        f"| tokenizer | `{ck}/tokenizer.json` — trained byte-level BPE, vocab {cfg.vocab_size} |",
        f"| parameters | {n_params:,} ({n_params / 1e6:.2f}M) |",
        f"| architecture | block_size {cfg.block_size}, n_embd {cfg.n_embd}, "
        f"n_head {cfg.n_head}, n_layer {cfg.n_layer} |",
        f"| seed | `{SEED}` — sample *i* uses `SEED + i`, so each sample is independently reproducible |",
        f"| temperature | {TEMPERATURE} (library + `chat.py` default) |",
        f"| top-k | {topk_note} |",
        f"| max new tokens | {MAX_NEW_TOKENS} (a cap; `<|endstory|>` usually fires first) |",
        f"| stop at eos | {STOP_AT_EOS} — stops on `{getattr(cfg, 'eos_token', None)}` |",
        f"| samples per prompt | {N_SAMPLES} |",
        "| sampler | `tiny_gpt.stream` — the same code path `chat.py` and notebook 02 use |",
        "",
        "## Summary",
        "",
        "Marker tests are crude lexical checks fixed before the run (see the script); the",
        "verbatim text below is the real evidence.",
        "",
        "| prompt | says \"Once upon a time\" | opens w/ fairy-tale framing | says \"Paris\" | "
        "re-uses \"France\"/\"capital\" | ran to token cap |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        n = len(r["samples"])
        claim = sum(s["claim_phrase"] for s in r["samples"])
        opens = sum(s["opens_story"] for s in r["samples"])
        fact = sum(bool(s["fact"]) for s in r["samples"])
        subj = sum(bool(s["subject"]) for s in r["samples"])
        cap = sum(s["hit_cap"] for s in r["samples"])
        L.append(f"| `{r['prompt']}` | {claim}/{n} | {opens}/{n} | {fact}/{n} | {subj}/{n} | {cap}/{n} |")
    L += ["", "## Verdict", "", VERDICT, "", "## Also observed", "", SIDE_OBSERVATION,
          "", "## Every sample, verbatim", ""]
    for r in results:
        L += [f"### `{r['kind']}` — prompt: `{r['prompt']}`", ""]
        for s in r["samples"]:
            stop = "hit the token cap" if s["hit_cap"] else "stopped at `<|endstory|>`"
            L += [
                f"**Sample {s['seed'] - SEED + 1}** (seed `{s['seed']}`, {s['chars']} chars, "
                f"~{s['approx_tokens']} tokens, {stop} — inferred by re-encoding):",
                "",
                "The prompt is shown in the fence too; everything after it is the model's.",
                "",
            ]
            full = r["prompt"] + s["continuation"]
            f = fence(full)
            L += [f + "text", full, f, ""]
    L += [
        "## Caveats",
        "",
        "- Stop reason is *inferred* by re-encoding the continuation and comparing to the",
        "  token cap; BPE round-trips are not guaranteed token-identical.",
        "- Marker tests are substring checks, not judgements. They can miss fairy-tale framing",
        "  phrased in words not on the list. They are a skimming aid over the verbatim text.",
        "- `n=5` per prompt at one seed family. This is enough to falsify a universal claim",
        "  (\"you get *once upon a time*\") but not to estimate rates precisely.",
        "",
    ]
    return "\n".join(L)


def main():
    if not (CKPT / "weights.safetensors").exists():
        sys.exit(f"No checkpoint at {CKPT.relative_to(REPO)}.\n"
                 f"Mint one first:  uv run python notebooks/train_v2_checkpoint.py")
    results, n_params, cfg = run()
    OUT.write_text(report(results, n_params, cfg))
    print(f"wrote {OUT.relative_to(REPO)}")
    for r in results:
        for s in r["samples"]:
            print(f"\n--- {r['kind']} seed={s['seed']} ---\n{r['prompt']}{s['continuation']}")


if __name__ == "__main__":
    main()
