"""gen_loss_surface.py — generate the animated 3-D loss-surface SVG for Part 0 · Concepts.

A two-weight loss surface drawn as an isometric wireframe, with a descent path
produced by running REAL gradient descent on the surface function (no faked
trajectory; constant learning rate — the shrinking hops are the shrinking
gradient, which is the teaching point). The ball replays the descent step by
step on a ~20 s CSS loop: pause, hop, pause; the trail draws itself behind it;
a ring pulses at the minimum. Click pauses/resumes; prefers-reduced-motion gets
the original static figure (ball at start, full path drawn).

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


# ---- animation timing -----------------------------------------------------------
STEP_T = 1.2      # seconds per descent step: 0.65 s pause + 0.55 s hop
T = 20.0          # full cycle; last arrival at 13*1.2 = 15.6 s, then hold


def pct(s):
    return round(min(s, T) / T * 100, 2)


def main():
    n = 13                                            # mesh resolution
    rng = [(-1 + 2 * i / (n - 1)) for i in range(n)]
    mesh = []
    for u in rng:                                     # lines of constant u
        mesh.append([proj(u, v, f(u, v)) for v in rng])
    for v in rng:                                     # lines of constant v
        mesh.append([proj(u, v, f(u, v)) for u in rng])

    # real gradient descent from a high corner (constant learning rate 0.16:
    # the steps shrink because the gradient does, not because we schedule them)
    path, (u, v) = [], (-0.92, 0.78)
    for _ in range(14):
        path.append(proj(u, v, f(u, v) + 0.012))      # nudge above the surface
        gu, gv = grad(u, v)
        u, v = u - 0.16 * gu, v - 0.16 * gv
    end = path[-1]
    sx, sy = path[0]

    # cumulative length fractions for the self-drawing trail (pathLength=100)
    seg = [math.dist(path[i], path[i + 1]) for i in range(len(path) - 1)]
    tot = sum(seg)
    cum = [0.0]
    for length in seg:
        cum.append(cum[-1] + length / tot)

    # ball: pause then hop to the next point; trail dashoffset synced to the hops
    ball_kf = ['0%{transform:translate(0px,0px)}']
    trail_kf = ['0%{stroke-dashoffset:100}']
    for i in range(len(path) - 1):
        depart, arrive = pct(i * STEP_T + 0.65), pct((i + 1) * STEP_T)
        dx0, dy0 = round(path[i][0] - sx, 1), round(path[i][1] - sy, 1)
        dx1, dy1 = round(path[i + 1][0] - sx, 1), round(path[i + 1][1] - sy, 1)
        ball_kf.append(f'{depart}%{{transform:translate({dx0}px,{dy0}px);'
                       'animation-timing-function:ease-in-out}')
        ball_kf.append(f'{arrive}%{{transform:translate({dx1}px,{dy1}px)}}')
        trail_kf.append(f'{depart}%{{stroke-dashoffset:{round(100 - cum[i] * 100, 2)};'
                        'animation-timing-function:ease-in-out}')
        trail_kf.append(f'{arrive}%{{stroke-dashoffset:{round(100 - cum[i + 1] * 100, 2)}}}')
    fx, fy = round(end[0] - sx, 1), round(end[1] - sy, 1)
    ball_kf.append(f'100%{{transform:translate({fx}px,{fy}px)}}')
    trail_kf.append('100%{stroke-dashoffset:0}')

    dots, dot_css = [], []
    for i, (x, y) in enumerate(path[1:], 1):
        a = pct(i * STEP_T)
        dot_css.append(f'.gd-d{i}{{opacity:0;animation:gdd{i} {T:.0f}s linear infinite}}'
                       f'@keyframes gdd{i}{{0%{{opacity:0}}{a}%{{opacity:0}}'
                       f'{round(a + 1, 2)}%{{opacity:1}}100%{{opacity:1}}}}')
        dots.append(f'<circle class="gd-d{i}" cx="{x:.1f}" cy="{y:.1f}" r="2.4" fill="#b0402a"/>')

    end_at = pct((len(path) - 1) * STEP_T)
    style = f'''<style>
.gd-ball{{animation:gdball {T:.0f}s linear infinite}}
@keyframes gdball{{{''.join(ball_kf)}}}
.gd-trail{{stroke-dasharray:100;stroke-dashoffset:100;animation:gdtrail {T:.0f}s linear infinite}}
@keyframes gdtrail{{{''.join(trail_kf)}}}
{''.join(dot_css)}
.gd-startlbl{{animation:gdstart {T:.0f}s linear infinite}}
@keyframes gdstart{{0%{{opacity:1}}{pct(1.4)}%{{opacity:1}}{pct(2.4)}%{{opacity:0.35}}100%{{opacity:0.35}}}}
.gd-ring{{opacity:0;transform-box:fill-box;transform-origin:center;animation:gdring {T:.0f}s linear infinite}}
@keyframes gdring{{0%{{opacity:0;transform:scale(.4)}}{end_at}%{{opacity:0;transform:scale(.4)}}{pct(15.6 + 0.5)}%{{opacity:.8;transform:scale(1)}}{pct(15.6 + 1.6)}%{{opacity:0;transform:scale(1.9)}}100%{{opacity:0}}}}
@media (prefers-reduced-motion: reduce){{.gd-ball,.gd-trail,.gd-startlbl,.gd-ring,[class^=gd-d]{{animation:none !important}}.gd-trail{{stroke-dashoffset:0}}[class^=gd-d]{{opacity:1}}}}
</style>'''

    out = [f'<svg id="gdvalley" style="cursor:pointer" viewBox="0 0 {W} {H}" role="img" '
           'aria-label="A loss surface over two weights, drawn as a 3-D wireframe valley. '
           'A ball takes real gradient-descent steps from a high slope down to the lowest '
           'point, pausing between hops; the hops shrink as the valley flattens, because '
           'the gradient does. The dotted path draws itself behind the ball and a ring '
           'pulses at the minimum.">']
    for line in mesh:
        out.append(f'<polyline points="{pts(line)}" fill="none" stroke="#cfc5ae" '
                   'stroke-width="1" opacity="0.85"/>')
    out.append(style)
    # trail under the dots and ball; pathLength normalises dashoffset to 0–100
    out.append(f'<polyline class="gd-trail" pathLength="100" points="{pts(path)}" '
               'fill="none" stroke="#b0402a" stroke-width="2.4"/>')
    out.extend(dots)
    out.append(f'<circle cx="{end[0]:.1f}" cy="{end[1]:.1f}" r="5" fill="#5f6c33" '
               'stroke="#fff" stroke-width="1.8"/>')
    out.append(f'<text x="{end[0] + 12:.0f}" y="{end[1] + 18:.0f}" font-size="12" '
               'fill="#5f6c33">lowest loss</text>')
    out.append(f'<circle class="gd-ring" cx="{end[0]:.1f}" cy="{end[1]:.1f}" r="14" '
               'fill="none" stroke="#5f6c33" stroke-width="2"/>')
    out.append(f'<g class="gd-ball"><circle cx="{sx:.1f}" cy="{sy:.1f}" r="9" '
               'fill="#b0402a" stroke="#fff" stroke-width="2.5"/></g>')
    out.append(f'<text class="gd-startlbl" x="{sx + 16:.0f}" y="{sy - 12:.0f}" font-size="12" '
               'fill="#231f18">start: random weights</text>')
    # axis hints + legend
    out.append('<text x="52" y="210" font-size="12" fill="#6e6557" '
               'transform="rotate(-64 52 210)">loss (height) ↑</text>')
    out.append(f'<text x="{W - 190}" y="{H - 14}" font-size="12" fill="#6e6557">weight 1 →</text>')
    out.append(f'<text x="120" y="{H - 14}" font-size="12" fill="#6e6557">← weight 2</text>')
    out.append('<text x="18" y="22" font-size="10.5" fill="#998f7d" '
               'font-family="ui-monospace,Menlo,monospace">each hop = one update · '
               'click to pause / resume</text>')
    out.append('<script>document.getElementById("gdvalley").addEventListener("click",'
               'function(){this.classList.toggle("gd-paused");var p=this.classList.'
               'contains("gd-paused")?"paused":"running";this.querySelectorAll("*").'
               'forEach(function(e){e.style.animationPlayState=p})});</script>')
    out.append('</svg>')
    print("\n".join(out))


if __name__ == "__main__":
    main()
