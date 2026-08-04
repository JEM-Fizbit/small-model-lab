"""gen_probs_figure.py — emit the "what comes next?" probability bar chart for Part 0 §7.

Every percentage in this figure is a REAL softmax output from the trained Track A v2
checkpoint — which is exactly why it needs a generator. Before this script existed the
numbers were measured once and typed into the SVG by hand, so a retrain silently
falsified the figure and nothing failed loudly. Rerun this whenever the checkpoint is
retrained.

Run:   uv run python docs/walkthrough/gen_probs_figure.py > /tmp/probs.svg
Then:  paste the SVG into content_concepts.py as PROBS_SVG.
"""
import sys
from pathlib import Path

import mlx.core as mx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "notebooks"))
import tiny_gpt  # noqa: E402

CKPT = ROOT / "notebooks" / "checkpoints" / "tiny_gpt_v2"

# --- what we measure ----------------------------------------------------------
PROMPT = "One day, Lily went to the"
TEMPERATURE = 1.0   # the raw distribution — temperature is TEMP_SVG's subject, not this one
TOP_K = 5           # named bars; the remainder is pooled into "everything else"

# --- layout (matches the hand-built original exactly) --------------------------
W, H = 720, 286
LABEL_X, BAR_X = 218, 228     # right-aligned token label; bar left edge
MAX_BAR = 380                 # width of the TOP bar; every other bar scales against it
ROW_Y0, ROW_STEP, BAR_H = 64, 30, 21
PCT_GAP = 8                   # gap between bar end and its percentage label
BAR_FILL, REST_FILL = "#963d2c", "#cfc5ae"
INK, SOFT = "#231f18", "#6e6557"
MONO = 'font-family="ui-monospace,Menlo,monospace"'


def measure():
    model, tok, cfg = tiny_gpt.load(str(CKPT))
    ids = tok.encode(PROMPT).ids
    logits = model(mx.array([ids])[:, -cfg.block_size:])[:, -1, :] / TEMPERATURE
    probs = mx.softmax(logits, axis=-1)[0]
    order = mx.argsort(probs)[::-1][:TOP_K].tolist()
    # Round each bar to the 1 d.p. it will be LABELLED with, then take the remainder from
    # those rounded values — so the numbers a reader can see really do sum to 100.0, which
    # is what the figure's footnote claims. Deriving it from the unrounded probabilities
    # instead leaves the visible column adding up to 99.9.
    top = [(tok.decode([i]), round(float(probs[i]) * 100, 1)) for i in order]
    return top, round(100.0 - sum(p for _, p in top), 1), cfg.vocab_size


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    top, rest, vocab = measure()
    scale = MAX_BAR / top[0][1]
    rows = [(esc(t), p, BAR_FILL, False) for t, p in top]
    rows.append((f"everything else (~{round(vocab, -3):,} chunks)", rest, REST_FILL, True))

    label = (f"The model's real next-word scores for the prompt {PROMPT.strip()}: "
             f"{top[0][0].strip()} {top[0][1]:.0f} percent, {top[1][0].strip()} {top[1][1]:.0f} percent, "
             f"then small scores, with about {rest:.0f} percent spread over all other chunks.")
    L = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)}">',
         f'<text x="30" y="26" font-size="14" font-weight="700" fill="{INK}" {MONO}>'
         f'“{esc(PROMPT)} ___”</text>',
         f'<text x="30" y="46" font-size="11" fill="{SOFT}">the model’s scores for what comes '
         f'next — its real output, one number per vocabulary chunk</text>']

    for i, (name, pct, fill, italic) in enumerate(rows):
        y = ROW_Y0 + i * ROW_STEP
        w = round(pct * scale)
        style = ' font-style="italic"' if italic else ""
        font = "" if italic else f" {MONO}"
        colour = SOFT if italic else INK
        L.append(f'<text x="{LABEL_X}" y="{y + 15}" text-anchor="end" font-size="12"{style}{font} '
                 f'fill="{colour}">{name}</text>')
        L.append(f'<rect x="{BAR_X}" y="{y}" width="{w}" height="{BAR_H}" rx="4" fill="{fill}"/>')
        L.append(f'<text x="{BAR_X + w + PCT_GAP}" y="{y + 15}" font-size="11" fill="{SOFT}" {MONO}>'
                 f'{pct:.1f}%</text>')

    L += [f'<text x="30" y="266" font-size="10.5" fill="{SOFT}">The scores sum to 100% across all '
          f'{vocab:,} chunks. Training (§7) nudges the weights so the chunk that actually came '
          f'next</text>',
          f'<text x="30" y="282" font-size="10.5" fill="{SOFT}">gets a bigger share; generating '
          f'(§8) means picking from this menu, appending, and scoring again.</text>',
          "</svg>"]
    print("\n".join(L))


if __name__ == "__main__":
    main()
