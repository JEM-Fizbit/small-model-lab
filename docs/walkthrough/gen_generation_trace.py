"""gen_generation_trace.py — measure the data behind the animated generation-loop figure.

Replays six steps of autoregressive generation with the Track A "v2" checkpoint
(notebooks/checkpoints/tiny_gpt_v2) and records, for every step, the model's top-4
next-token probabilities plus the token actually sampled. The numbers printed here are
pasted into GENLOOP_SVG in content.py — rerun this script to regenerate them.

    uv run python docs/walkthrough/gen_generation_trace.py           # emit the trace
    uv run python docs/walkthrough/gen_generation_trace.py --hunt    # re-pick SEED

THE SEED IS LOAD-BEARING, so it gets a stated criterion instead of folklore. The figure
exists to show that sampling is a *weighted die* — that the model does not simply take its
favourite every time. That is only visible if the final step samples something OTHER than
the argmax (the original: " boy" at 14% beating " girl" at 83%). Most seeds just take the
favourite and the figure silently stops demonstrating its own caption.

So SEED is chosen to satisfy SELECTION_CRITERION below, and `--hunt` re-derives it. A
retrain invalidates the choice — MLX on the GPU is not bitwise reproducible, so even the
same seed and the same data give a slightly different model — and this script will TELL
you when the current seed no longer works rather than emitting a figure that lies.
"""
import argparse
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
SEED = 3           # satisfies SELECTION_CRITERION — re-derive with --hunt after any retrain
HUNT_RANGE = 40    # seeds scanned by --hunt

SELECTION_CRITERION = (
    "the final step must sample a token that is NOT the most likely one, so the figure "
    "actually shows the weighted die refusing the favourite"
)


def trace(model, tok, cfg, seed):
    mx.random.seed(seed)
    ids = list(tok.encode(PROMPT).ids)
    steps = []
    for _ in range(STEPS):
        logits = model(mx.array([ids])[:, -cfg.block_size:])[:, -1, :] / TEMPERATURE
        probs = mx.softmax(logits, axis=-1)[0]
        next_id = int(mx.random.categorical(logits).item())
        order = mx.argsort(probs)[::-1][:TOP_K].tolist()
        top = [{"token": tok.decode([i]), "p": round(float(probs[i]), 3)} for i in order]
        steps.append({
            "context": tok.decode(ids),
            "top": top,
            "rest": round(1 - sum(t["p"] for t in top), 3),
            "picked": tok.decode([next_id]),
            "picked_p": round(float(probs[next_id]), 3),
            "favourite": top[0]["token"],
            "took_favourite": next_id == int(mx.argmax(probs).item()),
        })
        ids.append(next_id)
    return {"prompt": PROMPT, "temperature": TEMPERATURE, "seed": seed,
            "final": tok.decode(ids), "steps": steps}


def satisfies(t):
    return not t["steps"][-1]["took_favourite"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hunt", action="store_true",
                    help=f"scan seeds 0..{HUNT_RANGE - 1} for ones meeting the criterion")
    args = ap.parse_args()

    model, tok, cfg = tiny_gpt.load(str(CKPT))

    if args.hunt:
        print(f"criterion: {SELECTION_CRITERION}\n")
        hits = 0
        for s in range(HUNT_RANGE):
            t = trace(model, tok, cfg, s)
            if satisfies(t):
                hits += 1
                last = t["steps"][-1]
                print(f"  seed {s:>3}: picked {last['picked']!r} at {last['picked_p']:.1%} "
                      f"over favourite {last['favourite']!r} at {last['top'][0]['p']:.1%}")
                print(f"           -> {t['final']!r}")
        print(f"\n{hits}/{HUNT_RANGE} seeds satisfy it. Set SEED to one of them.")
        return

    t = trace(model, tok, cfg, SEED)
    if not satisfies(t):
        sys.exit(
            f"SEED={SEED} no longer satisfies the selection criterion — step {STEPS} sampled "
            f"{t['steps'][-1]['picked']!r}, which IS the model's favourite.\n"
            f"The figure would no longer demonstrate its own caption. Re-pick with:\n"
            f"    uv run python {Path(__file__).name} --hunt")
    print(json.dumps(t, indent=2))


if __name__ == "__main__":
    main()
