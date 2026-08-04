"""train_v2_checkpoint.py — headless one-time producer for the Track A "v2" checkpoint.

This mirrors the training cell in `02_tiny_gpt_tuned.ipynb` (the annotated, canonical
version lives there). Its only job is to train once and write a checkpoint that
`tiny_gpt.load()` / notebook 03 / chat.py can reload in ~1s — so you never sit through
a training run again just to use the model.

    uv run python notebooks/train_v2_checkpoint.py            # full quality (3000 steps)
    uv run python notebooks/train_v2_checkpoint.py --steps 800   # quick-and-rough first mint

Writes to notebooks/checkpoints/tiny_gpt_v2/ (gitignored).
"""
import sys
import time
import argparse
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_flatten
from tokenizers import Tokenizer, models, trainers, pre_tokenizers, decoders

sys.path.insert(0, str(Path(__file__).parent))
import tiny_gpt  # noqa: E402  (the model class — single source of truth for the architecture)

# ---- config (matches notebook 02, plus a real end-of-story token) -----------
EOS = "<|endstory|>"  # dedicated end-of-text token (cf. GPT-2's <|endoftext|>) — see below
cfg = SimpleNamespace(
    block_size=256,   # context length in TOKENS
    n_embd=384,       # width
    n_head=6,
    n_layer=6,        # depth
    vocab_size=8192,  # set precisely after BPE training below
    eos_token=EOS,    # the model learns to emit this when a story is complete
)
N_STORIES = 25000
batch_size = 32
warmup = 150
peak_lr = 6e-4
end_lr = 6e-5
weight_decay = 0.1
grad_clip = 1.0
eval_every = 250

SEED = 1337  # everything random downstream (weight init, batch order) derives from this.
             # Without it a rerun produces a wholly different model, which makes the
             # committed notebook outputs, loss curves and figures unreproducible.
             #
             # What the seed does and does NOT buy you (measured, 2026-08-04): it pins
             # weight init and batch order exactly — two fresh processes agree to 10
             # decimal places on the first steps. It does NOT give a bit-identical
             # checkpoint on the GPU: Metal kernels accumulate in nondeterministic order,
             # so runs drift apart in the last decimals and the final weights differ.
             # (Forcing mx.set_default_device(mx.cpu) IS bit-reproducible, and far too
             # slow to train on.) So: same seed ⇒ same experiment, not the same bytes.

parser = argparse.ArgumentParser()
parser.add_argument("--steps", type=int, default=3000, help="training steps (3000 ≈ notebook quality)")
parser.add_argument("--seed", type=int, default=SEED,
                    help="RNG seed — pins init + batch order (not bit-identical on GPU; see note above)")
parser.add_argument("--out", default=str(Path(__file__).parent / "checkpoints" / "tiny_gpt_v2"))
args = parser.parse_args()
max_steps = args.steps

# Seed BEFORE anything draws a random number: MLX drives weight init (tiny_gpt._normal),
# NumPy drives batch sampling (get_batch). Both must be pinned or the run won't reproduce.
mx.random.seed(args.seed)
np.random.seed(args.seed)

print(f"MLX device: {mx.default_device()}  | steps={max_steps} | seed={args.seed}")


# ---- corpus hygiene ---------------------------------------------------------
# ~7.5% of TinyStories stories ship with double-encoded UTF-8 ("daddyâ€™s tie" for
# "daddy's tie"): the text was UTF-8 bytes decoded as CP1252 somewhere upstream. Left
# alone, the BPE spends ~1% of its vocabulary learning the garbled byte-pairs as if they
# were words (dedicated merges for the mangled forms of "Mommy, "Hello, ' couldn''), and
# the model emits them at generation time. See docs/DECISIONS.md ADR-0013.
TELLTALE = ("Â", "Ã", "â", "Å")  # cheap pre-filter: no mojibake can exist without one


def _sloppy_cp1252(s):
    """Encode as CP1252, falling back to the raw Latin-1 byte for CP1252's five undefined
    slots (0x81/0x8D/0x8F/0x90/0x9D). Real mojibake contains them; strict CP1252 refuses."""
    out = bytearray()
    for ch in s:
        try:
            out += ch.encode("cp1252")
        except UnicodeEncodeError:
            if ord(ch) >= 256:
                raise
            out.append(ord(ch))
    return bytes(out)


def _restore_dropped_byte(s):
    """Put back the third byte of a mangled right double quote.

    U+201D (") is UTF-8 E2 80 9D. CP1252 has no mapping for 0x9D, so whoever mis-decoded
    the corpus DROPPED it, leaving a bare "â€" that no round-trip can reverse (E2 80
    followed by a space is not valid UTF-8). This is the majority of the damage — 5.5% of
    stories, against 2% that are losslessly reversible. Where "â€" is not followed by a
    valid continuation byte, restore the lost 0x9D so the round-trip below can work.
    """
    out, i = [], 0
    while i < len(s):
        if s.startswith("â€", i):
            nxt = s[i + 2] if i + 2 < len(s) else ""
            try:
                b = _sloppy_cp1252(nxt)[0] if nxt else None
            except (UnicodeEncodeError, IndexError):
                b = None
            if b is None or not (0x80 <= b <= 0xBF):
                out.append("â€\x9d")
                i += 2
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


