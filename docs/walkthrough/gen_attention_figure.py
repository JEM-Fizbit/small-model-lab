"""gen_attention_figure.py — emit the "where does `it` look?" attention figure for Part 0 §5.

Every arc in this figure is a REAL attention weight from one head of the trained Track A
v2 checkpoint. tiny_gpt's forward pass never returns attention, so this script replays it
and captures the softmax directly — which is why the numbers previously had to be measured
by hand and typed in, and why a retrain falsified them silently.

WHICH head: layer 2 of 6, head 4 of 6 as the figure states it for readers — LAYER=1,
HEAD=3 zero-indexed below. That choice IS the figure's claim: this particular head has
learned to track who the sentence is about, so `it` looks back at `dragon`. Nothing
guarantees that survives a retrain — attention heads are not stable across runs, and a
different head may become the referent-tracker. So the claim is encoded as
SELECTION_CRITERION and checked on every run: this script refuses to emit a figure whose
subtitle would be lying, and `--hunt` re-derives which head to point at.

    uv run python docs/walkthrough/gen_attention_figure.py > /tmp/attn.svg
    uv run python docs/walkthrough/gen_attention_figure.py --hunt   # re-pick LAYER/HEAD

Then paste the SVG into content_concepts.py as ATTENTION_SVG (or let
scripts/regenerate_track_a.py splice it for you).
"""
import argparse
import math
import sys
from pathlib import Path

import mlx.core as mx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "notebooks"))
import tiny_gpt  # noqa: E402

CKPT = ROOT / "notebooks" / "checkpoints" / "tiny_gpt_v2"

# --- what we measure ----------------------------------------------------------
SENTENCE = "The dragon looked at the boy and it"
LAYER, HEAD = 1, 3          # 0-indexed; shown to readers as "layer 2 of 6, head 4 of 6"
MIN_ARC_PCT = 1             # arcs below this round to 0% and are omitted as clutter

# The figure's claim, made checkable: the head must send most of `it`'s attention back to
# the REFERENT, hard enough to be visually obvious. Attention heads are not stable across
# retrains, so this is verified every run rather than assumed.
REFERENT = "dragon"
MIN_REFERENT_PCT = 40

# --- layout -------------------------------------------------------------------
# Word boxes are FIXED: the sentence is a constant of the figure, so their geometry never
# needs to move. Only arc thickness, opacity and the labels are measurement-driven.
W, H = 720, 312
BOX_Y, BOX_H, BASE_Y = 208, 34, 204
BOXES = [  # (x, width) per token, in sentence order — hand-tuned to the rendered text
    (120, 48), (176, 78), (262, 78), (348, 38), (394, 48), (450, 48), (506, 48), (562, 38),
]
# stroke-width is linear in the weight: 1% -> 1.3px, 76% -> 8.8px in the original figure
STROKE_BASE, STROKE_PER_PCT = 1.2, 0.1
# An arc's height tracks how FAR BACK it reaches, not how strong it is — that is what keeps
# long arcs clear of short ones instead of stacking them on top of each other. Fitted from
# the hand-drawn original (five arcs, all within 1px).
ARC_RISE_BASE, ARC_RISE_PER_PX = 71.6, 0.36
LABEL_ABOVE_APEX = 8        # a quadratic Bezier peaks at (start + control) / 2
# Per-arc opacity is a LEGIBILITY setting tied to how much each arc overlaps its
# neighbours, not to the value it encodes (the original is deliberately non-monotonic
# in the weight). Keyed by source position so it stays stable across retrains.
OPACITY = {0: 0.40, 1: 0.84, 2: 0.45, 3: 0.36, 4: 0.36, 5: 0.36, 6: 0.39}
ARC_COLOUR, TOP_COLOUR = "#963d2c", "#b0402a"
INK, SOFT, GOLD, ROSE = "#231f18", "#6e6557", "#8c6a2a", "#8d4257"
MONO = 'font-family="ui-monospace,Menlo,monospace"'


