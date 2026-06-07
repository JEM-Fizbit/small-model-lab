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
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

ROOT = Path(__file__).resolve().parents[2]          # repo root
NB_DIR = ROOT / "notebooks"
OUT = Path(__file__).resolve().parent / "tiny-gpt.html"

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
def main():
    import content  # local import so a syntax error there points cleanly here

    sections = content.SECTIONS
    rendered = []
    for sec in sections:
        body = "\n".join(render_block(b, sec) for b in sec["blocks"])
        rendered.append({**sec, "body": body})

    # Table of contents grouped by "part"
    toc = []
    seen_parts = {}
    for sec in sections:
        part = sec.get("part")
        if part and part not in seen_parts:
            seen_parts[part] = True
            toc.append({"part": part})
        toc.append({"id": sec["id"], "num": sec.get("num", ""), "title": sec["title"]})

    env = Environment(loader=BaseLoader(), autoescape=False)
    tmpl = env.from_string(content.TEMPLATE)
    html = tmpl.render(
        meta=content.META,
        sections=rendered,
        toc=toc,
        pygments_css=_fmt.get_style_defs(".hl"),
        hero=content.HERO,
        primer=content.PYTHON_PRIMER,
    )
    OUT.write_text(html)
    kb = len(html.encode()) / 1024
    print(f"wrote {OUT.relative_to(ROOT)}  ({kb:.0f} KB, {len(sections)} sections)")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
