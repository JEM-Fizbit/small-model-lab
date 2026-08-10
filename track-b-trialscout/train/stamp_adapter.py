"""Record which schema contract an adapter was trained against. Run right after training.

    uv run python track-b-trialscout/train/stamp_adapter.py track-b-trialscout/train/adapters/qwen_v2s

The serve layer refuses to load an adapter whose stamp disagrees with the live schema. See
schema/fingerprint.py for why bookkeeping beats validation here.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "schema"))
from fingerprint import stamp, fingerprint  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    path = stamp(Path(sys.argv[1]))
    print(f"stamped {path} with contract {fingerprint()}")
