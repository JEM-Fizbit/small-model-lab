"""gen_generation_trace.py — measure the data behind the animated generation-loop figure.

Replays six steps of autoregressive generation with the Track A "v2" checkpoint
(notebooks/checkpoints/tiny_gpt_v2) and records, for every step, the model's
top-4 next-token probabilities plus the token actually sampled. The numbers
printed here are pasted into GEN_LOOP_SVG in content.py — rerun this script to
regenerate them (same seed → same trace).

    uv run python docs/walkthrough/gen_generation_trace.py
"""
import json
import sys
from pathlib import Path

import mlx.core as mx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "notebooks"))
import tiny_gpt  # noqa: E402

CKPT = Path(__file__).resolve().parents[2] / "notebooks" / "checkpoints" / "tiny_gpt_v2"
PROMPT = "Once upon a time"
STEPS = 6          # generation steps to record
TOP_K = 4          # candidates shown per step in the figure
TEMPERATURE = 0.8  # chat.py's default
SEED = 1           # fixed so the figure is reproducible (chosen because step 6's
                   # sample lands on " boy" at 14% over " girl" at 83% — the
                   # weighted die visibly NOT picking the favourite)


def main():
    model, tok, cfg = tiny_gpt.load(str(CKPT))
    mx.random.seed(SEED)
    ids = list(tok.encode(PROMPT).ids)
    trace = []
    for _ in range(STEPS):
        logits = model(mx.array([ids])[:, -cfg.block_size:])[:, -1, :] / TEMPERATURE
        probs = mx.softmax(logits, axis=-1)[0]
        next_id = int(mx.random.categorical(logits).item())
        order = mx.argsort(probs)[::-1][:TOP_K].tolist()
        top = [{"token": tok.decode([i]), "p": round(float(probs[i]), 3)} for i in order]
        trace.append({
            "context": tok.decode(ids),
            "top": top,
            "rest": round(1 - sum(t["p"] for t in top), 3),
            "picked": tok.decode([next_id]),
            "picked_p": round(float(probs[next_id]), 3),
        })
        ids.append(next_id)
    print(json.dumps({"prompt": PROMPT, "temperature": TEMPERATURE, "seed": SEED,
                      "final": tok.decode(ids), "steps": trace}, indent=2))


if __name__ == "__main__":
    main()
