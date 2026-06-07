"""chat.py — a terminal REPL for the from-scratch GPT (Track A "v2").

Loads a saved checkpoint in ~1s and lets you 'chat' (really: prompt → story completion;
this is a TinyStories model, not an instruction-tuned assistant) without touching Jupyter
and without ever retraining.

    uv run python notebooks/chat.py
    uv run python notebooks/chat.py --temp 1.0 --tokens 250

Commands inside the REPL:
    /temp 0.6     set sampling temperature (low = safe/repetitive, high = wild)
    /tokens 200   set how many tokens to generate
    /quit         exit
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import tiny_gpt  # noqa: E402

DEFAULT_CKPT = str(Path(__file__).parent / "checkpoints" / "tiny_gpt_v2")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=DEFAULT_CKPT)
    ap.add_argument("--temp", type=float, default=0.8)
    ap.add_argument("--tokens", type=int, default=300, help="max tokens per reply (a cap; the story usually ends first)")
    ap.add_argument("--no-stop", action="store_true",
                    help="don't stop at the end-of-story token; keep generating to --tokens (rolls into new stories)")
    args = ap.parse_args()

    if not Path(args.ckpt, "weights.safetensors").exists():
        sys.exit(f"No checkpoint at {args.ckpt}.\n"
                 f"Mint one first:  uv run python notebooks/train_v2_checkpoint.py")

    print(f"loading {args.ckpt} …")
    model, tok, cfg = tiny_gpt.load(args.ckpt)
    temp, ntok = args.temp, args.tokens
    stop_eos = not args.no_stop
    has_eos = getattr(cfg, "eos_token", None) is not None
    note = "on" if (stop_eos and has_eos) else ("off" if not stop_eos else "n/a — checkpoint has no eos token")
    print(f"ready (temp={temp}, max tokens={ntok}, stop-at-story-end={note}).  "
          "/temp N  /tokens N  /stop  /quit\n"
          "Type a prompt — it's a TinyStories model, so try 'Once upon a time' style openers.\n")

    while True:
        try:
            prompt = input("you ▸ ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not prompt:
            continue
        if prompt in ("/quit", "/exit", "/q"):
            break
        if prompt.startswith("/temp"):
            try:
                temp = float(prompt.split()[1])
                print(f"  temperature = {temp}")
            except (IndexError, ValueError):
                print("  usage: /temp 0.8")
            continue
        if prompt.startswith("/tokens"):
            try:
                ntok = int(prompt.split()[1])
                print(f"  max tokens = {ntok}")
            except (IndexError, ValueError):
                print("  usage: /tokens 200")
            continue
        if prompt.startswith("/stop"):
            stop_eos = not stop_eos
            print(f"  stop-at-story-end = {'on' if stop_eos else 'off'}")
            continue

        print("gpt ▸ ", end="", flush=True)
        for delta in tiny_gpt.stream(model, tok, cfg, prompt, n_new=ntok, temperature=temp, stop_at_eos=stop_eos):
            print(delta, end="", flush=True)
        print("\n")


if __name__ == "__main__":
    main()