def measure_all():
    """Replay the forward pass, capturing EVERY head's attention for the last token.

    tiny_gpt's forward pass doesn't return attention, so the block maths is repeated here.
    It must stay a mirror of tiny_gpt.CausalSelfAttention.__call__ — if the architecture
    changes there, change it here too.
    """
    model, tok, cfg = tiny_gpt.load(str(CKPT))
    ids = tok.encode(SENTENCE).ids
    toks = [tok.decode([i]) for i in ids]
    x = model.tok(mx.array([ids])) + model.pos(mx.arange(len(ids)))
    T = len(ids)
    mask = (1 - mx.tril(mx.ones((T, T)))) * -1e9
    rows = {}
    n_head = None
    for li, blk in enumerate(model.blocks):
        h = blk.ln1(x)
        B, T_, C = h.shape
        n_head = blk.attn.nh
        hd = C // n_head
        q, k, v = mx.split(blk.attn.c_attn(h), 3, axis=-1)
        q = mx.transpose(q.reshape(B, T_, n_head, hd), (0, 2, 1, 3))
        k = mx.transpose(k.reshape(B, T_, n_head, hd), (0, 2, 1, 3))
        v = mx.transpose(v.reshape(B, T_, n_head, hd), (0, 2, 1, 3))
        att = mx.softmax((q @ mx.transpose(k, (0, 1, 3, 2))) * (1 / math.sqrt(hd)) + mask, axis=-1)
        for hi in range(n_head):
            rows[(li, hi)] = [round(float(att[0, hi, -1, i]) * 100) for i in range(T)]
        x = x + blk.attn.c_proj(mx.transpose(att @ v, (0, 2, 1, 3)).reshape(B, T_, C))
        x = x + blk.mlp(blk.ln2(x))
    return toks, rows, len(model.blocks), n_head


def tracks_referent(toks, pct):
    """Does this head send most of the last token's attention back to the REFERENT?"""
    words = [t.strip() for t in toks]
    if REFERENT not in words:
        return False
    ri = words.index(REFERENT)
    earlier = range(len(words) - 1)
    return pct[ri] >= MIN_REFERENT_PCT and pct[ri] == max(pct[i] for i in earlier)


def measure():
    toks, rows, n_layer, n_head = measure_all()
    return toks, rows[(LAYER, HEAD)], n_layer, n_head


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _bezier_y_at_x(p0, p1, p2, target_x):
    """y of a quadratic Bezier at a given x (x is monotonic along these arcs, so bisect)."""
    lo, hi = 0.0, 1.0
    for _ in range(40):
        t = (lo + hi) / 2
        x = (1 - t) ** 2 * p0[0] + 2 * t * (1 - t) * p1[0] + t ** 2 * p2[0]
        if (x > target_x) == (p0[0] > p2[0]):
            lo = t
        else:
            hi = t
    t = (lo + hi) / 2
    return (1 - t) ** 2 * p0[1] + 2 * t * (1 - t) * p1[1] + t ** 2 * p2[1]


TEXT_ASCENT, TEXT_DESCENT = 10, 3      # roughly how far a 10px label extends around its baseline
# how far along its own arc a label may slide to find clear space, as Bezier t offsets from
# the apex. Ordered nearest-first so a label only moves as far as it has to.
SLIDE_OFFSETS = [0.0, 0.07, -0.07, 0.14, -0.14, 0.21, -0.21, 0.28, -0.28, 0.35, -0.35]


def _bezier_point(curve, t):
    (x0, y0), (x1, y1), (x2, y2) = curve
    return ((1 - t) ** 2 * x0 + 2 * t * (1 - t) * x1 + t ** 2 * x2,
            (1 - t) ** 2 * y0 + 2 * t * (1 - t) * y1 + t ** 2 * y2)


def _collides(label_y, arc_y, stroke):
    """Does the label's box overlap the arc's band?

    A symmetric distance test is wrong here: a label sitting just above a descending arc
    reads fine, while one the same distance below it does not.
    """
    return (label_y - TEXT_ASCENT < arc_y + stroke / 2
            and label_y + TEXT_DESCENT > arc_y - stroke / 2)


LABEL_HALF_WIDTH = 14      # a centred "15%" at 10px is roughly 28px across


