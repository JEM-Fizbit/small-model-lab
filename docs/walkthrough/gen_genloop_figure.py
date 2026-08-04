"""gen_genloop_figure.py — refresh the measured numbers in the animated generation-loop figure.

GENLOOP_SVG is a 27k-character hand-built animation: six step panels, CSS keyframes, and a
sentence that assembles itself token by token. Almost all of that is STRUCTURE and never
changes. What does change on a retrain is the measurement: six panels x (four candidate
chunks + a pooled remainder), their bar widths, and the closing commentary.

So this is a template-updater rather than a from-scratch emitter — it rewrites exactly the
value-driven parts of the existing SVG and leaves the animation alone. That keeps the last
hand-tuned figure in the repo from being the one surface a retrain silently falsifies.

    uv run python docs/walkthrough/gen_genloop_figure.py > /tmp/genloop.svg

The trace (and its load-bearing seed) comes from gen_generation_trace.py, which refuses to
run if the seed no longer makes the figure demonstrate its own caption.
"""
import importlib.util
import re
import sys
from pathlib import Path

WALK = Path(__file__).resolve().parent
ROOT = WALK.parents[1]

_spec = importlib.util.spec_from_file_location("gen_trace", WALK / "gen_generation_trace.py")
gen_trace = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen_trace)

# --- layout constants read off the hand-built original -------------------------
BAR_X = 222                 # left edge of every bar
PX_PER_PCT = 3.897          # fixed across all six panels: 87.5% -> 341px, 83.4% -> 325px
MIN_BAR = 2                 # a ~0% chunk still gets a visible sliver
PCT_GAP = 8                 # percentage label sits this far past the bar's end
TINY = 0.1                  # below this the figure prints "<0.1%" rather than a rounded 0.0%


ORDINALS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
            9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}


def pct_text(p):
    return "&lt;0.1%" if p < TINY else f"{p:.1f}%"


def spoken(token):
    """Punctuation tokens need a name, not a glyph, in the screen-reader description."""
    return {",": "comma", ".": "full stop", "!": "exclamation mark",
            "?": "question mark", ";": "semicolon"}.get(token.strip(), token.strip())


def bar_width(p):
    return max(MIN_BAR, round(p * PX_PER_PCT))


def read_svg():
    src = (WALK / "content.py").read_text()
    marker = "GENLOOP_SVG = r'''"
    i = src.index(marker)
    j = src.index("'''", i + len(marker))
    return src[i + len(marker):j]


def update(svg, trace):
    lines = svg.split("\n")
    for step_i, step in enumerate(trace["steps"], start=1):
        # rows = the four candidates the panel names, then the pooled remainder
        rows = [(c["token"].strip(), c["p"] * 100) for c in step["top"]]
        rows.append((None, step["rest"] * 100))

        b = next(k for k, ln in enumerate(lines) if f'gl-bars gl-b{step_i}"' in ln)
        for r, (_, p) in enumerate(rows):
            lines[b + 1 + r] = re.sub(r'width="\d+"', f'width="{bar_width(p)}"', lines[b + 1 + r])

        t = b + len(rows) + 2                      # skip the closing </g>
        for r, (name, p) in enumerate(rows):
            label_line, pct_line = t + 2 * r, t + 2 * r + 1
            if name is not None:                   # the remainder row keeps its italic caption
                lines[label_line] = re.sub(r">([^<]*)</text>$", f">{name}</text>",
                                           lines[label_line])
            lines[pct_line] = re.sub(r'^<text x="\d+"', f'<text x="{BAR_X + bar_width(p) + PCT_GAP}"',
                                     lines[pct_line])
            lines[pct_line] = re.sub(r">([^<]*)</text>$", f">{pct_text(p)}</text>", lines[pct_line])
    return "\n".join(lines)


def update_prose(svg, trace):
    """Refresh the caption sentences that quote specific numbers."""
    last = trace["steps"][-1]
    picked_p = last["picked_p"] * 100
    fav = last["top"][0]
    odds = round(1 / max(last["picked_p"], 1e-9))
    svg = re.sub(r"A \d+\.\d% chunk wins about one roll in \w+",
                 f"A {picked_p:.1f}% chunk wins about one roll in {ORDINALS.get(odds, odds)}", svg)
    svg = re.sub(r"gen_generation_trace\.py \(seed \d+\)",
                 f"gen_generation_trace.py (seed {trace['seed']})", svg)
    # the aria-label spells out every panel's winner for screen readers
    steps = trace["steps"]
    named = ", ".join(f"{spoken(s['picked'])} {s['picked_p'] * 100:.1f}%" for s in steps[:5])
    aria = (f"Autoregressive generation, animated: the prompt {trace['prompt']} grows one "
            f"word-chunk at a time. At each of six steps the model&#8217;s real top-4 "
            f"next-chunk probabilities appear as growing bars, the sampled chunk is outlined "
            f"and then appended to the sentence with a brief highlight. Steps 1 to 5 pick the "
            f"favourite ({named}); at step 6 the weighted die lands on "
            f"{last['picked'].strip()} at {picked_p:.1f}% instead of the favourite "
            f"{fav['token'].strip()} at {fav['p'] * 100:.1f}%, finishing:"
            f"{trace['final']}.")
    return re.sub(r'(role="img" aria-label=")[^"]*(")', lambda m: m.group(1) + aria + m.group(2),
                  svg, count=1)


def main():
    model, tok, cfg = gen_trace.tiny_gpt.load(str(gen_trace.CKPT))
    trace = gen_trace.trace(model, tok, cfg, gen_trace.SEED)
    if not gen_trace.satisfies(trace):
        sys.exit(f"SEED={gen_trace.SEED} no longer samples a non-favourite at the last step — "
                 f"the figure would stop demonstrating its own caption.\n"
                 f"Re-pick with: uv run python docs/walkthrough/gen_generation_trace.py --hunt")
    svg = update_prose(update(read_svg(), trace), trace)
    print(svg.strip())


if __name__ == "__main__":
    main()
