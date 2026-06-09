"""build.py — assemble the tiny-GPT walk-through into one self-contained HTML file.

HYBRID DESIGN (see docs/DECISIONS.md / the chat that produced this):
  - The *narrative* is hand-authored, prose-first, in `content.py`.
  - The *code blocks and outputs* are pulled programmatically from the real notebooks
    (`notebooks/01_…ipynb`, `02_…ipynb`, `03_…ipynb`) by anchor string, so what the
    reader sees is guaranteed to match the code that actually ran. Change the notebook,
    re-run this script, the page updates.
  - Figures (the loss curves) are base64-embedded, so the output is a single file you
    can double-click or email — no server, no external assets, works offline.

Run:   uv run python docs/walkthrough/build.py
Out:   docs/walkthrough/tiny-gpt.html
"""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

from jinja2 import Environment, BaseLoader
from pygments import highlight
from pygments.lexers import PythonLexer, JsonLexer, TextLexer
from pygments.formatters import HtmlFormatter

ROOT = Path(__file__).resolve().parents[2]          # repo root
NB_DIR = ROOT / "notebooks"
NOTEBOOKS = {
    "01": NB_DIR / "01_tiny_gpt_from_scratch.ipynb",
    "02": NB_DIR / "02_tiny_gpt_tuned.ipynb",
    "03": NB_DIR / "03_tiny_gpt_chat.ipynb",
}

# Plain-source files (chat.py / tiny_gpt.py / the trainer) we also quote from, by anchor.
SRC_FILES = {
    "chat": NB_DIR / "chat.py",
    "lib": NB_DIR / "tiny_gpt.py",
    "train": NB_DIR / "train_v2_checkpoint.py",
}

_lexer = PythonLexer()
_fmt = HtmlFormatter(nowrap=False, cssclass="hl", style="monokai")


# ---------------------------------------------------------------- extraction --
def _load_cells(nb_key: str):
    nb = json.loads(NOTEBOOKS[nb_key].read_text())
    return nb["cells"]


def _code_cells(nb_key: str):
    return [c for c in _load_cells(nb_key) if c["cell_type"] == "code"]


def get_code(nb_key: str, anchor: str) -> str:
    """Full source of the first code cell in `nb_key` whose source contains `anchor`."""
    for c in _code_cells(nb_key):
        src = "".join(c["source"])
        if anchor in src:
            return src.rstrip("\n")
    raise LookupError(f"anchor {anchor!r} not found in notebook {nb_key}")


def get_src(file_key: str, start: str | None = None, end: str | None = None) -> str:
    """A slice of a plain .py file, from the line containing `start` to the line
    containing `end` (inclusive). With no bounds, returns the whole file body
    minus the module docstring."""
    text = SRC_FILES[file_key].read_text()
    if start is None and end is None:
        # drop a leading module docstring for quoting purposes
        return re.sub(r'^\s*""".*?"""\s*', "", text, count=1, flags=re.S).strip()
    lines = text.splitlines()
    i0 = next(i for i, ln in enumerate(lines) if start in ln)
    i1 = (next(i for i, ln in enumerate(lines) if end in ln and i >= i0)
          if end else len(lines) - 1)
    return "\n".join(lines[i0:i1 + 1])


def get_file(relpath: str, start: str | None = None, end: str | None = None) -> str:
    """A slice of any repo file by line-substring anchors (inclusive); whole file if no bounds."""
    text = (ROOT / relpath).read_text()
    if start is None and end is None:
        return text.rstrip("\n")
    lines = text.splitlines()
    i0 = next(i for i, ln in enumerate(lines) if start in ln)
    i1 = (next(i for i, ln in enumerate(lines) if end in ln and i >= i0)
          if end else len(lines) - 1)
    return "\n".join(lines[i0:i1 + 1])


def get_output(nb_key: str, anchor: str, max_chars: int | None = None) -> str:
    """Concatenated stream/text output of the first code cell containing `anchor`."""
    for c in _code_cells(nb_key):
        src = "".join(c["source"])
        if anchor not in src:
            continue
        chunks = []
        for o in c.get("outputs", []):
            if o.get("output_type") == "stream":
                chunks.append("".join(o.get("text", [])))
            elif o.get("output_type") == "execute_result":
                chunks.append("".join(o.get("data", {}).get("text/plain", [])))
        text = "".join(chunks).rstrip("\n")
        if max_chars and len(text) > max_chars:
            text = text[:max_chars].rstrip() + "\n…"
        return text
    raise LookupError(f"anchor {anchor!r} not found in notebook {nb_key}")


def img_data_uri(filename: str) -> str:
    b = (NB_DIR / filename).read_bytes()
    return "data:image/png;base64," + base64.b64encode(b).decode()