def fix_mojibake(s):
    """Repair double-encoded UTF-8; leave already-clean text byte-identical.

    Conservative by design: anything that doesn't round-trip cleanly is returned
    untouched, because corrupting good text is worse than leaving a bug in. Verified on
    3,000 upstream stories — 226 repaired, 2,774 unchanged, 0 clean strings modified.
    """
    if not any(c in s for c in TELLTALE):
        return s
    s = _restore_dropped_byte(s)
    for _ in range(3):  # a few stories are double-encoded
        try:
            fixed = _sloppy_cp1252(s).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break       # not repairable -> leave exactly as-is
        if fixed == s:
            break
        s = fixed
    return s


# ---- data -------------------------------------------------------------------
try:
    from datasets import load_dataset
    ds = load_dataset("roneneldan/TinyStories", split="train", streaming=True)
    stories, n_fixed = [], 0
    for ex in ds:
        raw = ex["text"].strip()
        clean = fix_mojibake(raw)
        n_fixed += clean != raw
        stories.append(clean)
        if len(stories) >= N_STORIES:
            break
    text = "\n\n".join(stories)
    print(f"Loaded {len(stories):,} stories ({len(text):,} chars); "
          f"repaired encoding in {n_fixed:,} ({100 * n_fixed / max(len(stories), 1):.1f}%)")
except Exception as e:
    print("fallback corpus:", e)
    stories = [("The little robot read a happy story about a fox and a bird by the river. ") * 200] * 100
text = "\n\n".join(stories)

# ---- tokenizer (byte-level BPE) + an end-of-story token ---------------------
# We reserve "<|endstory|>" as a special token and place it BETWEEN stories in the training
# stream. "\n\n" can't serve as the story boundary because it's also the paragraph break inside
# nearly every story — so the model could never tell "end of paragraph" from "end of story".
# With a dedicated token, the model learns to emit it only when a story is truly done, and
# generation can stop there (natural, self-contained, variable-length stories).
tok = Tokenizer(models.BPE(unk_token="[UNK]"))
tok.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=True)
tok.decoder = decoders.ByteLevel()
trainer = trainers.BpeTrainer(vocab_size=8192, special_tokens=["[UNK]", EOS], show_progress=False)
t0 = time.time()
tok.train_from_iterator([text], trainer)
tok.add_special_tokens([EOS])           # match "<|endstory|>" atomically when encoding
eos_id = tok.token_to_id(EOS)
cfg.vocab_size = tok.get_vocab_size()
print(f"Trained BPE in {time.time()-t0:.1f}s — vocab_size={cfg.vocab_size}  eos_id={eos_id}")

# Build the token stream story-by-story, dropping the eos token after each.
ids = []
for s in stories:
    ids.extend(tok.encode(s).ids)
    ids.append(eos_id)
data = np.array(ids, dtype=np.int32)
n_train = int(0.9 * len(data))
train_data, val_data = data[:n_train], data[n_train:]
print(f"tokens: {len(data):,}  ({len(stories):,} stories)  train {len(train_data):,}  val {len(val_data):,}")


def get_batch(split):
    d = train_data if split == "train" else val_data
    ix = np.random.randint(0, len(d) - cfg.block_size - 1, size=batch_size)
    x = np.stack([d[i:i + cfg.block_size] for i in ix])
    y = np.stack([d[i + 1:i + 1 + cfg.block_size] for i in ix])
    return mx.array(x), mx.array(y)


# ---- model + train ----------------------------------------------------------
model = tiny_gpt.GPT(cfg)
mx.eval(model.parameters())
n_params = sum(p.size for _, p in tree_flatten(model.parameters()))
print(f"Model: {n_params/1e6:.1f}M params")


def loss_fn(model, x, y):
    logits = model(x)
    B, T, V = logits.shape
    return nn.losses.cross_entropy(logits.reshape(B * T, V), y.reshape(B * T)).mean()


def eval_val_loss(n=20):
    return sum(loss_fn(model, *get_batch("val")).item() for _ in range(n)) / n


warm = optim.linear_schedule(0.0, peak_lr, warmup)
cos = optim.cosine_decay(peak_lr, max_steps - warmup, end_lr)
sched = optim.join_schedules([warm, cos], [warmup])
optimizer = optim.AdamW(learning_rate=sched, weight_decay=weight_decay)
loss_and_grad = nn.value_and_grad(model, loss_fn)

t0 = time.time()
for step in range(1, max_steps + 1):
    x, y = get_batch("train")
    loss, grads = loss_and_grad(model, x, y)
    grads, _ = optim.clip_grad_norm(grads, grad_clip)
    optimizer.update(model, grads)
    mx.eval(model.parameters(), optimizer.state)
    if step % eval_every == 0 or step == 1:
        vl = eval_val_loss()
        print(f"step {step:4d}/{max_steps}  train {loss.item():.3f}  val {vl:.3f}  "
              f"lr {optimizer.learning_rate.item():.2e}  ({time.time()-t0:.0f}s)", flush=True)
print(f"Done training in {(time.time()-t0)/60:.1f} min.")

# ---- save -------------------------------------------------------------------
out = tiny_gpt.save_checkpoint(model, tok, cfg, args.out)
print(f"\n✅ saved checkpoint → {out}")
print("   load it with:  model, tok, cfg = tiny_gpt.load('checkpoints/tiny_gpt_v2')")
print("\n--- sample @ temp 0.8 ---")
print(tiny_gpt.generate(model, tok, cfg, "Once upon a time", n_new=120, temperature=0.8))
