"""gen_loss_surface.py — generate the 3-D loss-surface SVG for Part 0 · Concepts.

The walk-through's diagrams are static inline SVG (no JS), but a 3-D wireframe is
tedious to hand-author, so this script generates it: a two-weight loss surface
drawn as an isometric mesh, with a descent path produced by running REAL gradient
descent on the surface function (no faked trajectory).

Usage:  uv run python docs/walkthrough/gen_loss_surface.py > /tmp/surface.svg
        …then paste the output into SURFACE3D_SVG in content_concepts.py.
"""
import math

# ---- the surface: a valley with a little character (one clear global minimum) --
def f(u, v):
    return 0.55 * u * u + 0.9 * v * v + 0.18 * math.sin(2.6 * u) * math.cos(1.7 * v) + 0.18


def grad(u, v, eps=1e-5):
    return ((f(u + eps, v) - f(u - eps, v)) / (2 * eps),
            (f(u, v + eps) - f(u, v - eps)) / (2 * eps))


# ---- isometric projection ------------------------------------------------------
W, H = 660, 350
CX, CY = W / 2, 248
SU, SV, SZ = 200, 130, 150          # horizontal spread (u, v) and height scale


def proj(u, v, z):
    x = CX + (u - v) * SU * 0.78
    y = CY + (u + v) * SV * 0.55 - z * SZ
    return x, y


def pts(seq):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in seq)


def main():
    n = 13                                            # mesh resolution
    rng = [(-1 + 2 * i / (n - 1)) for i in range(n)]
    mesh = []
    for u in rng:                                     # lines of constant u
        mesh.append([proj(u, v, f(u, v)) for v in rng])
    for v in rng:                                     # lines of constant v
        mesh.append([proj(u, v, f(u, v)) for u in rng])

    # real gradient descent from a high corner
    path, (u, v) = [], (-0.92, 0.78)
    for _ in range(14):
        path.append(proj(u, v, f(u, v) + 0.012))      # nudge above the surface
        gu, gv = grad(u, v)
        u, v = u - 0.16 * gu, v - 0.16 * gv
    end = path[-1]

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="A loss surface over two '
           'weights, drawn as a 3-D wireframe valley. A ball starts high on one slope and '
           'a dotted gradient-descent path of real downhill steps curves to the lowest '
           'point of the valley.">']
    out.append('<defs><marker id="arS" markerWidth="8" markerHeight="8" refX="5" refY="2.5" '
               'orient="auto"><path d="M0,0 L5,2.5 L0,5 Z" fill="#e8462e"/></marker></defs>')
    for line in mesh:
        out.append(f'<polyline points="{pts(line)}" fill="none" stroke="#b9c2d6" '
                   'stroke-width="1" opacity="0.85"/>')
    # descent path (drawn after the mesh so it reads as "on" the surface)
    out.append(f'<polyline points="{pts(path)}" fill="none" stroke="#e8462e" '
               'stroke-width="2.4" stroke-dasharray="6 4" marker-end="url(#arS)"/>')
    for x, y in path[1:-1:2]:
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="#e8462e"/>')
    sx, sy = path[0]
    out.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="9" fill="#e8462e" stroke="#fff" '
               'stroke-width="2.5"/>')
    out.append(f'<text x="{sx + 16:.0f}" y="{sy - 12:.0f}" font-size="12" '
               'fill="#1c2230">start: random weights</text>')
    out.append(f'<circle cx="{end[0]:.1f}" cy="{end[1]:.1f}" r="5" fill="#0e7a5f" '
               'stroke="#fff" stroke-width="1.8"/>')
    out.append(f'<text x="{end[0] + 12:.0f}" y="{end[1] + 18:.0f}" font-size="12" '
               'fill="#0e7a5f">lowest loss</text>')
    # axis hints
    out.append('<text x="52" y="210" font-size="12" fill="#5a6373" '
               'transform="rotate(-64 52 210)">loss (height) ↑</text>')
    out.append(f'<text x="{W - 190}" y="{H - 14}" font-size="12" fill="#5a6373">weight 1 →</text>')
    out.append(f'<text x="120" y="{H - 14}" font-size="12" fill="#5a6373">← weight 2</text>')
    out.append('</svg>')
    print("\n".join(out))


if __name__ == "__main__":
    main()