# ------------------------------------------------------------------ rendering --
def render_code(src: str) -> str:
    return highlight(src, _lexer, _fmt)


_LEXERS = {".py": PythonLexer(), ".json": JsonLexer()}


def render_code_lang(src: str, suffix: str) -> str:
    return highlight(src, _LEXERS.get(suffix, TextLexer()), _fmt)


def render_block(block, ctx):
    """block is a tuple (kind, *args). Returns an HTML fragment."""
    kind = block[0]
    if kind == "prose":
        return f'<div class="prose">{block[1]}</div>'
    if kind == "code":
        nb, anchor = block[1], block[2]
        caption = block[3] if len(block) > 3 else None
        src = get_code(nb, anchor)
        cap = f'<figcaption>{caption}</figcaption>' if caption else ""
        nb_label = {"01": "notebook 01", "02": "notebook 02", "03": "notebook 03"}[nb]
        return (f'<figure class="codefig"><div class="codebar">'
                f'<span class="dot"></span><span class="dot"></span><span class="dot"></span>'
                f'<span class="srcname">{nb_label}</span></div>{render_code(src)}{cap}</figure>')
    if kind == "srccode":
        fkey = block[1]
        start = block[2] if len(block) > 2 else None
        end = block[3] if len(block) > 3 else None
        caption = block[4] if len(block) > 4 else None
        src = get_src(fkey, start, end)
        cap = f'<figcaption>{caption}</figcaption>' if caption else ""
        name = {"chat": "chat.py", "lib": "tiny_gpt.py", "train": "train_v2_checkpoint.py"}[fkey]
        return (f'<figure class="codefig"><div class="codebar">'
                f'<span class="dot"></span><span class="dot"></span><span class="dot"></span>'
                f'<span class="srcname">{name}</span></div>{render_code(src)}{cap}</figure>')
    if kind == "filecode":
        from pathlib import Path as _P
        relpath = block[1]
        caption = block[2] if len(block) > 2 else None
        start = block[3] if len(block) > 3 else None
        end = block[4] if len(block) > 4 else None
        src = get_file(relpath, start, end)
        cap = f'<figcaption>{caption}</figcaption>' if caption else ""
        name = _P(relpath).name
        return (f'<figure class="codefig"><div class="codebar">'
                f'<span class="dot"></span><span class="dot"></span><span class="dot"></span>'
                f'<span class="srcname">{name}</span></div>'
                f'{render_code_lang(src, _P(relpath).suffix)}{cap}</figure>')
    if kind == "gloss":
        return f'<div class="gloss"><div class="gloss-tag">what this says</div>{block[1]}</div>'
    if kind == "output":
        nb, anchor = block[1], block[2]
        label = block[3] if len(block) > 3 else "output"
        mx = block[4] if len(block) > 4 else None
        text = get_output(nb, anchor, mx)
        return (f'<div class="term"><div class="term-tag">{label}</div>'
                f'<pre>{_esc(text)}</pre></div>')
    if kind == "rawoutput":
        text, label = block[1], (block[2] if len(block) > 2 else "output")
        return (f'<div class="term"><div class="term-tag">{label}</div>'
                f'<pre>{_esc(text)}</pre></div>')
    if kind == "figure":
        fn, caption = block[1], (block[2] if len(block) > 2 else "")
        cap = f'<figcaption>{caption}</figcaption>' if caption else ""
        return (f'<figure class="imgfig"><img src="{img_data_uri(fn)}" alt="{caption}"/>'
                f'{cap}</figure>')
    if kind == "diagram":
        svg, caption = block[1], (block[2] if len(block) > 2 else "")
        cap = f'<figcaption>{caption}</figcaption>' if caption else ""
        return f'<figure class="imgfig diagram">{svg}{cap}</figure>'
    if kind == "callout":
        variant, title, html = block[1], block[2], block[3]
        return (f'<aside class="callout {variant}"><div class="callout-title">{title}</div>'
                f'<div class="callout-body">{html}</div></aside>')
    if kind == "table":
        return f'<div class="tablewrap">{block[1]}</div>'
    raise ValueError(f"unknown block kind {kind!r}")


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# -------------------------------------------------------------------- assemble --
SITE = Path(__file__).resolve().parent / "site"   # multi-page output root
# slm-lab lives within the public AI Knowledge Hub (cross-branding).
HUB_URL = "https://possible-meeting-f8b.notion.site/AI-Knowledge-Hub-718881b895cb4666a2fcfc1887b77566"


