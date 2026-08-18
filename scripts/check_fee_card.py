#!/usr/bin/env python3
"""Lint the hardcoded fee card against the canonical pricing artifact.

WHY THIS EXISTS. On 2026-08-14 the fee card in ``make_gold.py`` carried a comment
saying Sonnet 5's $2/$10 would revert to $3/$15 on 2026-09-01. That increase had been
cancelled. Nothing detected it, because the fee card was a hand-maintained copy of a
fact that already had a canonical home -- ``ANTHROPIC_MODEL_REFERENCE.md``. Two copies
of a moving number, no comparison between them, is a drift generator.

The protocol carries a *Roster verified* date and a 45-day staleness guard, but that
guard only protects a reader of the protocol. It cannot see a project that duplicated
the numbers into code months ago. This script closes that gap: it is the comparison.

UPDATED 2026-08-18: this used to regex-parse the markdown table in
ANTHROPIC_MODEL_REFERENCE.md. Rates are now canonical as DATA in ai-knowledge at
``protocols/data/anthropic-pricing.json`` (synced here to
``docs/protocols/data/anthropic-pricing.json``), so the comparison reads structured
fields instead of matching prose — the markdown table shape was itself a documented
failure mode of this script. The markdown remains the human view and ai-knowledge's
own ``check-anthropic-pricing.py`` keeps the two in step at source.

Runs offline against the synced copy in ``docs/protocols/`` (refresh it with ``knowhub``).
It deliberately does NOT call the Models API -- per the protocol, freshness is refreshed
on a schedule and read statically, never fetched on the advice path.

    uv run python scripts/check_fee_card.py

Exit 0 clean, 1 on any drift or staleness.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "docs" / "protocols" / "data" / "anthropic-pricing.json"
FEE_CARD = ROOT / "track-b-trialscout" / "train" / "make_gold.py"

def parse_artifact(raw: str) -> tuple[dict[str, tuple[float, float]], dt.date | None, int]:
    """Pull {model_id: (in, out)}, verified_on and the staleness window out of the JSON."""
    data = json.loads(raw)
    prices = {
        model: (float(spec["input"]), float(spec["output"]))
        for model, spec in data["models"].items()
    }
    prov = data["provenance"]
    return prices, dt.date.fromisoformat(prov["verified_on"]), int(prov["staleness_days"])


def parse_fee_card(text: str) -> dict[str, tuple[float, float]]:
    """Pull {model_id: (in, out)} out of the PRICING dict literal."""
    block = re.search(r"PRICING\s*=\s*\{(.*?)\n\}", text, re.S)
    if not block:
        return {}
    entry = re.compile(
        r'"([a-z0-9-]+)":\s*\{\s*"in":\s*([\d.]+),\s*"out":\s*([\d.]+)'
    )
    return {
        m.group(1): (float(m.group(2)), float(m.group(3)))
        for m in entry.finditer(block.group(1))
    }


def main() -> int:
    if not ARTIFACT.exists():
        print(f"FAIL  synced pricing artifact missing: {ARTIFACT.relative_to(ROOT)}")
        print("      run `knowhub` to sync it from ai-knowledge")
        return 1

    proto, verified, staleness = parse_artifact(ARTIFACT.read_text())
    card = parse_fee_card(FEE_CARD.read_text())
    problems: list[str] = []

    if not proto:
        problems.append("parsed 0 prices from the artifact -- its schema changed")
    if not card:
        problems.append("parsed 0 prices from PRICING -- the dict shape changed")

    # Staleness: the protocol's own guard, applied on this project's behalf.
    if verified is None:
        problems.append("artifact has no `verified_on` date")
    else:
        age = (dt.date.today() - verified).days
        if age > staleness:
            problems.append(
                f"canonical pricing is {age}d old (>{staleness}d) -- "
                f"re-verify against platform.claude.com/docs/en/about-claude/pricing"
            )
        else:
            print(f"ok    roster verified {verified} ({age}d ago)")

    # Every model we actually price must match the protocol.
    for model, (cin, cout) in sorted(card.items()):
        if model not in proto:
            problems.append(f"{model}: in fee card but not in the canonical artifact")
            continue
        pin, pout = proto[model]
        if (cin, cout) != (pin, pout):
            problems.append(
                f"{model}: fee card ${cin}/${cout} != canonical ${pin}/${pout}"
            )
        else:
            print(f"ok    {model:20} ${cin}/${cout}")

    if problems:
        print(f"\nFAIL  {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        print("\nCanonical source is ai-knowledge/protocols/data/anthropic-pricing.json.")
        print("Fix it THERE, run `knowhub`, then update the fee card to match.")
        return 1

    print(f"\nPASS  fee card matches the canonical artifact ({len(card)} models)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
