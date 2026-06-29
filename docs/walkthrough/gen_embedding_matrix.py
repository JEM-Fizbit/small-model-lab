"""gen_embedding_matrix.py — emit the W_E embedding-matrix figure for Part 0 §3.

Self-contained: loads the trained Track A v2 checkpoint, reads its real token-embedding
table (model.tok.weight, shape [vocab, n_embd]), and prints an SVG to stdout. Every cell
is a measured weight — no illustrative numbers. Columns are real tokens swept A→Z (first
and last whole-word tokens, alphabetical); the middle is elided with ⋯, exactly as 3b1b's
W_E figure elides the ~50k-word vocabulary.

Run:   uv run python docs/walkthrough/gen_embedding_matrix.py > /tmp/we.svg
Then:  paste the SVG into content_concepts.py as WE_MATRIX_SVG (see the comment there).
Rerun whenever the checkpoint is retrained; the figure tracks the real weights.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "notebooks"))
import tiny_gpt                 # noqa: E402

CKPT = ROOT / "notebooks/checkpoints/tiny_gpt_v2"
N_END = 8           # tokens shown from each end of the alphabet
DIMS = list(range(11))          # embedding dims shown as rows …
SAT = 0.07          # |value| >= SAT -> full red/blue (≈85th pct of |W_E|)

INK = "#231f18"; SOFT = "#6e6557"; FAINT = "#998f7d"; LINE = "#ddd4c2"
GOLD = "#8c6a2a"
MONO = 'font-family="ui-monospace,Menlo,monospace"'
SERIF = "font-family=\"Charter,'Iowan Old Style',Georgia,serif\""


def main():
    model, tok, cfg = tiny_gpt.load(str(CKPT))
    E = model.tok.weight
    dims = DIMS + [cfg.n_embd - 1]          # … plus the last dim, mirroring 3b1b's ⋮ + final row

    # whole-word, alphabetic tokens (byte-level BPE leading-space marker 'Ġ')
    words, seen = [], set()
    # sort by id: get_vocab()'s dict order isn't stable across runs, so iterate deterministically
    # (lowest id wins each lowercase slot — usually the more common, lowercase form)
    for t, i in sorted(tok.get_vocab().items(), key=lambda kv: kv[1]):
        if t.startswith("Ġ") and t[1:].isalpha() and len(t) >= 4 and t[1:].lower() not in seen:
            seen.add(t[1:].lower()); words.append((t[1:].lower(), t[1:], i))  # (sort key, real-cased token, id)
    words.sort()
    sel = words[:N_END] + [("…", "…", None)] + words[-N_END:]

    def numcol(v):
        t = max(-1.0, min(1.0, v / SAT)); grey = (154, 143, 121)
        end = (176, 39, 31) if t >= 0 else (43, 86, 168)
        c = tuple(round(grey[k] + (end[k] - grey[k]) * abs(t)) for k in range(3))
        return f"rgb({c[0]},{c[1]},{c[2]})"

    def fmt(v):
        return f"{'+' if v >= 0 else '−'}{abs(v):.2f}"

    n = len(sel); cw = 46; ch = 26
    gx = 156; gy = 158; gw = n * cw   # gy raised to fit the word + token-id header rows above the matrix
    vrows = len(dims) - 1
    gh = (vrows + 2) * ch
    Wd = gx + gw + 70; Ht = gy + gh + 72
    s = [f'<svg viewBox="0 0 {Wd} {Ht}" role="img" aria-label="The embedding matrix W_E of the '
         f'trained Track A model: {cfg.vocab_size} token columns (real tokens, alphabetical) by '
         f'{cfg.n_embd} dimension rows; each cell a real signed learned value, red positive, blue negative.">']
    bx0, bx1 = gx + 6, gx + gw - 6; bxm = (bx0 + bx1) / 2; byb = 72
    s.append(f'<path d="M {bx0} {byb} q 0 -12 12 -12 L {bxm-14} {byb-12} q 14 0 14 -12 q 0 12 14 12 '
             f'L {bx1-12} {byb-12} q 12 0 12 12" fill="none" stroke="{SOFT}" stroke-width="1.4"/>')
    s.append(f'<text x="{bxm}" y="{byb-26}" text-anchor="middle" font-size="15" {SERIF} fill="{INK}">'
             f'All tokens, <tspan font-style="italic">~{round(cfg.vocab_size/1000)}k</tspan></text>')
    yw, yid = gy - 27, gy - 11        # word-label baseline & token-id baseline — both OUTSIDE the W_E matrix
    for ci, (_sk, w, i) in enumerate(sel):
        cx = gx + ci * cw + cw / 2
        if i is None:
            s.append(f'<text x="{cx}" y="{yw}" text-anchor="middle" font-size="13" fill="{FAINT}">⋯</text>')
            s.append(f'<text x="{cx}" y="{yid}" text-anchor="middle" font-size="11" fill="{FAINT}">⋯</text>')
        else:
            s.append(f'<text x="{cx}" y="{yw}" font-size="11.5" {MONO} fill="{INK}" '
                     f'transform="rotate(-50 {cx} {yw})">{w}</text>')
            s.append(f'<text x="{cx}" y="{yid}" text-anchor="middle" font-size="9" {MONO} fill="{FAINT}">#{i}</text>')
    # the token id is a column LABEL, not part of W_E: name the row and rule it off from the values
    s.append(f'<text x="{gx-12}" y="{yid}" text-anchor="end" font-size="8.5" {SERIF} fill="{SOFT}">token id →</text>')
    s.append(f'<line x1="{gx-8}" y1="{gy-5}" x2="{gx+gw+8}" y2="{gy-5}" stroke="{LINE}" stroke-width="0.9"/>')

    def bracket(x, top, bot, left=True):
        t = 8 if left else -8
        return f'<path d="M {x+t} {top} L {x} {top} L {x} {bot} L {x+t} {bot}" fill="none" stroke="{INK}" stroke-width="2.2"/>'
    s.append(bracket(gx - 8, gy - 2, gy + gh + 2, True))
    s.append(bracket(gx + gw + 8, gy - 2, gy + gh + 2, False))
    midy = gy + gh / 2
    s.append(f'<text x="70" y="{midy+2}" text-anchor="middle" font-size="34" {SERIF} font-style="italic" '
             f'fill="{INK}">W<tspan font-size="22" dy="8">E</tspan><tspan font-size="34" dy="-8" font-style="normal"> =</tspan></text>')
    for ci, (_sk, w, i) in enumerate(sel):
        cx = gx + ci * cw
        for r in range(vrows):
            y = gy + r * ch
            if i is None:
                s.append(f'<text x="{cx+cw/2}" y="{y+ch/2+4}" text-anchor="middle" font-size="12" fill="{FAINT}">⋯</text>')
                continue
            v = round(float(E[i, dims[r]]), 2); color = numcol(v)
            s.append(f'<text x="{cx+cw/2}" y="{y+ch/2+4}" text-anchor="middle" font-size="11.5" {MONO} fill="{color}">{fmt(v)}</text>')
        yv = gy + vrows * ch
        s.append(f'<text x="{cx+cw/2}" y="{yv+ch/2+4}" text-anchor="middle" font-size="13" fill="{FAINT}">⋮</text>')
        yf = gy + (vrows + 1) * ch
        if i is None:
            s.append(f'<text x="{cx+cw/2}" y="{yf+ch/2+4}" text-anchor="middle" font-size="12" fill="{FAINT}">⋯</text>')
        else:
            v = round(float(E[i, dims[-1]]), 2); color = numcol(v)
            s.append(f'<text x="{cx+cw/2}" y="{yf+ch/2+4}" text-anchor="middle" font-size="11.5" {MONO} fill="{color}">{fmt(v)}</text>')
    rbx = gx + gw + 24
    s.append(f'<path d="M {rbx-8} {gy} q 8 0 8 10 L {rbx} {midy-10} q 0 10 8 10 q -8 0 -8 10 '
             f'L {rbx} {gy+gh-10} q 0 10 -8 10" fill="none" stroke="{FAINT}" stroke-width="1.2"/>')
    s.append(f'<text x="{rbx+14}" y="{midy-4}" font-size="12" {SERIF} fill="{SOFT}">{cfg.n_embd}</text>')
    s.append(f'<text x="{rbx+14}" y="{midy+11}" font-size="12" {SERIF} fill="{SOFT}">dims</text>')
    s.append(f'<text x="{gx+gw/2}" y="{gy+gh+44}" text-anchor="middle" font-size="23" {SERIF} fill="{INK}">Embedding matrix</text>')
    ly = gy + gh + 62
    s.append(f'<text x="{gx}" y="{ly}" font-size="10.5" {SERIF} fill="{SOFT}">each cell is one real learned number:</text>')
    s.append(f'<text x="{gx+212}" y="{ly}" font-size="11" {MONO} fill="rgb(176,39,31)">+ red</text>')
    s.append(f'<text x="{gx+268}" y="{ly}" font-size="10.5" {SERIF} fill="{SOFT}">stronger positive,</text>')
    s.append(f'<text x="{gx+372}" y="{ly}" font-size="11" {MONO} fill="rgb(43,86,168)">− blue</text>')
    s.append(f'<text x="{gx+428}" y="{ly}" font-size="10.5" {SERIF} fill="{SOFT}">stronger negative</text>')
    s.append('</svg>')
    print("\n".join(s))


if __name__ == "__main__":
    main()