def _place_label(own, others, placed):
    """Put an arc's label on its own curve, SLID ALONG IT into space everything else leaves free.

    Checks against EVERY other arc, not just the thickest one: when the weights are close
    together the figure is a bundle of similar curves, and a label dodging the dominant arc
    can land straight on a neighbour. Also checks labels already placed — two arcs peaking in
    the same region will otherwise print their percentages on top of each other. Sliding along
    the arc — what the hand-built original did by eye — finds open space while keeping the
    label on the curve it belongs to.
    """
    def clear_at(x, ly):
        for curve, stroke in others:
            if min(curve[0][0], curve[2][0]) <= x <= max(curve[0][0], curve[2][0]):
                if _collides(ly, _bezier_y_at_x(*curve, x), stroke):
                    return False
        for px, py in placed:
            if abs(px - x) < 2 * LABEL_HALF_WIDTH and abs(py - ly) < TEXT_ASCENT + TEXT_DESCENT:
                return False
        return True

    apex = None
    for dt in SLIDE_OFFSETS:
        x, y = _bezier_point(own, 0.5 + dt)
        ly = round(y) - TEXT_ASCENT
        if apex is None:
            apex = (round(x), ly)
        if clear_at(x, ly):
            return round(x), ly
    # Nowhere along the arc is clear. Drop the label below every arc that crosses its apex —
    # the space under the whole bundle is always free.
    x, _ = _bezier_point(own, 0.5)
    below = [_bezier_y_at_x(*c, x) + s / 2 for c, s in others
             if min(c[0][0], c[2][0]) <= x <= max(c[0][0], c[2][0])]
    return round(x), round(max(below) + TEXT_ASCENT + 6) if below else apex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hunt", action="store_true",
                    help="scan every layer/head for one that tracks the referent")
    args = ap.parse_args()

    toks, rows, n_layer, n_head = measure_all()
    words = [t.strip() for t in toks]

    if args.hunt:
        print(f"criterion: {REFERENT!r} must take the largest share of {words[-1]!r}'s "
              f"attention, and at least {MIN_REFERENT_PCT}%\n")
        hits = 0
        for (li, hi), pct in sorted(rows.items()):
            if tracks_referent(toks, pct):
                hits += 1
                share = {w: p for w, p in zip(words, pct) if p >= 1}
                print(f"  layer {li + 1} of {n_layer}, head {hi + 1} of {n_head}  "
                      f"(LAYER={li}, HEAD={hi})  ->  {share}")
        print(f"\n{hits}/{n_layer * n_head} heads qualify. Set LAYER/HEAD to one of them "
              f"and update the figure's subtitle.")
        return

    pct = rows[(LAYER, HEAD)]
    if not tracks_referent(toks, pct):
        top = max(range(len(words) - 1), key=lambda i: pct[i])
        sys.exit(
            f"layer {LAYER + 1}/head {HEAD + 1} no longer tracks {REFERENT!r}: {words[-1]!r} "
            f"now attends most to {words[top]!r} at {pct[top]}% "
            f"({REFERENT} gets {pct[words.index(REFERENT)]}%).\n"
            f"The figure's subtitle and caption would be lying. Re-pick with:\n"
            f"    uv run python {Path(__file__).name} --hunt")
    last = len(words) - 1
    src_x, src_w = BOXES[last]
    src_cx = src_x + src_w // 2

    ranked = sorted(range(last), key=lambda i: -pct[i])
    best = ranked[0]

    named = ", ".join(f"{words[i]} ({pct[i]} percent)" for i in ranked[1:] if pct[i] >= MIN_ARC_PCT)
    label = (f"Attention, measured: arcs from the word {words[last]} back to earlier words in the "
             f"sentence {SENTENCE}. The arc to {words[best]} carries {pct[best]} percent of the "
             f"attention; smaller arcs go to {named}; {words[last]} keeps {pct[last]} percent for itself.")

    L = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)}">',
         f'<text x="360" y="26" text-anchor="middle" font-size="13.5" font-weight="700" fill="{INK}">'
         f'Where does <tspan {MONO} fill="{GOLD}">{esc(words[last])}</tspan> look? — one real '
         f'attention head, measured</text>',
         f'<text x="360" y="44" text-anchor="middle" font-size="11" fill="{SOFT}">the trained Part 1 '
         f'model, layer {LAYER + 1} of {n_layer}, head {HEAD + 1} of {n_head} — each arc’s thickness '
         f'= how much of the blend</text>']

    # every arc's geometry up front, so each label can be placed clear of all the others
    def arc_of(i):
        cx = BOXES[i][0] + BOXES[i][1] // 2
        return (((src_cx, BASE_Y),
                 ((src_cx + cx) // 2,
                  BASE_Y - round(ARC_RISE_BASE + ARC_RISE_PER_PX * abs(src_cx - cx))),
                 (cx, BASE_Y)),
                STROKE_BASE + STROKE_PER_PCT * pct[i])

    drawn = [i for i in range(last) if pct[i] >= MIN_ARC_PCT]
    arcs = {i: arc_of(i) for i in drawn}
    placed = []          # label positions already committed, so later ones dodge them

    for i in range(last):
        if pct[i] < MIN_ARC_PCT:
            continue                      # ≈0% arcs are visual clutter, not information
        x0, w0 = BOXES[i]
        cx = x0 + w0 // 2
        mid = (src_cx + cx) // 2
        apex = BASE_Y - round(ARC_RISE_BASE + ARC_RISE_PER_PX * abs(src_cx - cx))
        top = pct[i] == pct[best]
        L.append(f'<path d="M {src_cx} {BASE_Y} Q {mid} {apex} {cx} {BASE_Y}" fill="none" '
                 f'stroke="{TOP_COLOUR if top else ARC_COLOUR}" '
                 f'stroke-width="{STROKE_BASE + STROKE_PER_PCT * pct[i]:.1f}" '
                 f'opacity="{OPACITY.get(i, 0.40)}"/>')
        own = ((src_cx, BASE_Y), (mid, apex), (cx, BASE_Y))
        if top:
            lx, ly = mid, round((BASE_Y + apex) / 2) - LABEL_ABOVE_APEX
        else:
            lx, ly = _place_label(own, [arcs[j] for j in drawn if j != i], placed)
        placed.append((lx, ly))
        L.append(f'<text x="{lx}" y="{ly}" text-anchor="middle" font-size="{11 if top else 10}" '
                 f'font-weight="{700 if top else 400}" fill="{TOP_COLOUR if top else ARC_COLOUR}">'
                 f'{pct[i]}%</text>')

    for i, (x0, w0) in enumerate(BOXES):
        if i == last:
            fill, stroke, sw = "#f3ecd9", GOLD, 2.2
        elif i == best:
            fill, stroke, sw = "#f1e4e4", ROSE, 2.2
        else:
            fill, stroke, sw = "#f3ece1", ARC_COLOUR, 1.3
        L.append(f'<rect x="{x0}" y="{BOX_Y}" width="{w0}" height="{BOX_H}" rx="7" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}"/>')
        L.append(f'<text x="{x0 + w0 // 2}" y="{BOX_Y + 22}" text-anchor="middle" font-size="14" '
                 f'fill="{INK}" {MONO}>{esc(words[i])}</text>')

    zero = [words[i] for i in range(last) if pct[i] < MIN_ARC_PCT]
    zero_txt = " and ".join(f'“{z}”' for z in zero) if zero else "the filler words"
    L += [f'<text x="{src_cx}" y="260" text-anchor="middle" font-size="9.5" fill="{GOLD}">the token '
          f'asking (its “query”) — keeps {pct[last]}% for itself</text>',
          f'<text x="{BOXES[best][0] + BOXES[best][1] // 2}" y="260" text-anchor="middle" '
          f'font-size="9.5" fill="{ROSE}">the best-matching “key”</text>',
          f'<text x="30" y="292" font-size="10.5" fill="{SOFT}">{zero_txt} get ≈0%. This head has '
          f'learned to track who the sentence is about; other heads in the same</text>',
          f'<text x="30" y="308" font-size="10.5" fill="{SOFT}">model attend to different things '
          f'(recent words, sentence starts) — together they give the next layer rich context.</text>',
          "</svg>"]
    print("\n".join(L))


if __name__ == "__main__":
    main()
