"""content.py — the hand-authored narrative + page chrome for the tiny-GPT walk-through.

This file holds everything a human wrote: the prose, the Python primer, the HTML/CSS
template, and the section/block structure. The *code* and *outputs* are NOT stored here
— they are pulled live from the notebooks by `build.py` (see the ("code", …) / ("output", …)
block tuples below). That's the "hybrid" split: words here, code from the source of truth.

Block tuple kinds (handled in build.render_block):
  ("prose", html)                         narrative paragraph(s)
  ("code", nb, anchor[, caption])         code cell pulled from notebook `nb` by `anchor`
  ("srccode", filekey[, start, end, cap]) slice of chat.py / tiny_gpt.py
  ("gloss", html)                         "what this says" plain-English explanation box
  ("output", nb, anchor, label[, max])    real cell output, pulled by anchor
  ("rawoutput", text, label)              literal text block (curated excerpt)
  ("figure", filename, caption)           base64-embedded PNG
  ("callout", variant, title, html)       key | tryit | aside | math
  ("table", html)
"""

META = {
    "title": "How a tiny GPT works — a guided walk-through",
    "subtitle": "Building a language model from nothing, on a laptop — explained for the curious.",
}

# ----------------------------------------------------------------------- HERO --
HERO = r"""
<p class="kicker">slm-lab · Track A</p>
<h1>How a tiny GPT works</h1>
<p class="lede">We are going to build a language model from nothing — no pre-trained
weights, no magic — and watch it learn to write. This page walks through the real code
that did it, line by line, for someone who is curious but doesn't necessarily write Python. By the
end you'll understand, concretely, how a model &ldquo;predicts the next word&rdquo; —
and why, strictly, it predicts no such thing.</p>

<div class="bigidea">
  <p><strong>The whole idea:</strong> a GPT is a <strong>model</strong> — really a mathematical
  function with millions of adjustable numbers, its <strong>parameters</strong> — that, given
  some text so far, predicts what comes next. Two algorithms surround it: <em>training</em> tunes
  those parameters, millions of tiny adjustments, until coherent language falls out;
  <em>generation</em> runs the function in a loop to write.</p>
  <p>Everything below is just unpacking that idea: how text becomes numbers, how the
  model &ldquo;looks back&rdquo; at what it has read (<em>attention</em>), how it measures
  its own mistakes, and how it slowly improves.</p>
</div>

<p class="readnote"><strong>How to read this.</strong> Top to bottom, like an essay. Each
step has the plain idea first, then the actual code in a dark box, then a
&ldquo;what this says&rdquo; translation. You can skip the code boxes entirely and still
follow the story — or read them closely and learn to recognise what Python is doing.
A one-page <a href="#primer">Python primer</a> at the end explains the handful of symbols
that recur.</p>
"""

# -------------------------------------------------------------- PYTHON PRIMER --
PYTHON_PRIMER = r"""
<p>You don't need this to follow the walk-through — the &ldquo;what this says&rdquo; boxes
translate everything. But if you want to read the code itself, here are the few patterns
that show up again and again. Learn these six and Python stops looking like noise.</p>

<dl class="primer">
  <dt><code>name = something</code></dt>
  <dd><strong>Assignment.</strong> Give a value a name so you can refer to it later.
  <code>vocab_size = 90</code> means &ldquo;from now on, <code>vocab_size</code> is 90.&rdquo;
  The <code>=</code> is &ldquo;set to,&rdquo; not &ldquo;equals&rdquo; in the maths sense.</dd>

  <dt><code>def do_thing(a, b):</code></dt>
  <dd><strong>Define a function</strong> — a named, reusable recipe. <code>a, b</code> are
  its inputs. Everything indented underneath belongs to it. Later, <code>do_thing(2, 3)</code>
  <em>runs</em> the recipe with those inputs.</dd>

  <dt><code>class GPT:</code></dt>
  <dd><strong>A blueprint</strong> for an object that bundles data and behaviour together.
  The model itself is one of these. <code>__init__</code> is the setup that runs once when
  the object is created; <code>__call__</code> is &ldquo;what happens when you use it like a
  function&rdquo; — so <code>model(x)</code> runs the model on input <code>x</code>.</dd>

  <dt><code>for item in things:</code></dt>
  <dd><strong>A loop.</strong> Do the indented steps once for each item — the engine of
  training (&ldquo;for each step, improve a little&rdquo;) and of generation
  (&ldquo;for each new word, predict one&rdquo;).</dd>

  <dt><code>[ ... ]</code> and indentation</dt>
  <dd>Square brackets make a <strong>list</strong> (an ordered collection). <strong>Indentation
  is meaningful</strong> in Python: the spaces aren't decoration — they show what belongs
  inside a function, loop, or block.</dd>

  <dt><code>x @ y</code> and &ldquo;shapes&rdquo;</dt>
  <dd>The data flowing through the model lives in <strong>arrays</strong> — grids of numbers.
  An array's <strong>shape</strong> is its dimensions, e.g. <code>(B, T, C)</code> =
  (how many examples at once, how many positions in each, how many numbers per position).
  <code>@</code> is <strong>matrix multiplication</strong> — the bulk-arithmetic operation
  that does almost all the work in a neural network. <code>mx</code> is Apple's array
  library (MLX); think &ldquo;the thing that does fast maths on the GPU.&rdquo;</dd>
</dl>
"""

# ---------------------------------------------------------------------- TEMPLATE
TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{{ meta.title }}</title>
<style>
:root{
  --ink:#1c2230; --soft:#5a6373; --faint:#8a93a3; --line:#e4e7ee;
  --bg:#fbfbfd; --panel:#ffffff; --accent:#3253d6; --accent-soft:#eef2ff;
  --key:#0e7a5f; --key-soft:#e7f6f0; --try:#9a5b00; --try-soft:#fbf1e0;
  --math:#5a3aa6; --math-soft:#f1ecfb; --code-bg:#272822;
  --serif:Charter,"Iowan Old Style",Georgia,"Times New Roman",serif;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
  --mono:"SF Mono",ui-monospace,"JetBrains Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--serif);
  font-size:18px;line-height:1.65;-webkit-font-smoothing:antialiased;}

