#!/usr/bin/env python3
"""Lint the hardcoded fee card against the canonical model-reference protocol.

WHY THIS EXISTS. On 2026-08-14 the fee card in ``make_gold.py`` carried a comment
saying Sonnet 5's $2/$10 would revert to $3/$15 on 2026-09-01. That increase had been
cancelled. Nothing detected it, because the fee card was a hand-maintained copy of a
fact that already had a canonical home -- ``ANTHROPIC_MODEL_REFERENCE.md``. Two copies
of a moving number, no comparison between them, is a drift generator.

The protocol carries a *Roster verified* date and a 45-day staleness guard, but that
guard only protects a reader of the protocol. It cannot see a project that duplicated
the numbers into code months ago. This script closes that gap: it is the comparison.

Runs offline against the synced copy in ``docs/protocols/`` (refresh it with ``knowhub``).
It deliberately does NOT call the Models API -- per the protocol, freshness is refreshed
on a schedule and read statically, never fetched on the advice path.

    uv run python scripts/check_fee_card.py

Exit 0 clean, 1 on any drift or staleness.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL = ROOT / "docs" / "protocols" / "ANTHROPIC_MODEL_REFERENCE.md"
FEE_CARD = ROOT / "track-b-trialscout" / "train" / "make_gold.py"

STALENESS_DAYS = 45  # must match the protocol's own guard


def parse_protocol(text: str) -> tuple[dict[str, tuple[float, float]], dt.date | None]:
    """Pull {model_id: (in, out)} and the Roster-verified date out of the protocol."""
    prices: dict[str, tuple[float, float]] = {}
    # Inventory rows: | **Name** | `model-id` | ctx | max-out | $in | $out |
    row = re.compile(
        r"^\|[^|]*\|\s*`([a-z0-9-]+)`\s*\|[^|]*\|[^|]*\|\s*\**\$?([\d.]+)\**\s*\|\s*\**\$?([\d.]+)\**\s*\|"
    )
    for line in text.splitlines():
        m = row.match(line.strip())
        if m:
            prices[m.group(1)] = (float(m.group(2)), float(m.group(3)))

    verified = None
    m = re.search(r"\*\*Roster verified:\*\*\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        verified = dt.date.fromisoformat(m.group(1))
    return prices, verified


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
    if not PROTOCOL.exists():
        print(f"FAIL  synced protocol missing: {PROTOCOL.relative_to(ROOT)}")
        print("      run `knowhub` to sync it from ai-knowledge")
        return 1

    proto, verified = parse_protocol(PROTOCOL.read_text())
    card = parse_fee_card(FEE_CARD.read_text())
    problems: list[str] = []

    if not proto:
        problems.append("parsed 0 prices from the protocol -- its table shape changed")
    if not card:
        problems.append("parsed 0 prices from PRICING -- the dict shape changed")

    # Staleness: the protocol's own guard, applied on this project's behalf.
    if verified is None:
        problems.append("protocol has no `Roster verified` date")
    else:
        age = (dt.date.today() - verified).days
        if age > STALENESS_DAYS:
            problems.append(
                f"protocol roster is {age}d old (>{STALENESS_DAYS}d) -- "
                f"re-verify against platform.claude.com/docs/en/about-claude/pricing"
            )
        else:
            print(f"ok    roster verified {verified} ({age}d ago)")

    # Every model we actually price must match the protocol.
    for model, (cin, cout) in sorted(card.items()):
        if model not in proto:
            problems.append(f"{model}: in fee card but not in the protocol inventory")
            continue
        pin, pout = proto[model]
        if (cin, cout) != (pin, pout):
            problems.append(
                f"{model}: fee card ${cin}/${cout} != protocol ${pin}/${pout}"
            )
        else:
            print(f"ok    {model:20} ${cin}/${cout}")

    if problems:
        print(f"\nFAIL  {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        print("\nCanonical source is ai-knowledge/protocols/ANTHROPIC_MODEL_REFERENCE.md.")
        print("Fix it THERE, run `knowhub`, then update the fee card to match.")
        return 1

    print(f"\nPASS  fee card matches the protocol ({len(card)} models)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
