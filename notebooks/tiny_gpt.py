"""tiny_gpt.py — inference library for the from-scratch GPT (Track A, "v2").

This is the *consumer* side of notebook 02. The architecture below is a structural
twin of the inline GPT class in `02_tiny_gpt_tuned.ipynb`: same attribute names and
shapes, so a checkpoint trained by either one loads cleanly here (MLX loads weights
by parameter name). If you ever change the architecture in the notebook, mirror the
change here and retrain — otherwise `load()` will raise on a key/shape mismatch.

A checkpoint is a directory with three files (see `save_checkpoint`):
    weights.safetensors  — the trained parameters
    tokenizer.json       — the trained byte-level BPE tokenizer
    config.json          — the shape (block_size/n_embd/n_head/n_layer/vocab_size)

Typical use:
    import tiny_gpt
    model, tok, cfg = tiny_gpt.load("checkpoints/tiny_gpt_v2")
    print(tiny_gpt.generate(model, tok, cfg, "Once upon a time", temperature=0.8))
"""
import math
import json
from pathlib import Path
from types import SimpleNamespace

import mlx.core as mx
import mlx.nn as nn
from tokenizers import Tokenizer

STD = 0.02


def _normal(shape, std=STD):
    return mx.random.normal(shape) * std


class CausalSelfAttention(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        C = cfg.n_embd
        self.c_attn = nn.Linear(C, 3 * C)
        self.c_proj = nn.Linear(C, C)
        self.nh = cfg.n_head
        self.c_attn.weight = _normal(self.c_attn.weight.shape)
        self.c_attn.bias = mx.zeros((3 * C,))
        # residual projection: extra 1/sqrt(2*n_layer) damping
        self.c_proj.weight = _normal(self.c_proj.weight.shape, STD / math.sqrt(2 * cfg.n_layer))
        self.c_proj.bias = mx.zeros((C,))

    def __call__(self, x, mask):
        B, T, C = x.shape
        hd = C // self.nh
        q, k, v = mx.split(self.c_attn(x), 3, axis=-1)
        q = mx.transpose(q.reshape(B, T, self.nh, hd), (0, 2, 1, 3))
        k = mx.transpose(k.reshape(B, T, self.nh, hd), (0, 2, 1, 3))
        v = mx.transpose(v.reshape(B, T, self.nh, hd), (0, 2, 1, 3))
        att = mx.softmax((q @ mx.transpose(k, (0, 1, 3, 2))) * (1 / math.sqrt(hd)) + mask, axis=-1)
        return self.c_proj(mx.transpose(att @ v, (0, 2, 1, 3)).reshape(B, T, C))


class Block(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        C = cfg.n_embd
        self.ln1 = nn.LayerNorm(C)
        self.ln2 = nn.LayerNorm(C)
        self.attn = CausalSelfAttention(cfg)
        l1 = nn.Linear(C, 4 * C)
        l2 = nn.Linear(4 * C, C)
        l1.weight = _normal(l1.weight.shape)
        l1.bias = mx.zeros((4 * C,))
        l2.weight = _normal(l2.weight.shape, STD / math.sqrt(2 * cfg.n_layer))  # residual proj
        l2.bias = mx.zeros((C,))
        self.mlp = nn.Sequential(l1, nn.GELU(), l2)

    def __call__(self, x, mask):
        x = x + self.attn(self.ln1(x), mask)
        x = x + self.mlp(self.ln2(x))
        return x


class GPT(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        C = cfg.n_embd
        self.tok = nn.Embedding(cfg.vocab_size, C)
        self.pos = nn.Embedding(cfg.block_size, C)
        self.tok.weight = _normal(self.tok.weight.shape)
        self.pos.weight = _normal(self.pos.weight.shape)
        self.blocks = [Block(cfg) for _ in range(cfg.n_layer)]
        self.lnf = nn.LayerNorm(C)
        self.head = nn.Linear(C, cfg.vocab_size)
        self.head.weight = _normal(self.head.weight.shape)
        self.head.bias = mx.zeros((cfg.vocab_size,))

    def __call__(self, idx):
        B, T = idx.shape
        x = self.tok(idx) + self.pos(mx.arange(T))
        mask = (1 - mx.tril(mx.ones((T, T)))) * -1e9
        for b in self.blocks:
            x = b(x, mask)
        return self.head(self.lnf(x))


# --- checkpoint I/O -----------------------------------------------------------

CONFIG_FIELDS = ("block_size", "n_embd", "n_head", "n_layer", "vocab_size")


def save_checkpoint(model, tok, cfg, ckpt_dir):
    """Persist weights + tokenizer + config so the model can be reloaded without retraining."""
    ckpt = Path(ckpt_dir)
    ckpt.mkdir(parents=True, exist_ok=True)
    model.save_weights(str(ckpt / "weights.safetensors"))
    tok.save(str(ckpt / "tokenizer.json"))
    cfg_d = cfg if isinstance(cfg, dict) else vars(cfg)
    out_cfg = {k: cfg_d[k] for k in CONFIG_FIELDS}
    if cfg_d.get("eos_token"):  # the end-of-story token, if this model was trained with one
        out_cfg["eos_token"] = cfg_d["eos_token"]
    json.dump(out_cfg, open(ckpt / "config.json", "w"), indent=2)
    return ckpt.resolve()


def load(ckpt_dir):
    """Load a saved checkpoint. Returns (model, tokenizer, cfg). Takes ~1s, no training."""
    ckpt = Path(ckpt_dir)
    cfg = SimpleNamespace(**json.load(open(ckpt / "config.json")))
    model = GPT(cfg)
    model.load_weights(str(ckpt / "weights.safetensors"))
    mx.eval(model.parameters())
    model.eval()  # inference mode (no dropout etc.)
    tok = Tokenizer.from_file(str(ckpt / "tokenizer.json"))
    return model, tok, cfg


# --- generation ---------------------------------------------------------------

# A model trained with a dedicated end-of-story token (cfg.eos_token, e.g. "<|endstory|>")
# emits it when a story is complete — exactly how real LMs use <|endoftext|>. Generation stops
# there, giving naturally varying, self-contained stories. Checkpoints without an eos_token
# (e.g. the plain notebook-02 save) just run to n_new — stop_at_eos is then a no-op.


def _eos_id(tok, cfg):
    name = getattr(cfg, "eos_token", None)
    return tok.token_to_id(name) if name else None


def stream(model, tok, cfg, prompt, n_new=200, temperature=0.8, stop_at_eos=True):
    """Yield text deltas as tokens are produced — for a live 'typing' feel.

    Stops when the model emits its end-of-story token (if it has one and stop_at_eos=True),
    or after at most `n_new` tokens. Set stop_at_eos=False to keep going past story ends.
    """
    eos = _eos_id(tok, cfg) if stop_at_eos else None
    out = list(tok.encode(prompt).ids)
    idx = mx.array([out])
    prompt_text = tok.decode(out)
    emitted = 0  # chars of generated (post-prompt) text already yielded
    for _ in range(n_new):
        logits = model(idx[:, -cfg.block_size:])[:, -1, :] / temperature
        next_id = int(mx.random.categorical(logits).item())
        if next_id == eos:          # story finished — stop before emitting the marker
            return
        idx = mx.concatenate([idx, mx.array([[next_id]])], axis=1)
        out.append(next_id)
        gen = tok.decode(out)[len(prompt_text):]
        if len(gen) > emitted:
            yield gen[emitted:]
            emitted = len(gen)


def generate(model, tok, cfg, prompt, n_new=200, temperature=0.8, stop_at_eos=True):
    """Return a full completion as a string (prompt + continuation).

    Stops at the model's end-of-story token (if any) or after at most `n_new` tokens.
    Set stop_at_eos=False to always run the full n_new tokens.
    """
    return prompt + "".join(stream(model, tok, cfg, prompt, n_new, temperature, stop_at_eos))