/* hero */
.hero{background:linear-gradient(165deg,#10182f 0%,#202b4d 60%,#2b3a66 100%);
  color:#eaeefb;padding:72px 24px 60px;}
.hero .inner{max-width:760px;margin:0 auto;}
.hero .kicker{font-family:var(--sans);text-transform:uppercase;letter-spacing:.18em;
  font-size:12px;font-weight:600;color:#9fb2e8;margin:0 0 14px;}
.hero h1{font-family:var(--sans);font-weight:700;font-size:46px;line-height:1.08;
  margin:0 0 18px;letter-spacing:-.02em;}
.hero .lede{font-size:20px;line-height:1.6;color:#d4ddf4;margin:0 0 26px;}
.bigidea{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);
  border-radius:14px;padding:20px 24px;margin:26px 0;}
.bigidea p{margin:0 0 10px;font-size:17px;color:#e6ecfb;}
.bigidea p:last-child{margin:0;color:#c2cdee;font-size:16px;}
.hero .readnote{font-size:15px;color:#aebbdd;font-family:var(--sans);line-height:1.6;
  border-top:1px solid rgba(255,255,255,.12);padding-top:20px;margin-top:26px;}
.hero a{color:#a9c0ff;}

/* layout */
.layout{max-width:1140px;margin:0 auto;display:grid;grid-template-columns:248px 1fr;
  gap:48px;padding:48px 24px 80px;}
nav.toc{position:sticky;top:24px;align-self:start;font-family:var(--sans);font-size:14px;
  max-height:calc(100vh - 48px);overflow:auto;}
nav.toc .toctitle{text-transform:uppercase;letter-spacing:.14em;font-size:11px;
  color:var(--faint);font-weight:700;margin:0 0 12px;}
nav.toc a{display:block;color:var(--soft);text-decoration:none;padding:4px 0;
  line-height:1.4;border-left:2px solid transparent;padding-left:12px;margin-left:-14px;}
nav.toc a:hover{color:var(--accent);}
nav.toc .toc-part{font-weight:700;color:var(--ink);margin:18px 0 6px;font-size:12px;
  text-transform:uppercase;letter-spacing:.08em;}
nav.toc .toc-num{color:var(--faint);font-variant-numeric:tabular-nums;
  display:inline-block;min-width:30px;}

main{min-width:0;max-width:760px;}
section{margin:0 0 8px;padding:34px 0 6px;border-top:1px solid var(--line);}
section:first-of-type{border-top:none;padding-top:0;}
.sec-head{display:flex;align-items:baseline;gap:14px;margin:0 0 14px;}
.sec-num{font-family:var(--sans);font-weight:700;font-size:13px;color:#fff;
  background:var(--accent);border-radius:7px;padding:4px 9px;letter-spacing:.02em;
  white-space:nowrap;flex:none;}
.sec-head h2{font-family:var(--sans);font-weight:700;font-size:27px;letter-spacing:-.01em;
  margin:0;line-height:1.15;}
.part-banner{font-family:var(--sans);text-transform:uppercase;letter-spacing:.16em;
  font-size:12px;font-weight:700;color:var(--accent);margin:8px 0 0;}

/* prose */
.prose{margin:0 0 4px;}
.prose p{margin:0 0 18px;}
.prose h3{font-family:var(--sans);font-size:19px;font-weight:700;margin:26px 0 10px;}
.prose strong{font-weight:700;}
.prose em{font-style:italic;}
.prose code,.gloss code,.callout code,td code,.primer code{font-family:var(--mono);
  font-size:.86em;background:#eef0f5;color:#33405e;padding:1px 6px;border-radius:5px;}
.prose a,.gloss a,.callout a{color:var(--accent);text-decoration:none;
  border-bottom:1px solid #c5d0f5;}
.prose a:hover{border-color:var(--accent);}

/* code figures */
.codefig{margin:22px 0;border-radius:12px;overflow:hidden;
  box-shadow:0 2px 10px rgba(20,28,60,.10);border:1px solid #2c2d27;}
.codebar{background:#1f201b;display:flex;align-items:center;gap:7px;padding:9px 14px;}
.codebar .dot{width:11px;height:11px;border-radius:50%;background:#3a3b34;}
.codebar .dot:nth-child(1){background:#ff5f56;}
.codebar .dot:nth-child(2){background:#ffbd2e;}
.codebar .dot:nth-child(3){background:#27c93f;}
.codebar .srcname{margin-left:auto;font-family:var(--mono);font-size:12px;color:#9b9c92;}
.codefig .hl{margin:0;padding:18px 20px;overflow:auto;background:var(--code-bg);
  font-family:var(--mono);font-size:13.5px;line-height:1.55;}
.codefig .hl pre{margin:0;}
.codefig figcaption{font-family:var(--sans);font-size:13px;color:var(--soft);
  background:#fbfbfc;padding:10px 16px;border-top:1px solid var(--line);}

/* gloss box */
.gloss{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);
  border-radius:0 10px 10px 0;padding:16px 20px 6px;margin:18px 0 22px;
  font-size:16.5px;}
.gloss-tag{font-family:var(--sans);text-transform:uppercase;letter-spacing:.12em;
  font-size:10.5px;font-weight:700;color:var(--accent);margin:0 0 8px;}
.gloss p{margin:0 0 12px;}
.gloss ul{margin:0 0 12px;padding-left:22px;}
.gloss li{margin:0 0 7px;}
.gloss b{color:var(--ink);}

/* terminal output */
.term{margin:18px 0 22px;border-radius:10px;overflow:hidden;border:1px solid #d7dbe4;}
.term-tag{font-family:var(--sans);text-transform:uppercase;letter-spacing:.1em;
  font-size:10.5px;font-weight:700;color:var(--soft);background:#eef0f4;
  padding:7px 14px;border-bottom:1px solid #dde1ea;}
.term pre{margin:0;padding:14px 16px;background:#f7f8fb;color:#2a3142;
  font-family:var(--mono);font-size:12.5px;line-height:1.5;overflow:auto;
  white-space:pre-wrap;word-break:break-word;}

/* figures (images) */
.imgfig{margin:24px 0;text-align:center;}
.imgfig img{max-width:100%;border-radius:10px;border:1px solid var(--line);
  box-shadow:0 2px 10px rgba(20,28,60,.08);}
.imgfig figcaption{font-family:var(--sans);font-size:13.5px;color:var(--soft);
  margin-top:10px;}
.diagram{background:#fff;border:1px solid var(--line);border-radius:12px;
  padding:20px 18px 8px;box-shadow:0 2px 10px rgba(20,28,60,.06);}
.diagram svg{max-width:100%;height:auto;display:block;margin:0 auto;}
.diagram text{font-family:var(--sans);}
.diagram figcaption{margin-top:6px;}

/* callouts */
.callout{border-radius:10px;padding:16px 20px;margin:22px 0;font-size:16px;
  font-family:var(--sans);line-height:1.6;}
.callout-title{font-weight:700;font-size:13px;text-transform:uppercase;
  letter-spacing:.08em;margin:0 0 8px;}
.callout-body p{margin:0 0 10px;}
.callout-body p:last-child{margin:0;}
.callout-body ul{margin:6px 0 0;padding-left:20px;}
.callout-body li{margin:0 0 6px;}
.callout.key{background:var(--key-soft);border:1px solid #bfe6d6;}
.callout.key .callout-title{color:var(--key);}
.callout.tryit{background:var(--try-soft);border:1px solid #f0dcb4;}
.callout.tryit .callout-title{color:var(--try);}
.callout.aside{background:#f1f3f8;border:1px solid #dfe3ec;}
.callout.aside .callout-title{color:var(--soft);}
.callout.math{background:var(--math-soft);border:1px solid #d9ccf3;}
.callout.math .callout-title{color:var(--math);}
.callout.math .formula{font-family:var(--mono);font-size:15px;background:#fff;
  border:1px solid #e1d8f5;border-radius:8px;padding:12px 14px;margin:6px 0 12px;
  text-align:center;color:#33285a;overflow:auto;}

/* tables */
.tablewrap{margin:22px 0;overflow:auto;}
table{border-collapse:collapse;width:100%;font-family:var(--sans);font-size:14.5px;}
th,td{text-align:left;padding:10px 13px;border-bottom:1px solid var(--line);
  vertical-align:top;}
th{font-weight:700;color:var(--ink);border-bottom:2px solid #cfd5e2;
  background:#f6f7fb;font-size:13px;text-transform:uppercase;letter-spacing:.04em;}
td:first-child{font-weight:600;}

/* python primer appendix */
dl.primer{margin:18px 0;}
dl.primer dt{font-family:var(--mono);font-size:14px;margin:18px 0 6px;color:#2a3142;}
dl.primer dd{margin:0 0 4px 0;font-size:16.5px;}

footer{border-top:1px solid var(--line);padding:30px 24px 60px;text-align:center;
  font-family:var(--sans);font-size:13.5px;color:var(--faint);line-height:1.6;}
footer p{margin:0 0 8px;} footer p:last-child{margin:0;}
footer code{font-family:var(--mono);background:#eef0f5;padding:1px 6px;border-radius:5px;}
footer a{color:var(--accent);text-decoration:none;border-bottom:1px solid #c5d0f5;}

@media (max-width:920px){
  .layout{grid-template-columns:1fr;gap:0;}
  nav.toc{display:none;}
  .hero h1{font-size:36px;}
  body{font-size:17px;}
}
{{ pygments_css }}
</style>
</head>
<body>

<header class="hero"><div class="inner">{{ hero }}</div></header>

<div class="layout">
  <nav class="toc">
    <p class="toctitle">Contents</p>
    {% for t in toc %}
      {% if t.part %}<div class="toc-part">{{ t.part }}</div>
      {% else %}<a href="#{{ t.id }}"><span class="toc-num">{{ t.num }}</span>{{ t.title }}</a>{% endif %}
    {% endfor %}
    <div class="toc-part">Reference</div>
    <a href="#primer"><span class="toc-num">↪</span>Python primer</a>
  </nav>

  <main>
    {% for sec in sections %}
    <section id="{{ sec.id }}">
      {% if sec.part_banner %}<p class="part-banner">{{ sec.part_banner }}</p>{% endif %}
      <div class="sec-head">
        {% if sec.num %}<span class="sec-num">{{ sec.num }}</span>{% endif %}
        <h2>{{ sec.title }}</h2>
      </div>
      {{ sec.body }}
    </section>
    {% endfor %}

    <section id="primer">
      <div class="sec-head"><span class="sec-num">↪</span><h2>Python primer</h2></div>
      <div class="prose">{{ primer }}</div>
    </section>
  </main>
</div>

<footer>
  <p>Generated from the live notebooks by <code>build.py</code> — every code block and output above
  is pulled straight from the Jupyter notebooks, so what you read is what actually ran.</p>
  <p>Open source:
  <a href="https://github.com/JEM-Fizbit/slm-lab">github.com/JEM-Fizbit/slm-lab</a>
  &nbsp;·&nbsp; notebooks
  <a href="https://github.com/JEM-Fizbit/slm-lab/blob/main/notebooks/01_tiny_gpt_from_scratch.ipynb">01</a>,
  <a href="https://github.com/JEM-Fizbit/slm-lab/blob/main/notebooks/02_tiny_gpt_tuned.ipynb">02</a>,
  <a href="https://github.com/JEM-Fizbit/slm-lab/blob/main/notebooks/03_tiny_gpt_chat.ipynb">03</a>
  &nbsp;·&nbsp; Part of <strong>slm-lab</strong>, Track A.</p>
  <p><a href="https://github.com/JEM-Fizbit/slm-lab/blob/main/LICENSE">MIT-licensed</a> © 2026
  John E. Milad. Builds on <a href="https://github.com/karpathy/nanoGPT">nanoGPT</a> (Karpathy),
  <a href="https://github.com/ml-explore/mlx">Apple MLX</a>, and the
  <a href="https://huggingface.co/datasets/roneneldan/TinyStories">TinyStories</a> dataset
  (Eldan &amp; Li, Microsoft Research).</p>
</footer>

</body>
</html>
"""

# ---------------------------------------------------------------- DIAGRAMS --
# Hand-drawn inline SVG (no JS, no external assets — keeps the single-file build).

LANDSCAPE_SVG = r'''<svg viewBox="0 0 640 300" role="img" aria-label="A loss landscape shaped like a valley. A ball sits partway up the left slope, with an arrow showing one step downhill toward the point of lowest loss.">
<defs><marker id="arL" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#1c2230"/></marker></defs>
<line x1="62" y1="28" x2="62" y2="272" stroke="#c7cdda" stroke-width="1.5"/>
<line x1="62" y1="272" x2="612" y2="272" stroke="#c7cdda" stroke-width="1.5"/>
<text x="50" y="42" text-anchor="end" font-size="12" fill="#8a93a3">high</text>
<text x="26" y="150" text-anchor="middle" font-size="13" fill="#5a6373" transform="rotate(-90 26 150)">loss (how wrong)</text>
<text x="337" y="294" text-anchor="middle" font-size="13" fill="#5a6373">a single weight (one of millions)</text>
<path d="M 90 70 Q 335 400 580 70" fill="none" stroke="#3253d6" stroke-width="3"/>
<line x1="335" y1="235" x2="335" y2="272" stroke="#0e7a5f" stroke-width="1.5" stroke-dasharray="4 4"/>
<circle cx="335" cy="235" r="4.5" fill="#0e7a5f"/>
<text x="346" y="231" font-size="12" fill="#0e7a5f">lowest loss</text>
<circle cx="188" cy="176" r="11" fill="#e8462e" stroke="#fff" stroke-width="2.5"/>
<text x="126" y="150" text-anchor="middle" font-size="12" fill="#1c2230">current</text>
<text x="126" y="165" text-anchor="middle" font-size="12" fill="#1c2230">weights</text>
<line x1="201" y1="186" x2="258" y2="210" stroke="#1c2230" stroke-width="2" marker-end="url(#arL)"/>
<text x="300" y="200" font-size="12" fill="#1c2230">one step downhill</text>
</svg>'''

CYCLE_SVG = r'''<svg viewBox="0 0 760 250" role="img" aria-label="The training cycle as a loop of four boxes: forward pass, then loss, then backward pass, then update, then back to the start.">
<defs><marker id="arC" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#3253d6"/></marker></defs>
<rect x="15" y="40" width="160" height="80" rx="12" fill="#eef2ff" stroke="#3253d6" stroke-width="1.5"/>
<text x="95" y="68" text-anchor="middle" font-size="13.5" font-weight="700" fill="#1c2230">① Forward pass</text>
<text x="95" y="88" text-anchor="middle" font-size="11" fill="#5a6373">run data → predictions</text>
<text x="95" y="106" text-anchor="middle" font-size="11" fill="#3253d6" font-family="ui-monospace,Menlo,monospace">model(x)</text>
<rect x="205" y="40" width="160" height="80" rx="12" fill="#eef2ff" stroke="#3253d6" stroke-width="1.5"/>
<text x="285" y="68" text-anchor="middle" font-size="13.5" font-weight="700" fill="#1c2230">② Loss</text>
<text x="285" y="88" text-anchor="middle" font-size="11" fill="#5a6373">how wrong is it?</text>
<text x="285" y="106" text-anchor="middle" font-size="11" fill="#3253d6" font-family="ui-monospace,Menlo,monospace">cross_entropy</text>
<rect x="395" y="40" width="160" height="80" rx="12" fill="#eef2ff" stroke="#3253d6" stroke-width="1.5"/>
<text x="475" y="68" text-anchor="middle" font-size="13.5" font-weight="700" fill="#1c2230">③ Backward pass</text>
<text x="475" y="88" text-anchor="middle" font-size="11" fill="#5a6373">which way is downhill</text>
<text x="475" y="106" text-anchor="middle" font-size="11" fill="#3253d6" font-family="ui-monospace,Menlo,monospace">loss_and_grad</text>
<rect x="585" y="40" width="160" height="80" rx="12" fill="#eef2ff" stroke="#3253d6" stroke-width="1.5"/>
<text x="665" y="68" text-anchor="middle" font-size="13.5" font-weight="700" fill="#1c2230">④ Update</text>
<text x="665" y="88" text-anchor="middle" font-size="11" fill="#5a6373">one step downhill</text>
<text x="665" y="106" text-anchor="middle" font-size="11" fill="#3253d6" font-family="ui-monospace,Menlo,monospace">optimizer.update</text>
<line x1="175" y1="80" x2="203" y2="80" stroke="#3253d6" stroke-width="2" marker-end="url(#arC)"/>
<line x1="365" y1="80" x2="393" y2="80" stroke="#3253d6" stroke-width="2" marker-end="url(#arC)"/>
<line x1="555" y1="80" x2="583" y2="80" stroke="#3253d6" stroke-width="2" marker-end="url(#arC)"/>
<path d="M 665 120 L 665 180 L 95 180 L 95 120" fill="none" stroke="#3253d6" stroke-width="2" stroke-dasharray="5 4" marker-end="url(#arC)"/>
<text x="380" y="173" text-anchor="middle" font-size="12.5" fill="#3253d6">repeat ~2,500 times</text>
</svg>'''

# ===========================================================================
#  SECTIONS — the walk-through itself
# ===========================================================================

SECTIONS = [

# ---------------------------------------------------------------- ORIENTATION --
{
 "id": "what", "num": "0", "title": "What we're actually building",
 "part": "Orientation",
 "part_banner": "Part I · Orientation",
 "blocks": [
  ("prose", r"""
<p>A &ldquo;GPT&rdquo; — the architecture behind ChatGPT, Claude, and the rest — is at
heart a <strong>next-token predictor</strong>. Show it some text and it produces, for every
possible next chunk of text, a probability: <em>how likely is this to come next?</em> To
generate, you sample one chunk from those probabilities, glue it on, and ask again. Do that
in a loop and the model writes.</p>
<p>That phrasing — &ldquo;chunk of text,&rdquo; not &ldquo;word&rdquo; — is deliberate. The
popular line &ldquo;predicts the next word&rdquo; is shorthand: a model predicts the next
<em>unit</em> of however we chose to slice text up, and that choice is ours to make. Notebook 01
slices text into single <strong>characters</strong>, so it literally predicts the next letter.
Notebook 02 slices it into <strong>tokens</strong> — frequent fragments like <code>" the"</code>
or <code>"ing"</code>, usually a few characters each — so it predicts the next fragment. A whole
word is then just one or a few of these in a row. The loop is identical either way — predict the
next unit, append it, ask again — only the <em>grain</em> changes.</p>
<p>That's the entire trick. The sophistication of a real model isn't a different idea — it's
the <em>same</em> idea at enormous scale: more data, more parameters, more compute. So if we
build a <em>tiny</em> one and understand every part, we've understood the shape of the whole
field. That is exactly what Track A of this lab does, in two passes:</p>
"""),
  ("table", r"""
<table>
<thead><tr><th>Pass</th><th>What it does</th><th>Result</th></tr></thead>
<tbody>
<tr><td>Notebook 01 — <em>from scratch</em></td>
    <td>The simplest possible GPT, working one <strong>character</strong> at a time, built
    from raw parts so every moving piece is visible.</td>
    <td>English-shaped <strong>gibberish</strong>, on purpose. The goal is transparency, not quality.</td></tr>
<tr><td>Notebook 02 — <em>tuned</em></td>
    <td>Same architecture, plus the handful of upgrades that genuinely move quality
    (chiefly: working in word-chunks, not letters).</td>
    <td>Recognisable <strong>little stories</strong> — the ceiling of a from-scratch model on a laptop.</td></tr>
</tbody></table>
"""),
  ("callout", "key", "Why two passes", r"""
<p>The jump from gibberish to coherent stories — same architecture, a few changes — is the
most instructive thing in the project. It separates <em>knowing the parts</em> from
<em>knowing what matters</em>. We'll build the parts in Part II and turn the dials in Part III.</p>
"""),
  ("callout", "aside", "A note on hardware", r"""
<p>All of this runs locally on an Apple-silicon Mac using <strong>MLX</strong>, Apple's
numerical library (the local equivalent of PyTorch). When you see <code>mx</code> in the code,
that's MLX doing fast maths on the GPU. Nothing here calls the cloud except a one-time dataset
download.</p>
"""),
 ],
},

# ============================ PART II — FROM SCRATCH ========================
{
 "id": "setup", "num": "1", "title": "Setup: the toolbox",
 "part": "Building it from scratch",
 "part_banner": "Part II · Building it from scratch (notebook 01)",
 "blocks": [
  ("prose", r"""
<p>Every program starts by laying its tools on the bench. Here we load the array library, the
neural-network building blocks, and the optimizer (the part that will adjust the model as it
learns). One line prints the compute device — confirmation that the Mac's GPU is in play.</p>
"""),
  ("code", "01", "MLX device:"),
  ("gloss", r"""
<p><b>Reading it:</b> the <code>import</code> lines bring in pre-written toolkits.
<code>np</code> is <strong>NumPy</strong> — Python's classic, decades-old library for arrays of
numbers, the workhorse under most of scientific computing (here it does a little data prep on the
CPU). <code>mx</code> is <strong>MLX</strong>, Apple's array library that runs on the Mac's GPU;
it's deliberately NumPy-like, so the two look almost identical in use. <code>nn</code> holds the
neural-net building blocks (layers and such), and <code>optim</code> is the optimizer — the part
that adjusts the model as it learns. The last line prints which device will run the maths; on an
M-series Mac it reports the GPU.</p>
"""),
 ],
},

{
 "id": "data", "num": "2", "title": "Turning text into numbers",
 "blocks": [
  ("prose", r"""
<p>A model can't read letters; it does arithmetic. So the very first job is
<strong>tokenisation</strong> — a fixed dictionary that maps text to whole numbers and back.
Notebook 01 uses the simplest scheme imaginable: <strong>one number per character</strong>.
Every distinct character it sees — every letter, space, comma — gets its own id. It's
inefficient, but maximally transparent: you can see <em>exactly</em> what the model sees.</p>
<p>The text itself is <strong>TinyStories</strong>: thousands of very simple children's
stories, written with a small vocabulary on purpose, so that a small model can actually learn
coherent English from them.</p>
"""),
  ("code", "01", "N_STORIES = 4000", "Stream a few thousand stories (no full download)."),
  ("gloss", r"""
<p><b>Reading it:</b> <code>N_STORIES = 4000</code> sets how many stories to grab. The
<code>try:</code> / <code>except:</code> pair is a safety net — &ldquo;<em>attempt</em> this;
if anything goes wrong, do that instead&rdquo; — so the notebook never hard-fails if you happen
to be offline.</p>
<ul>
<li><code>load_dataset(..., streaming=True)</code> — open the TinyStories dataset as a
<b>stream</b>: pull stories one at a time on demand, rather than downloading the whole thing.</li>
<li>the <code>for ... in ds:</code> loop — walk through the stream, tidy each story
(<code>.strip()</code> trims stray whitespace) and add it to a growing <code>stories</code> list.
<code>if len(stories) >= N_STORIES: break</code> means &ldquo;once we have 4,000, stop.&rdquo;</li>
<li><code>text = "\n\n".join(stories)</code> — glue all the stories into one big string, with a
blank line between each. That single string is the raw material everything downstream learns from.</li>
<li>the <code>except</code> branch — only runs if the download failed; it swaps in a tiny
built-in corpus so the rest of the notebook still works.</li>
</ul>
"""),
  ("output", "01", "N_STORIES = 4000", "what it prints", 600),
  ("prose", r"""
<p>Now we build the dictionary and convert the entire corpus into one long ribbon of integers.
The last 10% is held back as a <strong>validation set</strong> — text the model never trains
on — which later lets us tell genuine learning apart from mere memorising.</p>
"""),
  ("code", "01", "chars = sorted(set(text))"),
  ("gloss", r"""
<p><b>Line by line:</b></p>
<ul>
<li><code>chars = sorted(set(text))</code> — find every <em>distinct</em> character and put
them in a fixed order. That ordered list <em>is</em> the vocabulary.</li>
<li><code>stoi</code> / <code>itos</code> — two lookup tables: <b>s</b>tring-<b>to</b>-<b>i</b>nteger
and back. (&ldquo;<code>a</code> is 27,&rdquo; &ldquo;27 is <code>a</code>.&rdquo;)</li>
<li><code>encode</code> / <code>decode</code> — small recipes that run those lookups over a
whole string. Encode turns text into numbers; decode turns numbers back into text.</li>
<li><code>train_data, val_data</code> — split the encoded ribbon 90/10. The model studies the
first part and is tested on the held-out tail.</li>
</ul>
"""),
  ("output", "01", "chars = sorted(set(text))", "what it prints"),
  ("callout", "key", "The key idea", r"""
<p>From here on, the model lives entirely in the world of integers. &ldquo;Understanding
language&rdquo; will turn out to mean &ldquo;getting good at predicting the next integer in the
ribbon.&rdquo; Tokenisation is the bridge between our world and its.</p>
"""),
 ],
},

{
 "id": "batch", "num": "3", "title": "The task: predict the next character",
 "blocks": [
  ("prose", r"""
<p>How do you turn &ldquo;a long ribbon of numbers&rdquo; into a <em>learning task</em>? You
slice out short windows and set up a fill-in-the-blank exercise. For each window of text
<code>x</code>, the correct answer <code>y</code> is <em>the same window shifted one step to
the right</em>. So at every single position, the model's job is: &ldquo;given everything up to
here, what's the next character?&rdquo; One window quietly contains hundreds of these little
quizzes at once.</p>
"""),
  ("code", "01", "def get_batch", "Grab a stack of random windows; the target is shifted by one."),
  ("gloss", r"""
<p><b>In plain terms:</b> pick <code>batch_size</code> random starting points in the data.
For each, take a window of <code>block_size</code> characters as the input <code>x</code>, and
the <em>same window slid one place forward</em> as the answer <code>y</code>. Stacking many
windows together (a &ldquo;batch&rdquo;) lets the GPU practise on all of them simultaneously —
that's what makes training fast.</p>
"""),
  ("callout", "aside", "Why &ldquo;shifted by one&rdquo; is clever", r"""
<p>It means we never have to label data by hand. The text <em>is</em> its own answer key:
the next character is always sitting right there. This is why language models can train on raw
text from the internet — the supervision is free.</p>
"""),
 ],
},

{
 "id": "knobs", "num": "4", "title": "The dials (hyperparameters)",
 "blocks": [
  ("prose", r"""
<p>Before building the model we choose its size and how hard it will train. These are
<strong>hyperparameters</strong> — settings <em>we</em> pick, as opposed to the millions of
numbers the model will learn on its own. A founding principle of this lab is &ldquo;no magic
numbers,&rdquo; so each one carries a note on what it does and which way to push it.</p>
"""),
  ("code", "01", "block_size = 128"),
  ("gloss", r"""
<p>The four shape dials decide capacity: <code>block_size</code> is how far back the model can
see; <code>n_embd</code> is how many numbers describe each token: that list of numbers is the
token's <strong>vector</strong> — a vector being simply an ordered list of numbers, e.g.
<code>[0.31, -1.20, 0.05, …]</code> — and <code>n_embd</code> (256) is how long it is (the
token's &ldquo;richness&rdquo;); <code>n_head</code> is how many relationships attention tracks
in parallel; <code>n_layer</code>
is how many times the whole reasoning block is stacked (depth). The training dials —
<code>batch_size</code>, <code>learning_rate</code>, <code>max_steps</code> — decide how
steadily and how long it learns. Bigger or longer is generally better and always slower; the
art is the balance.</p>
"""),
 ],
},

{
 "id": "attention", "num": "5", "title": "Attention — the heart of it",
 "blocks": [
  ("prose", r"""
<p>This is the one idea that makes a transformer a transformer. Everything else is plumbing.</p>
<p><strong>The intuition.</strong> To predict the next word, a position needs to pull in
relevant context from earlier words — but <em>which</em> earlier words matters, and it depends
on the sentence. In &ldquo;the dragon looked at the boy and <u>it</u>…&rdquo;, the word
&ldquo;it&rdquo; should pay attention to &ldquo;dragon.&rdquo; <strong>Attention</strong> is
the mechanism that lets every position decide, on the fly, how much to listen to each earlier
position.</p>
<p>The standard analogy is a <em>search</em>. Each token emits three things:</p>
<ul>
<li>a <strong>query</strong> — &ldquo;here's what I'm looking for,&rdquo;</li>
<li>a <strong>key</strong> — &ldquo;here's what I'm about,&rdquo; and</li>
<li>a <strong>value</strong> — &ldquo;here's what I'll hand over if you attend to me.&rdquo;</li>
</ul>
<p>A token compares its query against every earlier token's key. Good matches get high
attention; the token then takes a weighted blend of those tokens' values. Strong match → big
say in the blend. That blend is how information moves between positions.</p>
"""),
  ("callout", "key", "Causal = no peeking", r"""
<p>When predicting the next character, a token may only look <em>backward</em>. If it could see
the future, the &ldquo;guess the next character&rdquo; game would be trivial — it would just
read the answer. We enforce this with a <strong>mask</strong> that blocks every forward-looking
connection. This is what the &ldquo;causal&rdquo; in <em>causal self-attention</em> means.</p>
"""),
  ("code", "01", "def causal_mask(T):", "The mask, then attention itself."),
  ("gloss", r"""
<p><b>The mask</b> (<code>causal_mask</code>) builds a grid where allowed (past) connections
are 0 and forbidden (future) ones are a huge negative number. Added to the raw scores, those
−1,000,000,000 entries become effectively zero probability after the next step — future tokens
are silenced.</p>
<p><b>Inside the attention</b> (<code>__call__</code>), reading the important lines:</p>
<ul>
<li><code>q, k, v = mx.split(self.c_attn(x), 3, …)</code> — one matrix multiply produces all
three vectors (query, key, value) for every token at once, then splits them apart.</li>
<li>the <code>reshape</code>/<code>transpose</code> lines — split the work across several
attention <em>heads</em>, so the model can track multiple kinds of relationship in parallel
(one head might follow grammar, another who-did-what).</li>
<li><code>scores = q @ transpose(k) … + mask</code> — compare every query against every key
(that's the match score), scale for stability, and add the mask to block the future.</li>
<li><code>weights = mx.softmax(scores)</code> — turn raw scores into clean percentages that sum
to 100% across the allowed past.</li>
<li><code>out = weights @ v</code> — the weighted blend of values. <em>This single line is
where information actually flows between positions.</em></li>
</ul>
"""),
  ("callout", "math", "For the curious — the actual formula", r"""
<p>Everything above is one compact equation. For queries <code>Q</code>, keys <code>K</code>,
and values <code>V</code>:</p>
<div class="formula">Attention(Q, K, V) = softmax( (Q · Kᵀ) / √d + mask ) · V</div>
<p><code>Q · Kᵀ</code> scores every query against every key. Dividing by <code>√d</code> (the
square root of the head size) keeps those scores from growing too large as the model widens.
<code>softmax</code> normalises each row into probabilities; the <code>mask</code> adds −∞ to
future positions so they vanish. Multiplying by <code>V</code> blends the values by those
probabilities. The code above implements exactly this — plus the bookkeeping to run several
attention heads in parallel.</p>
"""),
 ],
},

{
 "id": "block", "num": "6", "title": "The block, and the whole model",
 "blocks": [
  ("prose", r"""
<p>Attention gathers information across positions. The other half of a transformer block is a
small <strong>MLP</strong> — two linear layers with a nonlinear &ldquo;bend&rdquo; (a GELU
activation) between them, applied to each position on its own, giving the model room to
&ldquo;think&rdquo; about what attention just collected. A <strong>block</strong> is simply:
attention, then MLP. A GPT is just this block stacked <code>n_layer</code> times.</p>
<p>Two supporting tricks make deep stacks trainable, and they're worth naming because they're
everywhere in modern models:</p>
<ul>
<li><strong>Residual connections</strong> — <code>x = x + sublayer(x)</code>. Instead of
replacing its input, each sub-layer <em>adds an adjustment</em> to it. This keeps a clean
signal flowing through even a deep stack, which is what makes deep networks learnable at all.</li>
<li><strong>LayerNorm</strong> — a normalisation step that keeps the numbers in a sane range so
the maths stays stable.</li>
</ul>
"""),
  ("callout", "key", "Zoom out — the two operations a neural network is built from", r"""
<p>Step back from the details and almost the entire network is just <em>two</em> operations,
repeated:</p>
<ul>
<li><b>The linear layer — <code>y = Wx + b</code>.</b> The input <code>x</code> is a
<em>vector</em> — one token's list of numbers (256 of them here). The layer produces a new vector,
computing <em>each output on its own</em> as a weighted sum of <em>all</em> the inputs, plus a
single bias:
<div class="formula">out₁ = w₁,₁·x₁ + w₁,₂·x₂ + … + w₁,ₙ·xₙ + b₁ &nbsp;&nbsp;(one line like this per output)</div>
Stack those rows of weights into a grid <code>W</code> and the per-output biases into a vector
<code>b</code>, and the whole layer is <code>y = Wx + b</code> — the line <code>y = mx + c</code>
from school, vectorised. So <code>b</code> is a <em>vector</em> (one bias per output, not a single
number), and the <code>W</code>s vastly outnumber the <code>b</code>s. Almost every named box in
the code is one of these — <code>c_attn</code>, <code>c_proj</code>, both MLP layers, the final
<code>head</code> — each an <code>nn.Linear</code>, which simply <em>computes</em>
<code>Wx + b</code>. <em>(The code does this to a whole array of tokens at once, but the operation
is exactly this, per token.)</em></li>
<li><b>The activation — a bend.</b> After a linear step the model applies one simple nonlinear
function. Without it, stacking linear layers would collapse into a single bigger linear layer, and
the whole network could only ever draw <em>straight lines</em>. The bend is what lets depth model
curves. Ours is <b>GELU</b> (a smooth version of ReLU); the famous textbook activations are
<b>ReLU</b> (keep positives, zero the rest) and the <b>sigmoid</b> (squash any number into 0–1).</li>
</ul>
<p>That's the whole kit: <code>Wx + b</code>, then a bend, stacked — plus <em>attention</em> to
move information between positions, an <em>embedding</em> to turn tokens into vectors at the
bottom, and the <em>head</em> to read predictions out at the top. Every <code>W</code> and
<code>b</code> across all of those is a <b>parameter</b> — and &ldquo;training&rdquo; (next
section) is nothing more than nudging those millions of numbers downhill.</p>
"""),
  ("code", "01", "class Block(nn.Module):", "One block, then the full GPT assembled from blocks."),
  ("gloss", r"""
<p><b>The block</b> is the two-line heart: <code>x = x + self.attn(self.ln1(x), mask)</code>
(normalise, attend, add back) then <code>x = x + self.mlp(self.ln2(x))</code> (normalise,
think, add back). That &ldquo;add back&rdquo; is the residual connection.</p>
<p><b>The full GPT</b> wires the ends on:</p>
<ul>
<li><code>self.tok</code> — an <b>embedding</b> table turning each token id into a vector of
<code>n_embd</code> learnable numbers (its meaning, to be discovered during training).</li>
<li><code>self.pos</code> — a second embedding for <em>position</em>, because attention has no
built-in sense of order; we must tell it where each token sits.</li>
<li><code>self.blocks</code> — the stack of transformer blocks, run in sequence.</li>
<li><code>self.head</code> — a final layer that turns each position's vector into a
<strong>score for every possible next character</strong>. Those scores are called
<em>logits</em>; they're the model's raw opinion about what comes next.</li>
</ul>
<p>The print line counts the model's learnable numbers — its <strong>parameters</strong>. This
tiny one has about 3.2 million. (Frontier models have hundreds of <em>billions</em> — same
parts, more of them.)</p>
<p>Running an input all the way through these layers to produce the logits — that whole
left-to-right journey, <code>model(idx)</code> — is the model's <strong>forward pass</strong>
(&ldquo;forward propagation&rdquo;). Right now it produces nonsense, because the weights are
random. The next section is about fixing that — and the forward pass becomes step one of the
loop that does it.</p>
"""),
  ("output", "01", "class Block(nn.Module):", "what it prints"),
  ("prose", r"""
<h3>Our model, by the numbers</h3>
<p>So how big is the thing we just built? (&ldquo;How many neurons?&rdquo; has no clean answer for
a transformer — the honest measures are its <em>width</em>, its <em>depth</em>, and its
<em>parameter count</em>.)</p>
"""),
  ("table", r"""
<table>
<thead><tr><th>Property</th><th>Notebook 01 (this model)</th></tr></thead>
<tbody>
<tr><td>Transformer blocks — the depth (<code>n_layer</code>)</td><td>4</td></tr>
<tr><td>Width — numbers describing each token (<code>n_embd</code>)</td><td>256</td></tr>
<tr><td>Attention heads (<code>n_head</code>)</td><td>8</td></tr>
<tr><td>MLP hidden units per block (4 × width)</td><td>1,024</td></tr>
<tr><td><b>Total learnable parameters</b> (every <code>W</code> and <code>b</code>)</td><td><b>≈ 3.24 million</b></td></tr>
</tbody></table>
"""),
  ("prose", r"""
<p>Where do those 3.24 million <strong>parameters</strong> live? Almost all — ~3.16 million — are
in the four blocks' <code>Wx + b</code> layers; only ~56k in the two embedding tables and ~24k in
the output head. (Notebook 02 scales every row up — 6 blocks, width 384, ≈17 million — and that
extra capacity is much of what makes its writing better.)</p>
<p>Two things about that number. First, <strong>it <em>is</em> the model's &ldquo;size&rdquo;</strong>
— the same count meant by &ldquo;a 7-billion-parameter model&rdquo; (distinct from the file size on
disk, which is roughly the count × a few bytes per number). Second, <strong>who picks those millions
of values? Not us.</strong> We choose the architecture and the count, and start them as small random
numbers; <em>training</em> then sets every value by gradient descent, nudging each toward whatever
lowers the loss. So the <em>process</em> is no black box — it's the loop in the next section. What
stays opaque is what any <em>single</em> parameter <em>means</em>: the knowledge is smeared across
all of them, not stored in readable slots. We know precisely how they're set; we mostly can't read
them — which is the open research field of <strong>interpretability</strong>.</p>
"""),
 ],
},

{
 "id": "train", "num": "7", "title": "Training: making the guesses less wrong",
 "blocks": [
  ("prose", r"""
<p>A freshly built model is random — its parameters are noise, and its guesses are no better
than chance. <strong>Training</strong> is the loop that fixes that. It needs two things: a way
to <em>measure</em> how wrong a guess is, and a way to <em>nudge</em> every parameter to be a
little less wrong next time.</p>
<p><strong>Measuring wrongness — the loss.</strong> We use <em>cross-entropy</em>, which you
can read as <strong>surprise</strong>: how shocked was the model by the character that actually
came next? If it put high probability on the right character, surprise (loss) is low. A model
that knows nothing and guesses uniformly across a vocabulary of size <em>V</em> has a loss of
about <code>ln(V)</code> — a baseline we can check against.</p>
<p><strong>Using the loss — gradient descent.</strong> Knowing how wrong the model is only
helps if we can act on it. Picture every one of the model's millions of numbers as a dial, and
the loss as the <em>altitude</em> of a vast, foggy landscape: most dial settings sit high up
(bad), the best sit in a valley (low loss). We want the valley. We can't see the whole
landscape — but standing at our current spot we <em>can</em> feel which way is downhill. That
direction is the <strong>gradient</strong>. Take a small step that way, refeel, step again.
That repeated downhill shuffle is <strong>gradient descent</strong>, and the size of each step
is the <code>learning_rate</code>.</p>
"""),
  ("diagram", LANDSCAPE_SVG,
   "Gradient descent: the loss is the height of the landscape. The gradient says which way is "
   "downhill; the learning rate is how big a step you take. One weight is shown — the real model "
   "descends in millions of dimensions at once."),
  ("code", "01", "optimizer = optim.AdamW(learning_rate=learning_rate)",
   "The loss function, then the training loop."),
  ("gloss", r"""
<p><b>The loop is four steps — and every one is a line of code</b> (the
<code>for step in range(...)</code> block, plus the <code>loss_fn</code> above it):</p>
<ol>
<li><b>Forward pass</b> — <code>logits = model(x)</code> (inside <code>loss_fn</code>). Run the
batch of windows through the network to get its predictions. This is the same forward pass you
met when we built the model.</li>
<li><b>Loss</b> — <code>cross_entropy(...)</code>. Score how wrong those predictions are — the
surprise, one number.</li>
<li><b>Backward pass</b> — <code>loss, grads = loss_and_grad(model, x, y)</code>. Work backwards
through the network to get the <b>gradient</b> for every parameter: which way to nudge each one
to lower the loss. Doing this efficiently, end to end, is <b>backpropagation</b> — the central
algorithm of deep learning. (One call returns both the loss and all the gradients.)</li>
<li><b>Gradient-descent step</b> — <code>optimizer.update(model, grads)</code>. Take one small
step downhill — every parameter at once. The step size is the <code>learning_rate</code>.</li>
</ol>
<p><code>mx.eval(...)</code> just tells the GPU to actually run all of that now (MLX is lazy by
default). Repeat a couple of thousand times: each pass the model is microscopically less wrong,
and in aggregate, language emerges.</p>
"""),
  ("diagram", CYCLE_SVG,
   "One trip round the loop. The forward pass and loss measure how wrong the model is; the "
   "backward pass and update make it a little less wrong. Then it all repeats."),
  ("output", "01", "optimizer = optim.AdamW(learning_rate=learning_rate)",
   "watching it learn (loss falling)"),
  ("prose", r"""
<p>Read that output top to bottom: the loss starts near the &ldquo;knows nothing&rdquo;
baseline (~4.5) and falls fast to ~2.3 as the model picks up the statistics of English. The
<strong>validation</strong> loss falls alongside the training loss — proof it's learning the
<em>language</em>, not just memorising these particular stories.</p>
"""),
  ("callout", "math", "For the curious — what a gradient is, exactly", r"""
<p>A <strong>gradient</strong> is just a slope: the derivative of the loss with respect to one
parameter — how much the loss would change if you nudged that parameter a hair. Collect one for
every parameter and you have the direction of steepest <em>increase</em> in loss; descent steps
the opposite way:</p>
<div class="formula">parameter ← parameter − learning_rate × gradient</div>
<p>Computing <em>all</em> of them — one <code>∂loss/∂parameter</code> per parameter — is what the
<strong>backward pass</strong> does, by applying the <strong>chain rule</strong> backward through
the network (each layer's derivative feeding the one before it). That reuse is why
<strong>backpropagation</strong> gets every derivative in roughly the cost of one extra forward
pass, instead of re-running the whole model once per parameter.</p>
<p>The loss itself, cross-entropy, is <code>−log(probability the model gave the correct
token)</code> — zero when the model is confident and right, large when it's confident and wrong.
And <code>AdamW</code>, our optimizer, is a refined gradient descent: it keeps a little momentum
and adapts the step size per parameter — but the line above is the heart of it.</p>
"""),
 ],
},

{
 "id": "curve", "num": "8", "title": "The loss curve — the single most important plot",
 "blocks": [
  ("prose", r"""
<p>This plot has a name: the <strong>loss curve</strong> (sometimes <em>learning curve</em>). It
is the loss from the last section, tracked across the whole training run — so don't confuse it
with the loss <em>function</em>: the <em>function</em> is the formula that scores a single batch;
the <em>curve</em> is that score plotted step after step. Reading it is how every practitioner
judges the health of a run at a glance. The <strong style="color:#2f74c0">blue</strong> line is
the training loss; the <strong style="color:#d9772b">orange</strong> line (with dots) is the
validation loss; the grey dashed line is the &ldquo;knows nothing&rdquo; baseline.</p>
"""),
  ("figure", "loss_curve.png", "Notebook 01: both losses falling together toward the floor for a model this size."),
  ("gloss", r"""
<p><b>How to read it:</b> a healthy run drops fast, then flattens. The crucial signal is the
gap between the two lines. While validation loss keeps falling, the model is genuinely
<b>learning</b>. If validation loss ever turned <em>upward</em> while training loss kept
dropping, that widening gap would be <b>overfitting</b> — the model memorising its study
material instead of learning the general pattern. Here both fall together: no overfitting, just
the natural floor for a model this small.</p>
"""),
 ],
},

{
 "id": "generate", "num": "9", "title": "Generating text — and the honest result",
 "blocks": [
  ("prose", r"""
<p>Now we let it write. Generation is a loop: feed in a prompt, look at the model's scores for
the <em>next</em> character, turn them into probabilities, and <strong>sample</strong> one.
Append it, then feed the whole thing back in and repeat. This one-step-at-a-time process is
called <strong>autoregressive</strong> generation — and it's exactly how the largest models
write too.</p>
"""),
  ("code", "01", "def generate(prompt, n_new=400", "Predict one character, append, repeat."),
  ("gloss", r"""
<p><b>Step by step:</b> encode the prompt to numbers, then loop <code>n_new</code> times. Each
pass takes the scores for the last position, divides by <code>temperature</code> (more on that
in Part IV), and <code>mx.random.categorical</code> rolls a weighted die to pick the next
character — likelier characters chosen more often, but not always. Glue it on and continue.</p>
"""),
  ("callout", "aside", "Generation vs. inference — which is which", r"""
<p>Each pass through this loop is one step of <strong>inference</strong> — a single forward run
of the model to get the next-token scores. &ldquo;Inference&rdquo; is the umbrella term for
<em>using</em> a trained model (any forward pass), as opposed to <em>training</em> it. Wrapping
inference in this sample-and-append loop, to emit a whole sequence, is what we call
<strong>generation</strong> (or <em>decoding</em>). So generation isn't a different thing from
inference — it's inference run autoregressively, one token at a time.</p>
"""),
  ("output", "01", "def generate(prompt, n_new=400", "what a from-scratch char-level model writes"),
  ("callout", "key", "This gibberish is the point", r"""
<p>It looks like English — real spacing, plausible letter runs, the ghost of words — but it's
nonsense. That is the <em>correct</em> outcome for a 3-million-parameter model that works one
letter at a time and trained for four minutes. It proves the whole pipeline works end to end;
it just hasn't the capacity for meaning. Closing the gap between &ldquo;looks like
language&rdquo; and &ldquo;is coherent&rdquo; is the job of Part III.</p>
"""),
 ],
},

# ====================== PART III — THE UPGRADES ============================
{
 "id": "upgrades", "num": "10", "title": "The upgrades that move quality",
 "part": "Making it good",
 "part_banner": "Part III · The upgrades that move quality (notebook 02)",
 "blocks": [
  ("prose", r"""
<p>Notebook 02 keeps the <em>exact same architecture</em> and layers on the five changes that
actually improve a from-scratch run. Holding the architecture fixed is deliberate: it isolates
what each upgrade buys. One of these — the tokenizer — does most of the work.</p>
"""),
  ("table", r"""
<table>
<thead><tr><th>Upgrade</th><th>Notebook 01</th><th>Notebook 02</th><th>Why it helps</th></tr></thead>
<tbody>
<tr><td>Tokenizer</td><td>one per character</td><td><b>8k word-chunks (BPE)</b></td>
    <td>the big win — the model reasons in word-pieces, not letters</td></tr>
<tr><td>Weight init</td><td>framework default</td><td><b>scaled init</b></td>
    <td>stops a deep stack from blowing up at the start</td></tr>
<tr><td>Learning rate</td><td>constant</td><td><b>warm-up → decay</b></td>
    <td>reliably reaches a lower final loss</td></tr>
<tr><td>Gradient clipping</td><td>none</td><td><b>clip to a limit</b></td>
    <td>insurance against sudden training blow-ups</td></tr>
<tr><td>Capacity / context</td><td>3.2M params, 128</td><td><b>17M params, 256</b></td>
    <td>more room to learn; a whole story fits in view</td></tr>
</tbody></table>
"""),
 ],
},

{
 "id": "bpe", "num": "11", "title": "The big win: word-chunks, not letters",
 "blocks": [
  ("prose", r"""
<p>Working one character at a time forces the model to waste most of its capacity re-learning
how to spell. Real models — and notebook 02 — use <strong>sub-word tokenisation</strong>,
specifically <strong>BPE (Byte-Pair Encoding)</strong>. Starting from raw bytes (essentially
the individual characters), BPE repeatedly merges the most common adjacent pair into a single
new token. After enough merges,
frequent chunks like <code>" the"</code>, <code>"ing"</code>, or <code>" robot"</code> each
become <em>one</em> token. The model then reasons over meaningful units, and coherence appears
far faster at the same size.</p>
<p>Crucially, we <em>train</em> the tokenizer on our own corpus, so all 8,192 tokens are
relevant to these stories — no wasted vocabulary.</p>
"""),
  ("code", "02", "tok = Tokenizer(models.BPE", "Train a byte-level BPE tokenizer on the corpus."),
  ("gloss", r"""
<p><b>What's happening:</b> set up a BPE tokenizer, then <code>train_from_iterator</code> learns
the merges from our text, building an 8,192-token vocabulary. We then re-encode the whole
corpus with it. The print-outs report the <b>compression ratio</b> — characters per token —
and a round-trip check (encode then decode gets the original text back). At ~4 characters per
token, sequences are roughly 4× shorter, so the model effectively sees 4× more story within the
same context window.</p>
"""),
  ("output", "02", "tok = Tokenizer(models.BPE", "what it prints"),
  ("callout", "aside", "Notice the tokens for &ldquo;Once upon a time&rdquo;", r"""
<p>It encodes to just four numbers — four chunks, not sixteen characters. That compression is
the whole point: fewer, more meaningful units for the model to reason over. This is also a
preview of Track B, where a model is fine-tuned for clinical-trial readouts using exactly this
sub-word idea.</p>
"""),
 ],
},

{
 "id": "init", "num": "12", "title": "Init & stability: why deep stacks blow up",
 "blocks": [
  ("prose", r"""
<p>The model code in notebook 02 is the same architecture — but with one substantive change:
<strong>how the parameters start out</strong>. With a deeper stack, the framework's default
starting values can make the loss <em>rise</em> in the first steps. The reason is the residual
connections we praised earlier: every block <em>adds</em> its output back into the running
signal, so without damping, the signal compounds layer over layer and explodes.</p>
<p>The fix is the standard recipe: start all weights from a narrow random spread, and
specifically shrink the output of each block's residual path by a factor that depends on depth.
Tiny change, decisive effect.</p>
"""),
  ("code", "02", "STD = 0.02", "Same architecture, now with scaled initialisation."),
  ("gloss", r"""
<p><b>What to notice</b> (you don't need every line): <code>_normal(...)</code> sets a
parameter's starting values to small random numbers. The important detail is the
<code>STD / math.sqrt(2 * n_layer)</code> on the <code>c_proj</code> and second MLP layer —
the two places where each block writes back into the residual stream. Scaling those down by an
amount that grows with depth keeps the signal's size stable from the first layer to the last.
Everything else — attention, the block, the embeddings, the head — is identical to notebook 01.</p>
"""),
  ("output", "02", "STD = 0.02", "model size"),
  ("callout", "aside", "Same idea, written tighter", r"""
<p>You'll notice this code is more densely packed than notebook 01's. It's the same components —
attention, block, GPT — just written compactly now that the concepts are familiar. If you can
read notebook 01's version, you can read this one.</p>
"""),
 ],
},

{
 "id": "schedule", "num": "13", "title": "A smarter training schedule",
 "blocks": [
  ("prose", r"""
<p>Two upgrades live in the training loop. Both are about <em>stability</em> — letting us train
harder without things breaking.</p>
<ul>
<li><strong>Learning-rate schedule.</strong> Instead of a constant step size, we
<em>warm up</em> — start near zero and ramp up over the first stretch (a cold, random model
hates big steps) — then <em>cosine-decay</em> smoothly back down. The gentle landing lets the
model settle into a better solution.</li>
<li><strong>Gradient clipping.</strong> Before each update, if the proposed change is freakishly
large, scale it back to a ceiling. Cheap insurance against one bad batch blowing up the run.</li>
</ul>
"""),
  ("code", "02", "grads, gnorm = optim.clip_grad_norm", "Warm-up + cosine decay, plus gradient clipping."),
  ("gloss", r"""
<p><b>The new parts vs notebook 01:</b> the three <code>schedule</code> lines build the
learning-rate curve (ramp up, then ease down), handed to the optimizer instead of a fixed
number. Inside the loop, <code>optim.clip_grad_norm(grads, grad_clip)</code> is the one extra
line — it caps the size of each update. The rest of the loop is the same grab-batch → measure →
nudge rhythm from before.</p>
"""),
  ("figure", "loss_curve_tuned.png",
   "Left: a longer, steadier descent than notebook 01. Right: the learning rate ramping up, then decaying."),
  ("gloss", r"""
<p>The right-hand panel is the schedule made visible: the rate climbs during warm-up, then
follows a smooth cosine curve down to its floor. The left panel shows the payoff — a cleaner,
deeper descent than the constant-rate run. (The loss values aren't directly comparable to
notebook 01's, because the vocabulary is different now; it's the <em>shape</em> that matters.)</p>
"""),
 ],
},

{
 "id": "result", "num": "14", "title": "The payoff: from gibberish to little stories",
 "blocks": [
  ("prose", r"""
<p>Same generation loop as before — but now each step samples a word-chunk, not a single
letter. Here is what the tuned model writes, at two different temperatures:</p>
"""),
  ("output", "02", "def generate(prompt, n_new=200", "what the tuned model writes", 1400),
  ("callout", "key", "Look what changed", r"""
<p>Real words. Names that persist across sentences (&ldquo;Timmy,&rdquo; &ldquo;Jack&rdquo;).
Dialogue with quotation marks. The arc of a little story. It still wanders and contradicts
itself — it's a 17-million-parameter model trained for twenty minutes on a laptop — but set it
beside the character-level gibberish from Part II and the leap is unmistakable. <em>Same
architecture.</em> The difference is almost entirely the five upgrades, and mostly the tokenizer.</p>
"""),
  ("callout", "tryit", "Want to feel each upgrade?", r"""
<p>The notebooks invite an <em>ablation</em> — turn one upgrade off, re-run, compare:</p>
<ul>
<li><b>Tokenizer:</b> notebook 01 already <em>is</em> the &ldquo;no-BPE&rdquo; version — compare
its samples to these.</li>
<li><b>Init:</b> remove the depth-scaling and watch the early loss misbehave.</li>
<li><b>Schedule:</b> swap in a constant learning rate; the final loss creeps up.</li>
<li><b>Capacity:</b> push the steps or layers higher for more.</li>
</ul>
"""),
 ],
},

{
 "id": "ceiling", "num": "15", "title": "The honest ceiling — and where this leads",
 "blocks": [
  ("prose", r"""
<p>Even fully tuned, this is a 17-million-parameter model that trained for under an hour on
simple children's stories. It will produce believable words and short phrases — never reasoning
or reliable facts. That gap, between &ldquo;looks like language&rdquo; and &ldquo;is actually
useful,&rdquo; is exactly the gap a <strong>pretrained</strong> model closes: it has already
done the equivalent of this training across <em>trillions</em> of tokens and thousands of
GPU-hours.</p>
<p>And that is the whole point of building the tiny one first. You've now seen, in real code,
every mechanism a frontier model uses — tokenisation, embeddings, attention, the transformer
block, the loss, backpropagation, the optimizer, sampling. The giants are not different in
kind. They are this, scaled.</p>
"""),
  ("callout", "key", "What you now understand end-to-end", r"""
<ul>
<li><b>Tokenisation</b> — text ↔ numbers (characters, then word-chunks).</li>
<li><b>Embeddings</b> — turning a token id and its position into a vector of meaning.</li>
<li><b>Weights, biases &amp; activations</b> — every layer is <code>y = Wx + b</code> followed by
a nonlinear bend (GELU); those W's and b's are exactly the parameters training tunes.</li>
<li><b>Attention</b> — how positions share information, and why looking forward is forbidden.</li>
<li><b>The transformer block</b> — attention + MLP, held together by residuals and LayerNorm.</li>
<li><b>The training loop</b> — the four-step cycle: forward pass → loss → backward pass
(backpropagation) → gradient-descent step.</li>
<li><b>The loss curve</b> — reading learning versus overfitting.</li>
<li><b>Autoregressive sampling</b> — generating one token at a time, and what temperature does.</li>
</ul>
"""),
 ],
},

# ====================== PART IV — USE IT ============================
{
 "id": "use", "num": "16", "title": "Using the model you built",
 "part": "Use the thing you built",
 "part_banner": "Part IV · Use the thing you built (notebook 03)",
 "blocks": [
  ("prose", r"""
<p>Training took twenty-odd minutes. You should only ever pay that <em>once</em>. The last cell
of notebook 02 saves the trained model — its parameters, its tokenizer, and its configuration —
to a folder on disk. After that, a separate, tiny program can reload it in about a second and
generate text without any retraining at all.</p>
"""),
  ("code", "02", "import tiny_gpt", "Save the trained model so you never retrain just to use it."),
  ("gloss", r"""
<p><b>What's happening:</b> bundle up the three things you need to reuse a model — the learned
<b>weights</b>, the <b>tokenizer</b> (so new text is chunked the same way), and the
<b>config</b> (the shape of the model) — and write them to a checkpoint folder. That trio is,
in miniature, exactly what &ldquo;downloading a model&rdquo; gives you anywhere.</p>
"""),
  ("prose", r"""
<p>Reloading is the mirror image. A small library, <code>tiny_gpt.py</code>, rebuilds the model
from the config, pours the saved weights back in, and loads the tokenizer:</p>
"""),
  ("srccode", "lib", "def load(ckpt_dir):", "return model, tok, cfg", "tiny_gpt.load — rebuild and reload in ~1 second."),
  ("gloss", r"""
<p><b>The shape of it:</b> read the config, construct an empty model of that shape,
<code>load_weights</code> fills it with the trained numbers, and the tokenizer is read back from
its file. <code>model.eval()</code> flips it into inference mode. From here, generating text is
instant.</p>
"""),
  ("code", "03", "model, tok, cfg = tiny_gpt.load", "In a notebook: load once, then generate freely."),
  ("gloss", r"""
<p><b>In plain terms:</b> one line, <code>tiny_gpt.load("checkpoints/tiny_gpt_v2")</code>, does
all the rebuilding above and hands back three things — the <code>model</code>, its
<code>tok</code>enizer, and its <code>cfg</code> (configuration). The <code>time</code> calls
around it just measure how long it took, to make the point: about a second, versus the twenty
minutes of training. Load once at the top of a session, then generate as often as you like.</p>
"""),
  ("output", "03", "model, tok, cfg = tiny_gpt.load", "load time"),
 ],
},

{
 "id": "temperature", "num": "17", "title": "The one knob worth feeling: temperature",
 "blocks": [
  ("prose", r"""
<p>You met <code>temperature</code> in the generation code. It's the single most tangible dial
in all of language modelling, and the cheapest to experiment with — no retraining, just re-run.
It controls how boldly the model samples: <strong>low</strong> temperature makes it play it
safe (pick the likeliest token almost every time — coherent but repetitive);
<strong>high</strong> temperature makes it adventurous (give unlikely tokens a real chance —
creative but loopier).</p>
"""),
  ("code", "03", "for temp in (0.4, 0.7, 1.0, 1.2)", "Same prompt, rising temperature."),
  ("gloss", r"""
<p><b>What's happening:</b> run the same opening at four temperatures and print each. Reading the
results from low to high, you can watch the text loosen — tighter and more repetitive at 0.4,
freer and stranger by 1.2. It's the most direct way to <em>feel</em> what sampling does, and the
same knob you'll find in every model's API.</p>
"""),
  ("prose", r"""
<p>There's also a small terminal program, <code>chat.py</code>, that wraps all of this into an
interactive prompt — type an opener, watch the story stream in token by token, adjust the
temperature on the fly. It's the from-scratch model turned into something you can actually play
with.</p>
"""),
 ],
},

{
 "id": "endstory", "num": "18", "title": "Knowing when to stop: the end-of-story token",
 "blocks": [
  ("prose", r"""
<p>You can now generate text and shape it with temperature — but how does the model know when a
story is <em>over</em>? Left alone, it never stops: it just keeps predicting the next token until
you cut it off at a token limit. So every reply comes out the same length, and a long one runs
two stories together.</p>
<p>The fix is the one every real language model uses: a dedicated <strong>end-of-text
token</strong> (GPT-2 calls it <code>&lt;|endoftext|&gt;</code>; here it's
<code>&lt;|endstory|&gt;</code>). A tempting shortcut is to treat the blank line between stories
as the boundary — but that fails, because the blank line is <em>also</em> the paragraph break
inside almost every story, so the model can't tell &ldquo;end of paragraph&rdquo; from &ldquo;end
of story.&rdquo; A reserved token that appears <em>only</em> between stories has no such
ambiguity.</p>
"""),
  ("srccode", "train", "trainer = trainers.BpeTrainer", "data = np.array(ids",
   "Reserve a special token, then drop it after every story in the training stream."),
  ("gloss", r"""
<p><b>What's happening:</b> we add <code>&lt;|endstory|&gt;</code> to the tokenizer as a
<em>special</em> token — matched as one atomic unit, never split into characters — then build the
training stream story-by-story, appending that token's id after each one. The model now sees,
thousands of times over, that a finished story is followed by this exact marker. So it learns to
produce it precisely when a story is complete.</p>
"""),
  ("srccode", "lib", "def stream(model", "emitted = len(gen)",
   "At generation time, stop the instant that token appears."),
  ("gloss", r"""
<p><b>The payoff in code:</b> each step samples the next token; if it's the end-of-story token we
<code>return</code> immediately — <em>before</em> emitting it — so the story ends cleanly on its
last real word. If the model never emits it, the <code>n_new</code> cap still ends things
eventually. That single check is the whole mechanism behind &ldquo;the model decided it was
done.&rdquo;</p>
"""),
  ("rawoutput", """Once upon a time, there was a little girl named Lily. She loved to play outside in the sun and pretend to be a princess. One day, Lily went to the park and saw a little boy who was crying.

"Hello, little boy. What's wrong?" asked Lily.

"I lost my teddy bear," said the boy.

Lily nodded and said, "I will help you find your teddy bear."

Lily was happy to help, and said, "Thank you, I'm glad I could help you." The little boy smiled and said, "Thank you, Lily. You are a good friend.\"""",
   "a complete story from chat.py — it stopped on its own, well short of the token cap"),
  ("callout", "key", "Why this small change matters", r"""
<p>With a real boundary token, stories come out <em>self-contained and naturally varying in
length</em> — a short tale ends short, a longer one runs on, and neither bleeds into a stray new
&ldquo;Once upon a time.&rdquo; It's a tiny change to the <em>data</em>, not the model, but it's
the difference between a fixed-length text dump and something that knows when to stop. Every
chatbot you've used ends its turn in exactly this way.</p>
"""),
  ("callout", "key", "The thread that ties it all together", r"""
<p>Every concept in this walk-through — tokens, attention, the loss, the training loop,
temperature — reappears, unchanged in spirit, in Track B of this lab, where a real pretrained
model is fine-tuned into a useful clinical-trial expert. You built the tiny one to <em>see</em>
the machinery. The same machinery, scaled up and pointed at a real task, is the whole game.</p>
"""),
  ("callout", "aside", "Run it yourself", r"""
<p>Everything here is open source — the three notebooks, the terminal chat, and even the script
that builds this very page — at
<a href="https://github.com/JEM-Fizbit/slm-lab">github.com/JEM-Fizbit/slm-lab</a>. Clone it, run
<code>uv sync</code>, then open <code>notebooks/01_tiny_gpt_from_scratch.ipynb</code> and train
your own tiny GPT — about five minutes on an Apple-silicon Mac.</p>
"""),
 ],
},

]