def _asset_uri(name: str) -> str:
    """base64 a file from assets/ as a data URI (e.g. the headshot). '' if missing."""
    p = Path(__file__).resolve().parent / "assets" / name
    if not p.exists():
        return ""
    mime = "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def _render_chapter(tmpl, *, meta, hero, sections, primer, nav, footer_note, hub_url):
    """Render one chapter page (Track A or Track B) from its sections."""
    rendered = []
    for sec in sections:
        body = "\n".join(render_block(b, sec) for b in sec["blocks"])
        rendered.append({**sec, "body": body})
    toc, seen = [], {}
    for sec in sections:
        part = sec.get("part")
        if part and part not in seen:
            seen[part] = True
            toc.append({"part": part})
        toc.append({"id": sec["id"], "num": sec.get("num", ""), "title": sec["title"]})
    return tmpl.render(
        meta=meta, hero=hero, sections=rendered, toc=toc, primer=primer,
        nav=nav, footer_note=footer_note, hub_url=hub_url,
        pygments_css=_fmt.get_style_defs(".hl"),
    )


def main():
    import content  # local import so a syntax error there points cleanly here

    env = Environment(loader=BaseLoader(), autoescape=False)
    page_tmpl = env.from_string(content.TEMPLATE)
    landing_tmpl = env.from_string(content.LANDING_TEMPLATE)

    written = []

    # Detect optional chapters, so nav + landing reflect what's present.
    try:
        import content_concepts
        concepts_live = True
    except ModuleNotFoundError:
        content_concepts = None
        concepts_live = False
    try:
        import content_b
        track_b_live = True
    except ModuleNotFoundError:
        content_b = None
        track_b_live = False

    def nav_for(active):
        """Top-nav for a chapter page (all chapters live at site/<slug>/)."""
        def href(slug):
            return "./" if slug == active else f"../{slug}/"
        items = [{"label": "Home", "href": "../"}]
        if concepts_live:
            items.append({"label": "Part 0 · Concepts", "href": href("ideas"),
                          "active": active == "ideas"})
        items.append({"label": "Part 1 · Pre-training", "href": href("track-a"),
                      "active": active == "track-a"})
        if track_b_live:
            items.append({"label": "Part 2 · Post-training", "href": href("track-b"),
                          "active": active == "track-b"})
        else:
            items.append({"label": "Part 2 · Post-training", "href": None, "note": "coming"})
        return items

    # --- Part 0 · Concepts → site/ideas/  (no code → no Python primer) ---
    if concepts_live:
        html0 = _render_chapter(
            page_tmpl, meta=content_concepts.META, hero=content_concepts.HERO,
            sections=content_concepts.SECTIONS, primer="", nav=nav_for("ideas"),
            footer_note="Part 0 of the <strong>slm-lab</strong> walk-through.", hub_url=HUB_URL,
        )
        (SITE / "ideas").mkdir(parents=True, exist_ok=True)
        (SITE / "ideas" / "index.html").write_text(html0)
        written.append(("ideas/index.html", len(html0), len(content_concepts.SECTIONS)))

    # --- Part 1 · Pre-training → site/track-a/ ---
    html_a = _render_chapter(
        page_tmpl, meta=content.META, hero=content.HERO, sections=content.SECTIONS,
        primer=content.PYTHON_PRIMER, nav=nav_for("track-a"),
        footer_note="Part 1 of the <strong>slm-lab</strong> walk-through.", hub_url=HUB_URL,
    )
    (SITE / "track-a").mkdir(parents=True, exist_ok=True)
    (SITE / "track-a" / "index.html").write_text(html_a)
    written.append(("track-a/index.html", len(html_a), len(content.SECTIONS)))

    # --- Part 2 · Post-training → site/track-b/ ---
    if track_b_live:
        html_b = _render_chapter(
            page_tmpl, meta=content_b.META, hero=content_b.HERO, sections=content_b.SECTIONS,
            primer=getattr(content_b, "PYTHON_PRIMER", content.PYTHON_PRIMER), nav=nav_for("track-b"),
            footer_note="Part 2 of the <strong>slm-lab</strong> walk-through.", hub_url=HUB_URL,
        )
        (SITE / "track-b").mkdir(parents=True, exist_ok=True)
        (SITE / "track-b" / "index.html").write_text(html_b)
        written.append(("track-b/index.html", len(html_b), len(content_b.SECTIONS)))

    # --- Landing hub → site/index.html ---
    html_l = landing_tmpl.render(meta=content.LANDING_META, landing=content.LANDING,
                                 track_b_live=track_b_live, concepts_live=concepts_live,
                                 hub_url=HUB_URL, headshot=_asset_uri("jem-headshot.jpg"))
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "index.html").write_text(html_l)
    written.append(("index.html (landing)", len(html_l), 0))

    for name, n, secs in written:
        extra = f", {secs} sections" if secs else ""
        print(f"wrote site/{name}  ({n/1024:.0f} KB{extra})")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
