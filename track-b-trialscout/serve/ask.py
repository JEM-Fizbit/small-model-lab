#!/usr/bin/env python3
"""ask.py — interactive TrialScout REPL. Type an NCT id, get a readout. No MCP client needed.

This is the hands-on way to *touch* the model directly. It's the same model the MCP server
wraps — this just gives you a prompt to poke at it in a terminal. Loads the model once, then loops.

Run:  uv run python track-b-trialscout/serve/ask.py
Then: type an NCT id (e.g. NCT02942290), or 'random', or 'help'.
"""
import json
import random
import sys
from pathlib import Path

# Reuse the server's fetch + infer + formatting (single source of truth).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import trial_readout_server as t  # noqa: E402  (after sys.path.insert)

RAW = t.ROOT / "data" / "raw" / "trials.jsonl"  # local dataset (gitignored), used by 'random'

HELP = """commands:
  <NCT id>     read out that trial (fetched live from ClinicalTrials.gov)
  random / r   pick a random trial from the local dataset and read it out
  json / md    switch output format (default: markdown)
  help / ?     show this
  quit / q     exit"""


def _pool() -> list[str]:
    if not RAW.exists():
        return []
    return [json.loads(line)["nct_id"] for line in RAW.read_text().splitlines() if line.strip()]


def main() -> None:
    fmt = t.ResponseFormat.MARKDOWN
    pool = _pool()
    print("TrialScout — interactive readout. Loading model (~10s) …", flush=True)
    t._load_model()
    print(f"ready. {len(pool)} trials in local dataset for 'random'." if pool else "ready.")
    print(HELP)

    while True:
        try:
            s = input("\ntrial> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not s:
            continue
        low = s.lower()
        if low in ("q", "quit", "exit"):
            break
        if low in ("help", "?"):
            print(HELP)
            continue
        if low in ("json", "md", "markdown"):
            fmt = t.ResponseFormat.JSON if low == "json" else t.ResponseFormat.MARKDOWN
            print(f"output format -> {fmt.value}")
            continue
        if low in ("random", "r"):
            if not pool:
                print("no local dataset found; type an NCT id instead (or run the data fetch).")
                continue
            s = random.choice(pool)
            print(f"(random) {s}")

        nct = s.upper()
        if not nct.startswith("NCT"):
            print("type an NCT id like 'NCT02942290', or 'random'. ('help' for commands)")
            continue
        try:
            raw = t._fetch_trial(nct)
        except Exception as e:  # noqa: BLE001  REPL: surface any fetch failure, keep looping
            print(f"fetch error: {type(e).__name__}: {e}")
            continue
        if raw is None:
            print(f"{nct}: not found, or not a phased interventional trial (TrialScout's scope).")
            continue
        print()
        print(t._format_result(t._infer(raw), fmt))

    print("bye.")


if __name__ == "__main__":
    main()
