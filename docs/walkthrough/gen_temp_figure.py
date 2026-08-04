"""gen_temp_figure.py — emit the two-panel temperature comparison for Part 0 §8.

Both panels are REAL softmax outputs from the trained Track A v2 checkpoint, re-scored at
two sampling temperatures. Like PROBS_SVG, these numbers used to be measured once and
typed in by hand, so a retrain falsified them silently. Rerun whenever the checkpoint is
retrained.

The two panels deliberately share ONE bar scale: the figure's whole point is that the
LEFT distribution is peaked and the RIGHT one is flat, and normalising each panel to its
own maximum would erase exactly that difference.

FIXES A BUG IN THE HAND-BUILT ORIGINAL. That version drew the top 5 chunks but computed
"everything else" as 100 − (top **6**), so the 6th chunk (" proud") was dropped from the
bars *and* from the pool: its panels silently summed to 99.1% and 97.0% instead of 100%.
This generator pools everything below the drawn bars, so each panel totals 100.0. The
regenerated figure therefore differs from the old one by slightly more than the retrain
alone would explain — "everything else" is 0.9 and 3.0 points larger.

Run:   uv run python docs/walkthrough/gen_temp_figure.py > /tmp/temp.svg
Then:  paste the SVG into content_concepts.py as TEMP_SVG.
"""
import sys
from pathlib import Path

import mlx.core as mx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "notebooks"))
import tiny_gpt  # noqa: E402

CKPT = ROOT / "notebooks" / "checkpoints" / "tiny_gpt_v2"

# --- what we measure ----------------------------------------------------------
PROMPT = "Tom was very"
PANELS = [(0.5, "plays it safe", "#5f6c33", 148, 156),      # (temp, caption, colour, label_x, bar_x)
          (1.1, "adventurous", "#8c6a2a", 493, 501)]
TOP_K = 5              # named bars per panel; remainder pooled into "everything else"

# --- layout (matches the hand-built original exactly) --------------------------
W, H = 720, 320
MAX_BAR = 150          # px for the largest bar ACROSS BOTH panels — the shared scale
ROW_Y0, ROW_STEP, BAR_H = 82, 28, 19
PCT_GAP = 7
REST_FILL = "#cfc5ae"
INK, SOFT = "#231f18", "#6e6557"
MONO = 'font-family="ui-monospace,Menlo,monospace"'


def measure(model, tok, cfg, temperature):
    ids = tok.encode(PROMPT).ids
    logits = model(mx.array([ids])[:, -cfg.block_size:])[:, -1, :] / temperature
    probs = mx.softmax(logits, axis=-1)[0]
    order = mx.argsort(probs)[::-1][:TOP_K].tolist()
    # round to the labelled precision first, so each panel's visible numbers total 100.0
    top = [(tok.decode([i]), round(float(probs[i]) * 100, 1)) for i in order]
    return top, round(100.0 - sum(p for _, p in top), 1)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    model, tok, cfg = tiny_gpt.load(str(CKPT))
    panels = [(t, cap, col, lx, bx, *measure(model, tok, cfg, t))
              for t, cap, col, lx, bx in PANELS]
    # scale against EVERY bar drawn, remainder included. Scaling to the named bars alone
    # works only while they dominate; once the distribution flattens, "everything else"
    # becomes the widest bar and runs off the right edge of the viewBox.
    scale = MAX_BAR / max([p for *_, top, rest in panels for _, p in top]
                          + [rest for *_, rest in panels])

    lo, hi = panels[0], panels[1]
    label = (f"The same real next-word scores for {PROMPT}, sampled at temperature "
             f"{lo[0]} and {hi[0]}. At {lo[0]} {lo[5][0][0].strip()} dominates; at {hi[0]} "
             f"nearly half the probability spreads to the long tail of other chunks.")

    L = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)}">',
         f'<text x="360" y="24" text-anchor="middle" font-size="13" font-weight="700" '
         f'fill="{INK}" {MONO}>“{esc(PROMPT)} ___”</text>',
         f'<text x="360" y="42" text-anchor="middle" font-size="11" fill="{SOFT}">same model, '
         f'same scores — only the sampling temperature changes</text>']

    for temp, caption, colour, label_x, bar_x, top, rest in panels:
        L.append(f'<text x="{label_x + 39}" y="68" text-anchor="middle" font-size="12" '
                 f'font-weight="700" fill="{colour}">temperature {temp} — {caption}</text>')
        rows = [(esc(t), p, colour, False) for t, p in top]
        rows.append(("everything else", rest, REST_FILL, True))
        for i, (name, pct, fill, italic) in enumerate(rows):
            y = ROW_Y0 + i * ROW_STEP
            w = round(pct * scale)
            style = ' font-style="italic"' if italic else ""
            font = "" if italic else f" {MONO}"
            colr = SOFT if italic else INK
            L.append(f'<text x="{label_x}" y="{y + 14}" text-anchor="end" font-size="11.5"'
                     f'{style}{font} fill="{colr}">{name}</text>')
            L.append(f'<rect x="{bar_x}" y="{y}" width="{w}" height="{BAR_H}" rx="4" fill="{fill}"/>')
            L.append(f'<text x="{bar_x + w + PCT_GAP}" y="{y + 14}" font-size="10.5" fill="{SOFT}" '
                     f'{MONO}>{pct:.1f}%</text>')

    hi_rest = hi[6]
    L += ['<text x="660" y="265" text-anchor="end" font-size="10" fill="#8c6a2a" '
          'font-style="italic">↑ the long tail gets a real chance</text>',
          f'<text x="30" y="294" font-size="10.5" fill="{SOFT}">Temperature reshapes how the menu is '
          f'sampled, not the menu itself: at {lo[0]}, “{lo[5][0][0].strip()}” wins ~{lo[5][0][1]:.0f}% '
          f'of draws; at {hi[0]}, {"nearly half" if hi_rest >= 40 else "much more"}</text>',
          f'<text x="30" y="310" font-size="10.5" fill="{SOFT}">the draws come from outside the top '
          f'five — that’s where the surprises (good and bad) come from.</text>',
          "</svg>"]
    print("\n".join(L))


if __name__ == "__main__":
    main()
