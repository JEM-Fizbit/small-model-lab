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
    "title": "Build a tiny GPT from scratch: Part 1 · Pre-training",
    "subtitle": "Pre-training a language model from nothing, on a laptop: the real code, explained.",
}

# ----------------------------------------------------------------------- HERO --
HERO = r"""
<p class="kicker">small-model-lab · Part 1 · Pre-training</p>
<h1>Build a tiny GPT — from scratch</h1>
<p class="lede">This is the <strong>build</strong>: we train a language model from nothing (no
pre-trained weights, no magic) and watch it learn to write, walking through the <em>real code</em>
line by line, for someone who is curious but doesn't necessarily write Python.</p>

<div class="bigidea">
  <p><strong>New to the ideas?</strong> Read <a href="../ideas/">Part 0 · Concepts</a> first. With no
  code, it explains what a model <em>is</em>, how text becomes numbers, what &ldquo;learning&rdquo; means,
  and how the pieces fit (with all the diagrams). This page assumes that groundwork and focuses on
  building it; each step links back to the matching idea in Part 0.</p>
</div>

<p class="readnote"><strong>How to read this.</strong> Top to bottom. Each step is the plain idea in a
line or two, then the actual code in a dark box, then a &ldquo;what this says&rdquo; translation. You can
skip the code boxes entirely and still follow along, or read them closely and learn to recognise what
Python is doing. One tip up front: the muted grey text after a <code>#</code> in the code is a
<em>comment</em>, a note for you that the computer ignores entirely (and this project comments
generously, on purpose). A one-page <a href="#primer">Python primer</a> at the end explains the handful
of symbols that recur. Every code box is real, pulled straight from the project's Jupyter notebooks (code, notes,
and live results in one document you run in your browser), which you can read and run yourself: the full
source is on <a href="https://github.com/JEM-Fizbit/small-model-lab">GitHub</a> (with each notebook and a
from-zero <a href="https://github.com/JEM-Fizbit/small-model-lab/blob/main/docs/GETTING_STARTED.md">setup
guide</a> at the foot of the page).</p>
"""

# -------------------------------------------------------------- PYTHON PRIMER --
PYTHON_PRIMER = r"""
<p>You don't need this to follow the walk-through; the &ldquo;what this says&rdquo; boxes
translate everything. But if you want to read the code itself, here are the few patterns
that show up again and again. Learn these seven and Python stops looking like noise.</p>

<dl class="primer">
  <dt><code># a comment, like this</code></dt>
  <dd><strong>A comment.</strong> Anything from a <code>#</code> to the end of the line is ignored by
  the computer entirely: it's a note for the human reader, nothing more. In the dark code boxes,
  comments are the muted grey text. This project comments heavily on purpose (the &ldquo;no magic
  numbers&rdquo; rule: every setting carries a note on what it does), so a good share of what you'll
  see in the code is notes, not instructions.</dd>

  <dt><code>name = something</code></dt>
  <dd><strong>Assignment.</strong> Give a value a name so you can refer to it later.
  <code>vocab_size = 90</code> means &ldquo;from now on, <code>vocab_size</code> is 90.&rdquo;
  The <code>=</code> is &ldquo;set to,&rdquo; not &ldquo;equals&rdquo; in the maths sense.</dd>

  <dt><code>def do_thing(a, b):</code></dt>
  <dd><strong>Define a function</strong>, a named, reusable recipe. <code>a, b</code> are
  its inputs. Everything indented underneath belongs to it. Later, <code>do_thing(2, 3)</code>
  <em>runs</em> the recipe with those inputs.</dd>

  <dt><code>class GPT:</code></dt>
  <dd><strong>A blueprint</strong> for an object that bundles data and behaviour together.
  The model itself is one of these. <code>__init__</code> is the setup that runs once when
  the object is created; <code>__call__</code> is &ldquo;what happens when you use it like a
  function&rdquo;; so <code>model(x)</code> runs the model on input <code>x</code>.</dd>

  <dt><code>for item in things:</code></dt>
  <dd><strong>A loop.</strong> Do the indented steps once for each item: the engine of
  training (&ldquo;for each step, improve a little&rdquo;) and of generation
  (&ldquo;for each new word, predict one&rdquo;).</dd>

  <dt><code>[ ... ]</code> and indentation</dt>
  <dd>Square brackets make a <strong>list</strong> (an ordered collection). <strong>Indentation
  is meaningful</strong> in Python: the spaces aren't decoration, they show what belongs
  inside a function, loop, or block.</dd>

  <dt><code>x @ y</code> and &ldquo;shapes&rdquo;</dt>
  <dd>The data flowing through the model lives in <strong>arrays</strong>, grids of numbers.
  An array's <strong>shape</strong> is its dimensions, e.g. <code>(B, T, C)</code> =
  (how many examples at once, how many positions in each, how many numbers per position).
  <code>@</code> is <strong>matrix multiplication</strong>, the bulk-arithmetic operation
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
<meta name="description" content="{{ meta.subtitle }}"/>
<meta property="og:title" content="{{ meta.title }}"/>
<meta property="og:description" content="{{ meta.subtitle }}"/>
<meta property="og:type" content="article"/>
<link rel="apple-touch-icon" href="../apple-touch-icon.png"/>
<link rel="icon" type="image/png" sizes="64x64" href="../favicon.png"/>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064%2064%22%3E%3Crect%20width%3D%2264%22%20height%3D%2264%22%20rx%3D%2210%22%20fill%3D%22%23f7f3ea%22%2F%3E%3Crect%20x%3D%222.5%22%20y%3D%222.5%22%20width%3D%2259%22%20height%3D%2259%22%20rx%3D%228%22%20fill%3D%22none%22%20stroke%3D%22%23ddd4c2%22%20stroke-width%3D%222%22%2F%3E%3Ctext%20x%3D%2232%22%20y%3D%2246%22%20text-anchor%3D%22middle%22%20font-family%3D%22Georgia%2Cserif%22%20font-style%3D%22italic%22%20font-size%3D%2242%22%20fill%3D%22%23963d2c%22%3E%C2%A7%3C%2Ftext%3E%3C%2Fsvg%3E"/>
<meta property="og:image" content="https://jem-fizbit.github.io/small-model-lab/og-image.png"/>
<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300..700;1,6..72,300..700&family=IBM+Plex+Mono:ital,wght@0,400;0,500;0,600;1,400&display=swap');

/* ── small-model-lab · "The Monograph" chapter stylesheet ─────────────────────────
   Warm paper, Newsreader serif, IBM Plex Mono labels, one madder accent.
   Drop-in replacement for the <style> block in content.py's TEMPLATE:
   every selector below matches the existing markup. */

:root{
  --ink:#231f18; --soft:#6e6557; --faint:#998f7d;
  --line:#ddd4c2; --line-soft:#e8e1d2;
  --bg:#f7f3ea; --panel:#fbf8f1;
  --accent:#963d2c; --accent-soft:#f0e2dc;
  --code-bg:#f0eadb; --code-line:#e0d7c2;
  --teal:#3d6a72; --olive:#5f6c33;
  --serif:'Newsreader',Charter,'Iowan Old Style',Georgia,serif;
  --sans:'Newsreader',Charter,Georgia,serif; /* serif-first identity; --sans kept for selector compat */
  --mono:'IBM Plex Mono','SF Mono',ui-monospace,Menlo,monospace;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
.tablewrap,.codefig .hl,.term pre,.diagram{scrollbar-width:thin;scrollbar-color:#cfc5ae transparent;}
.tablewrap::-webkit-scrollbar,.codefig .hl::-webkit-scrollbar,.term pre::-webkit-scrollbar,.diagram::-webkit-scrollbar{height:8px;width:8px;}
.tablewrap::-webkit-scrollbar-thumb,.codefig .hl::-webkit-scrollbar-thumb,.term pre::-webkit-scrollbar-thumb,.diagram::-webkit-scrollbar-thumb{background:#cfc5ae;border-radius:4px;}
.tablewrap::-webkit-scrollbar-track,.codefig .hl::-webkit-scrollbar-track,.term pre::-webkit-scrollbar-track,.diagram::-webkit-scrollbar-track{background:transparent;}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--serif);
  font-size:18px;line-height:1.7;-webkit-font-smoothing:antialiased;
  font-optical-sizing:auto;}
::selection{background:var(--accent-soft);}

/* labels — the one non-serif voice */
.kicker,.toctitle,.toc-part,.part-banner,.gloss-tag,.term-tag,.callout-title,
.primer-kicker,.codebar .srcname{
  font-family:var(--mono)!important;text-transform:uppercase;letter-spacing:.16em;
  font-size:11px;font-weight:500;}

/* ── top nav ── */
.topnav{background:var(--bg);border-bottom:1px solid var(--line);
  position:sticky;top:0;z-index:50;}
.topnav .inner{max-width:1140px;margin:0 auto;padding:14px 24px;display:flex;gap:34px;
  align-items:baseline;font-family:var(--mono);font-size:11.5px;
  text-transform:uppercase;letter-spacing:.12em;}
.topnav a{color:var(--soft);text-decoration:none;white-space:nowrap;}
.topnav a:hover{color:var(--accent);}
.topnav a.active{color:var(--accent);font-weight:600;
  border-bottom:1px solid var(--accent);padding-bottom:2px;}
.topnav .pnum{color:var(--faint);}
.topnav a:hover .pnum,.topnav a.active .pnum{color:var(--accent);}
.topnav a.hub{margin-left:auto;color:var(--faint);}
.topnav a.hub:hover{color:var(--accent);}
.topnav .muted{color:var(--faint);white-space:nowrap;}
.topnav .muted em{font-style:normal;font-size:10px;opacity:.85;}
.topnav .hub-short{display:none;}

/* ── hero — same paper, ruled, no gradient ── */
.hero{background:var(--bg);color:var(--ink);padding:72px 24px 52px;
  border-bottom:1px solid var(--line);}
.hero .inner{max-width:1140px;margin:0 auto;}
.hero .kicker{color:var(--accent);margin:0 0 18px;}
.hero h1{font-family:var(--serif);font-weight:500;font-size:50px;line-height:1.06;
  margin:0 0 22px;letter-spacing:-.022em;max-width:780px;}
.hero .lede{font-size:20px;line-height:1.62;color:var(--soft);margin:0 0 26px;max-width:680px;}
.bigidea{background:transparent;border:none;border-top:1px solid var(--ink);
  border-bottom:1px solid var(--line);border-radius:0;padding:20px 0;margin:30px 0;max-width:680px;}
.bigidea p{margin:0 0 10px;font-size:17.5px;color:var(--ink);}
.bigidea p:last-child{margin:0;color:var(--soft);font-size:16px;}
.hero .readnote{font-size:15.5px;color:var(--soft);font-family:var(--serif);line-height:1.65;
  border-top:none;padding-top:0;margin-top:26px;max-width:680px;}
.hero a{color:var(--accent);text-decoration:none;border-bottom:1px solid var(--accent-soft);}
.hero a:hover{border-color:var(--accent);}

/* ── layout ── */
.layout{max-width:1140px;margin:0 auto;display:grid;grid-template-columns:236px 1fr;
  gap:56px;padding:48px 24px 80px;}
nav.toc{position:sticky;top:64px;align-self:start;font-family:var(--serif);font-size:14.5px;
  max-height:calc(100vh - 88px);overflow:auto;scrollbar-width:none;}
nav.toc::-webkit-scrollbar{display:none;}
nav.toc .toctitle{color:var(--faint);margin:0 0 12px;}
nav.toc a{display:grid;grid-template-columns:30px 1fr;align-items:baseline;color:var(--soft);text-decoration:none;padding:4.5px 0;
  line-height:1.45;}
nav.toc a:hover{color:var(--accent);}
nav.toc .toc-part{color:var(--accent);margin:20px 0 8px;font-size:10.5px;
  border-top:1px solid var(--line);padding-top:12px;}
nav.toc .toc-num{color:var(--faint);font-family:var(--mono);font-size:11px;
  font-variant-numeric:tabular-nums;}

main{min-width:0;max-width:720px;}
section{margin:0 0 8px;padding:38px 0 6px;border-top:1px solid var(--line);scroll-margin-top:64px;}
section:first-of-type{border-top:none;padding-top:0;}
.sec-head{display:flex;align-items:baseline;gap:16px;margin:0 0 16px;}
.sec-num{font-family:var(--serif);font-style:italic;font-weight:400;font-size:26px;
  color:var(--accent);background:transparent;border-radius:0;padding:0;
  letter-spacing:0;white-space:nowrap;flex:none;}
.sec-num::before{content:"§ ";}
.sec-head h2{font-family:var(--serif);font-weight:500;font-size:30px;letter-spacing:-.015em;
  margin:0;line-height:1.18;}
.part-banner{color:var(--accent);margin:8px 0 0;}

/* ── prose ── */
.prose{margin:0 0 4px;}
.prose p{margin:0 0 18px;text-wrap:pretty;}
.prose h3{font-family:var(--serif);font-size:21px;font-weight:600;margin:28px 0 10px;
  letter-spacing:-.01em;}
.prose strong{font-weight:600;}
.prose em{font-style:italic;}
.prose code,.gloss code,.callout code,td code,.primer code{font-family:var(--mono);
  font-size:.82em;background:var(--code-bg);color:#4a4234;padding:1px 6px;border-radius:3px;
  overflow-wrap:anywhere;}
.prose a,.gloss a,.callout a{color:var(--accent);text-decoration:none;
  border-bottom:1px solid var(--accent-soft);}
.prose a:hover,.gloss a:hover,.callout a:hover{border-color:var(--accent);}

/* ── code figures — quiet parchment inset, no window chrome ── */
.codefig{margin:26px 0;border-radius:3px;overflow:hidden;
  box-shadow:none;border:1px solid var(--code-line);background:var(--code-bg);}
.codebar{background:#e9e2cf;display:flex;align-items:baseline;gap:7px;padding:8px 16px;
  border-bottom:1px solid var(--code-line);}
.codebar .dot{display:none;}
.codebar .srcname{margin-left:0;color:var(--accent);font-size:10.5px;}
.codefig .hl{margin:0;padding:18px 20px;overflow:auto;background:var(--code-bg);
  font-family:var(--mono);font-size:13px;line-height:1.6;}
.codefig .hl pre{margin:0;}
.codefig figcaption{font-family:var(--serif);font-style:italic;font-size:14.5px;color:var(--soft);
  background:var(--bg);padding:10px 16px;border-top:1px solid var(--code-line);}

/* pygments (light, muted — replaces monokai) */
.hl pre{color:#3a342a;}
.hl .c,.hl .c1,.hl .ch,.hl .cm,.hl .cs,.hl .cpf{color:#9a8f7a;font-style:italic;}
.hl .k,.hl .kc,.hl .kd,.hl .kn,.hl .kp,.hl .kr,.hl .kt,.hl .ow{color:var(--accent);}
.hl .s,.hl .s1,.hl .s2,.hl .sa,.hl .sb,.hl .sc,.hl .se,.hl .si,.hl .sx,.hl .sr,.hl .ss,.hl .sd{color:var(--olive);}
.hl .m,.hl .mi,.hl .mf,.hl .mh,.hl .mo,.hl .il{color:var(--teal);}
.hl .nf,.hl .fm,.hl .nc,.hl .nd,.hl .ne,.hl .nx{color:#234a5c;}
.hl .nb,.hl .bp,.hl .vm{color:#234a5c;}
.hl .o,.hl .p,.hl .pm{color:#6e6557;}
.hl .n,.hl .nn,.hl .nv,.hl .na,.hl .nt,.hl .kt{color:#3a342a;}
.hl .err{border:none;color:#3a342a;}
.hl .gp{color:var(--faint);}

/* ── gloss ("what this says") — ruled, not boxed ── */
.gloss{background:transparent;border:none;border-top:1px solid var(--ink);
  border-bottom:1px solid var(--line);border-radius:0;padding:16px 0 8px;margin:22px 0 26px;
  font-size:16px;}
.gloss-tag{color:var(--accent);margin:0 0 10px;}
.gloss p{margin:0 0 12px;}
.gloss ul{margin:0 0 12px;padding-left:22px;}
.gloss li{margin:0 0 7px;}
.gloss b{color:var(--ink);font-weight:600;}

/* ── terminal output — quiet rule, no panel ── */
.term{margin:20px 0 24px;border-radius:0 3px 3px 0;overflow:hidden;
  border:1px solid var(--code-line);border-left:2px solid var(--accent);
  background:#f1ece0;padding:12px 16px 14px;}
.term-tag{color:var(--soft);background:transparent;padding:0 0 8px;border-bottom:none;}
.term pre{margin:0;padding:0;background:transparent;color:var(--ink);
  font-family:var(--mono);font-size:12.5px;line-height:1.55;overflow:auto;
  white-space:pre-wrap;word-break:break-word;}

/* ── figures ── */
.imgfig{margin:26px 0;text-align:center;background:var(--panel);
  border:1px solid var(--line);border-radius:3px;padding:20px 18px 8px;
  box-shadow:none;}
.imgfig img{max-width:100%;border:none;border-radius:0;
  box-shadow:none;background:transparent;mix-blend-mode:multiply;}
.imgfig figcaption{font-family:var(--serif);font-style:italic;font-size:14.5px;
  color:var(--soft);margin-top:10px;}
.fignum{font-weight:600;font-style:normal;color:var(--accent);margin-right:8px;
  scroll-margin-top:64px;font-family:var(--mono);font-size:11.5px;
  text-transform:uppercase;letter-spacing:.1em;}
.diagram svg{max-width:100%;height:auto;display:block;margin:0 auto;}
.diagram text{font-family:var(--serif);}
.diagram figcaption{margin-top:6px;}

/* ── callouts — one family, ruled; label color carries the variant ── */
.callout{border-radius:0;padding:16px 0 18px;margin:26px 0;font-size:16.5px;
  font-family:var(--serif);line-height:1.65;background:transparent;border:none;
  border-top:1px solid var(--ink);border-bottom:1px solid var(--line);}
.callout-title{margin:0 0 9px;font-weight:500;}
.callout-body p{margin:0 0 10px;}
.callout-body p:last-child{margin:0;}
.callout-body ul{margin:6px 0 0;padding-left:20px;}
.callout-body li{margin:0 0 6px;}
.callout.key{background:transparent;border-color:var(--ink) transparent var(--line);}
.callout.key .callout-title{color:var(--accent);}
.callout.tryit .callout-title{color:var(--olive);}
.callout.aside{border-top-color:var(--line);}
.callout.aside .callout-title{color:var(--faint);}
.callout.math .callout-title{color:var(--teal);}
.callout.insight .callout-title{color:var(--accent);}
.callout.math .formula{font-family:var(--mono);font-size:14.5px;background:var(--code-bg);
  border:1px solid var(--code-line);border-radius:3px;padding:12px 14px;margin:6px 0 12px;
  text-align:center;color:#4a4234;overflow:auto;}

/* ── tables ── */
.tablewrap{margin:24px 0;overflow:auto;}
table{border-collapse:collapse;width:100%;font-family:var(--serif);font-size:15.5px;}
th,td{text-align:left;padding:10px 13px;border-bottom:1px solid var(--line);
  vertical-align:top;}
th{font-family:var(--mono);font-weight:500;color:var(--soft);border-bottom:1px solid var(--ink);
  background:transparent;font-size:11px;text-transform:uppercase;letter-spacing:.12em;}
td:first-child{font-weight:600;}

/* ── python primer appendix ── */
.primer-panel{background:var(--panel);border:1px solid var(--line);border-radius:3px;
  padding:6px 26px 16px;margin-top:10px;}
section.primer-sec .sec-num{background:transparent;color:var(--teal);}
.primer-kicker{color:var(--teal);margin:8px 0 0;}
dl.primer{margin:18px 0;}
dl.primer dt{display:block;font-family:var(--mono);font-size:13px;color:#4a4234;
  background:var(--code-bg);border:1px solid var(--code-line);border-bottom:1px dashed var(--code-line);
  border-radius:3px 3px 0 0;padding:10px 16px 9px;margin:18px 0 0;}
dl.primer dd{margin:0 0 18px;font-size:15.5px;background:var(--bg);
  border:1px solid var(--code-line);border-top:none;border-radius:0 0 3px 3px;padding:11px 16px 13px;}

/* ── footer ── */
footer{border-top:1px solid var(--line);padding:28px 24px 60px;text-align:left;
  font-family:var(--mono);font-size:11.5px;color:var(--faint);line-height:1.9;}
footer p{margin:0 auto 10px;text-wrap:pretty;max-width:1140px;}
footer p:last-child{margin-bottom:0;}
footer .seg{display:inline-block;}
footer code{font-family:var(--mono);background:var(--code-bg);padding:1px 6px;border-radius:3px;}
footer a{color:var(--accent);text-decoration:none;border-bottom:1px solid var(--accent-soft);}
footer a:hover{border-color:var(--accent);}
footer strong{color:var(--soft);}

/* ── page jump buttons ── */
.pagenav{position:fixed;right:18px;bottom:18px;z-index:60;display:flex;flex-direction:column;gap:8px;}
.pagenav a{width:38px;height:38px;border-radius:2px;display:flex;align-items:center;
  justify-content:center;background:var(--bg);color:var(--accent);border:1px solid var(--line);
  text-decoration:none;font-size:16px;line-height:1;box-shadow:none;font-family:var(--serif);
  transition:background .12s,color .12s,border-color .12s;}
.pagenav a:hover{background:var(--accent);color:var(--bg);border-color:var(--accent);}
@media (max-width:920px){.pagenav{right:12px;bottom:12px;}}

/* ── responsive ── */
@media (max-width:920px){
  .layout{grid-template-columns:1fr;gap:0;}
  nav.toc{display:none;}
  .hero h1{font-size:38px;}
  body{font-size:17px;}
}
@media (max-width:680px){
  .diagram{overflow-x:auto;}
  .diagram svg{min-width:640px;}
  .topnav .inner{flex-wrap:wrap;padding:9px 16px;gap:5px 13px;font-size:10px;letter-spacing:.08em;}
  .topnav .pnum{display:none;}
  .topnav .hub-long{display:none;}
  .topnav .hub-short{display:inline;}
}
@media print{.pagenav,.topnav{display:none;}}
</style>
</head>
<body>

<nav class="topnav"><div class="inner">
{% for n in nav %}{% if n.href %}<a href="{{ n.href }}"{% if n.active %} class="active"{% endif %}>{{ n.label }}</a>{% else %}<span class="muted">{{ n.label }}{% if n.note %} <em>({{ n.note }})</em>{% endif %}</span>{% endif %}{% endfor %}
<a class="hub" href="{{ hub_url }}"><span class="hub-long">AI Knowledge Hub ↗</span><span class="hub-short">Hub ↗</span></a>
</div></nav>

<header class="hero" id="top"><div class="inner">{{ hero }}</div></header>

<nav class="pagenav" aria-label="Page jump">
  <a href="#top" title="Top" aria-label="Scroll to top">&uarr;</a>
  <a href="#bottom" title="Bottom" aria-label="Scroll to bottom">&darr;</a>
  <a href="../" title="Home" aria-label="small-model-lab home">&#8962;</a>
</nav>

<div class="layout">
  <nav class="toc">
    <p class="toctitle">Contents</p>
    {% for t in toc %}
      {% if t.part %}<div class="toc-part">{{ t.part }}</div>
      {% else %}<a href="#{{ t.id }}"><span class="toc-num">{{ t.num }}</span>{{ t.title }}</a>{% endif %}
    {% endfor %}
    {% if primer %}<div class="toc-part">Reference</div>
    <a href="#primer"><span class="toc-num">↪</span>Python primer</a>{% endif %}
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

    {% if primer %}<section id="primer" class="primer-sec">
      <p class="primer-kicker">Reference appendix</p>
      <div class="sec-head"><span class="sec-num">↪</span><h2>Python primer</h2></div>
      <div class="primer-panel"><div class="prose">{{ primer }}</div></div>
    </section>{% endif %}
  </main>
</div>

<footer id="bottom">
  <p>{{ footer_gen }}</p>
  <p>Built in collaboration with Claude (via Claude Code): John directed, co-wrote, and made every
  editorial call; Claude drafted much of the prose and most of the code and diagrams.
  <span class="seg">Spotted an error, or have a comment?</span>
  <span class="seg"><a href="https://github.com/JEM-Fizbit/small-model-lab/issues">Open a GitHub issue</a>.</span></p>
  <p><span class="seg">Open source:
  <a href="https://github.com/JEM-Fizbit/small-model-lab">github.com/JEM-Fizbit/small-model-lab</a>&nbsp;·</span>
  <span class="seg">notebooks
  <a href="https://github.com/JEM-Fizbit/small-model-lab/blob/main/notebooks/01_tiny_gpt_from_scratch.ipynb">01</a>,
  <a href="https://github.com/JEM-Fizbit/small-model-lab/blob/main/notebooks/02_tiny_gpt_tuned.ipynb">02</a>,
  <a href="https://github.com/JEM-Fizbit/small-model-lab/blob/main/notebooks/03_tiny_gpt_chat.ipynb">03</a>&nbsp;·</span>
  <span class="seg"><a href="https://github.com/JEM-Fizbit/small-model-lab/blob/main/docs/GETTING_STARTED.md">getting
  started</a>&nbsp;·</span>
  <span class="seg">{{ footer_note }}</span></p>
  <p><span class="seg"><a href="https://github.com/JEM-Fizbit/small-model-lab/blob/main/LICENSE">MIT-licensed</a>
  © 2026 John E. Milad.</span>
  <span class="seg">Builds on <a href="https://github.com/karpathy/nanoGPT">nanoGPT</a> (Karpathy),</span>
  <span class="seg"><a href="https://github.com/ml-explore/mlx">Apple MLX</a>,</span>
  <span class="seg">and the <a href="https://huggingface.co/datasets/roneneldan/TinyStories">TinyStories</a>
  dataset</span>
  <span class="seg">(Eldan &amp; Li, Microsoft Research).</span></p>
  <p><span class="seg">Part of <strong>John E. Milad's</strong>
  <a href="{{ hub_url }}">AI Knowledge Hub</a></span>
  <span class="seg">— a curated, hands-on library for the AI era.</span></p>
</footer>

</body>
</html>
"""

# ---------------------------------------------------------------- DIAGRAMS --
# Hand-drawn inline SVG (no JS, no external assets — keeps the single-file build).

LANDSCAPE_SVG = r'''<svg viewBox="0 0 640 300" role="img" aria-label="A loss landscape shaped like a valley. A ball sits partway up the left slope, with an arrow showing one step downhill toward the point of lowest loss.">
<defs><marker id="arL" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#231f18"/></marker></defs>
<line x1="62" y1="28" x2="62" y2="272" stroke="#d8cfbd" stroke-width="1.5"/>
<line x1="62" y1="272" x2="612" y2="272" stroke="#d8cfbd" stroke-width="1.5"/>
<text x="50" y="42" text-anchor="end" font-size="12" fill="#998f7d">high</text>
<text x="26" y="150" text-anchor="middle" font-size="13" fill="#6e6557" transform="rotate(-90 26 150)">loss (how wrong)</text>
<text x="337" y="294" text-anchor="middle" font-size="13" fill="#6e6557">a single weight (one of our model&#8217;s ~3.2 million)</text>
<path d="M 90 70 Q 335 400 580 70" fill="none" stroke="#963d2c" stroke-width="3"/>
<line x1="335" y1="235" x2="335" y2="272" stroke="#5f6c33" stroke-width="1.5" stroke-dasharray="4 4"/>
<circle cx="335" cy="235" r="4.5" fill="#5f6c33"/>
<text x="346" y="231" font-size="12" fill="#5f6c33">lowest loss</text>
<circle cx="188" cy="176" r="11" fill="#b0402a" stroke="#fff" stroke-width="2.5"/>
<text x="126" y="150" text-anchor="middle" font-size="12" fill="#231f18">current</text>
<text x="126" y="165" text-anchor="middle" font-size="12" fill="#231f18">weights</text>
<line x1="201" y1="186" x2="258" y2="210" stroke="#231f18" stroke-width="2" marker-end="url(#arL)"/>
<text x="300" y="200" font-size="12" fill="#231f18">one step downhill</text>
</svg>'''

CYCLE_SVG = r'''<svg viewBox="0 0 760 250" role="img" aria-label="The training cycle as a loop of four boxes: forward pass, then loss, then backward pass, then update, then back to the start.">
<defs><marker id="arC" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#963d2c"/></marker></defs>
<rect x="15" y="40" width="160" height="80" rx="12" fill="#f3ece1" stroke="#963d2c" stroke-width="1.5"/>
<text x="95" y="68" text-anchor="middle" font-size="13.5" font-weight="700" fill="#231f18">① Forward pass</text>
<text x="95" y="88" text-anchor="middle" font-size="11" fill="#6e6557">run data → predictions</text>
<text x="95" y="106" text-anchor="middle" font-size="11" fill="#963d2c" font-family="ui-monospace,Menlo,monospace">model(x)</text>
<rect x="205" y="40" width="160" height="80" rx="12" fill="#f3ece1" stroke="#963d2c" stroke-width="1.5"/>
<text x="285" y="68" text-anchor="middle" font-size="13.5" font-weight="700" fill="#231f18">② Loss</text>
<text x="285" y="88" text-anchor="middle" font-size="11" fill="#6e6557">how wrong is it?</text>
<text x="285" y="106" text-anchor="middle" font-size="11" fill="#963d2c" font-family="ui-monospace,Menlo,monospace">cross_entropy</text>
<rect x="395" y="40" width="160" height="80" rx="12" fill="#f3ece1" stroke="#963d2c" stroke-width="1.5"/>
<text x="475" y="68" text-anchor="middle" font-size="13.5" font-weight="700" fill="#231f18">③ Backward pass</text>
<text x="475" y="88" text-anchor="middle" font-size="11" fill="#6e6557">which way is downhill</text>
<text x="475" y="106" text-anchor="middle" font-size="11" fill="#963d2c" font-family="ui-monospace,Menlo,monospace">loss_and_grad</text>
<rect x="585" y="40" width="160" height="80" rx="12" fill="#f3ece1" stroke="#963d2c" stroke-width="1.5"/>
<text x="665" y="68" text-anchor="middle" font-size="13.5" font-weight="700" fill="#231f18">④ Update</text>
<text x="665" y="88" text-anchor="middle" font-size="11" fill="#6e6557">one step downhill</text>
<text x="665" y="106" text-anchor="middle" font-size="11" fill="#963d2c" font-family="ui-monospace,Menlo,monospace">optimizer.update</text>
<line x1="175" y1="80" x2="203" y2="80" stroke="#963d2c" stroke-width="2" marker-end="url(#arC)"/>
<line x1="365" y1="80" x2="393" y2="80" stroke="#963d2c" stroke-width="2" marker-end="url(#arC)"/>
<line x1="555" y1="80" x2="583" y2="80" stroke="#963d2c" stroke-width="2" marker-end="url(#arC)"/>
<path d="M 665 120 L 665 180 L 95 180 L 95 120" fill="none" stroke="#963d2c" stroke-width="2" stroke-dasharray="5 4" marker-end="url(#arC)"/>
<text x="380" y="173" text-anchor="middle" font-size="12.5" fill="#963d2c">repeat ~2,500 times</text>
</svg>'''

# ===========================================================================
#  SECTIONS — the walk-through itself
# ===========================================================================

LINEAR_SVG = r'''<svg viewBox="0 0 880 754" role="img" aria-label="A linear layer. fox is looked up to its embedding (256 numbers). Each output is its own neuron: all 256 inputs times that output's weights plus its bias = one number. A layer stacks m such outputs, so y and b have m entries (a few shown). One token in becomes a new vector of m numbers out, not a single number.">
<defs><marker id="aA" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#6e6557"/></marker></defs>
<text x="58" y="26" text-anchor="start" font-size="13" fill="#231f18" font-weight="700" >① One output (a "neuron"): a token's 256 numbers → one number</text>
<text x="72" y="62" text-anchor="middle" font-size="9.5" fill="#6e6557" font-weight="400" >vocabulary</text>
<rect x="46" y="70" width="52" height="26" rx="7" fill="#f3ece1" stroke="#963d2c" stroke-width="1.3"/>
<text x="72" y="87" text-anchor="middle" font-size="12.5" fill="#231f18" font-weight="400" >the</text>
<rect x="46" y="100" width="52" height="26" rx="7" fill="#ecd9d0" stroke="#963d2c" stroke-width="2.4"/>
<text x="72" y="117" text-anchor="middle" font-size="12.5" fill="#231f18" font-weight="700" >fox</text>
<rect x="46" y="130" width="52" height="26" rx="7" fill="#f3ece1" stroke="#963d2c" stroke-width="1.3"/>
<text x="72" y="147" text-anchor="middle" font-size="12.5" fill="#231f18" font-weight="400" >cat</text>
<text x="72" y="162" text-anchor="middle" font-size="13" fill="#6e6557" font-weight="400" >⋮</text>
<line x1="100" y1="113" x2="142" y2="113" stroke="#6e6557" stroke-width="1.6" marker-end="url(#aA)"/>
<text x="121" y="106" text-anchor="middle" font-size="8.5" fill="#6e6557" font-weight="400" >look up</text>
<text x="178" y="50" text-anchor="middle" font-size="11" fill="#963d2c" font-weight="400" >fox's embedding</text>
<text x="178" y="63" text-anchor="middle" font-size="9.5" fill="#6e6557" font-weight="400" >(x: #1–3, then #256)</text>
<rect x="150" y="70" width="60" height="27" rx="4" fill="#f3ece1" stroke="#963d2c" stroke-width="1.3"/>
<text x="180.0" y="87.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">0.31</text>
<rect x="150" y="97" width="60" height="27" rx="4" fill="#f3ece1" stroke="#963d2c" stroke-width="1.3"/>
<text x="180.0" y="114.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">−1.20</text>
<rect x="150" y="124" width="60" height="27" rx="4" fill="#f3ece1" stroke="#963d2c" stroke-width="1.3"/>
<text x="180.0" y="141.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">0.05</text>
<rect x="150" y="151" width="60" height="27" rx="4" fill="#f3ece1" stroke="#963d2c" stroke-width="1.3"/>
<text x="180.0" y="168.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">⋮</text>
<rect x="150" y="178" width="60" height="27" rx="4" fill="#f3ece1" stroke="#963d2c" stroke-width="1.3"/>
<text x="180.0" y="195.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">0.12</text>
<text x="224" y="88.5" text-anchor="middle" font-size="14" fill="#6e6557" font-weight="400" >×</text>
<text x="224" y="115.5" text-anchor="middle" font-size="14" fill="#6e6557" font-weight="400" >×</text>
<text x="224" y="142.5" text-anchor="middle" font-size="14" fill="#6e6557" font-weight="400" >×</text>
<text x="224" y="196.5" text-anchor="middle" font-size="14" fill="#6e6557" font-weight="400" >×</text>
<text x="286" y="50" text-anchor="middle" font-size="11" fill="#8c6a2a" font-weight="400" >its weights</text>
<text x="286" y="63" text-anchor="middle" font-size="9.5" fill="#6e6557" font-weight="400" >(one per number)</text>
<rect x="238" y="70" width="60" height="27" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="268.0" y="87.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">0.80</text>
<rect x="238" y="97" width="60" height="27" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="268.0" y="114.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">−0.40</text>
<rect x="238" y="124" width="60" height="27" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="268.0" y="141.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">1.10</text>
<rect x="238" y="151" width="60" height="27" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="268.0" y="168.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">⋮</text>
<rect x="238" y="178" width="60" height="27" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="268.0" y="195.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">−0.70</text>
<path d="M302 74 q12 0 12 13 v36 q0 13 12 13 q-12 0 -12 13 v36 q0 13 -12 13" fill="none" stroke="#6e6557" stroke-width="1.2"/>
<text x="326" y="130" text-anchor="start" font-size="10.5" fill="#6e6557" font-weight="400" >add</text>
<text x="326" y="143" text-anchor="start" font-size="10.5" fill="#6e6557" font-weight="400" >them up</text>
<text x="58" y="226" text-anchor="start" font-size="12" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">y₁  =  0.31×0.80  +  (−1.20)×(−0.40)  +  0.05×1.10  +  ⋯  +  0.12×(−0.70)  +  b₁   =  0.62</text>
<text x="58" y="252" text-anchor="start" font-size="10.5" fill="#a83a28" font-weight="700" >✗ NOT f→0.31, o→−1.20, x→0.05. The letters do not map to the numbers. The whole word "fox" is looked up to all 256 at once.</text>
<text x="58" y="268" text-anchor="start" font-size="10.5" fill="#6e6557" font-weight="400" >Each of fox's 256 numbers (its "embedding") is its value on one learned attribute/dimension. See the embedding figure below.</text>
<line x1="40" y1="288" x2="820" y2="288" stroke="#ddd4c2" stroke-width="1.5"/>
<text x="58" y="314" text-anchor="start" font-size="13" fill="#231f18" font-weight="700" >② A layer = MANY such neurons stacked: one row of weights each → the matrix <tspan fill="#8c6a2a">W</tspan> (so <tspan fill="#5f6c33">y</tspan> = <tspan fill="#8c6a2a">W</tspan><tspan fill="#963d2c">x</tspan> + <tspan fill="#8c6a2a">b</tspan>)</text>
<rect x="80" y="340" width="46" height="29" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="103.0" y="358.5" text-anchor="middle" font-size="9.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">0.80</text>
<rect x="126" y="340" width="46" height="29" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="149.0" y="358.5" text-anchor="middle" font-size="9.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">−0.40</text>
<rect x="172" y="340" width="46" height="29" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="195.0" y="358.5" text-anchor="middle" font-size="9.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">1.10</text>
<rect x="240" y="340" width="46" height="29" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="263.0" y="358.5" text-anchor="middle" font-size="9.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">−0.70</text>
<text x="222" y="358.5" text-anchor="middle" font-size="12" fill="#6e6557" font-weight="400" >⋯</text>
<rect x="80" y="369" width="46" height="29" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<rect x="126" y="369" width="46" height="29" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<rect x="172" y="369" width="46" height="29" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<rect x="240" y="369" width="46" height="29" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="222" y="387.5" text-anchor="middle" font-size="12" fill="#6e6557" font-weight="400" >⋯</text>
<rect x="80" y="398" width="46" height="29" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<rect x="126" y="398" width="46" height="29" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<rect x="172" y="398" width="46" height="29" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<rect x="240" y="398" width="46" height="29" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="222" y="416.5" text-anchor="middle" font-size="12" fill="#6e6557" font-weight="400" >⋯</text>
<text x="103.0" y="437" text-anchor="middle" font-size="12" fill="#6e6557" font-weight="400" >⋮</text>
<text x="149.0" y="437" text-anchor="middle" font-size="12" fill="#6e6557" font-weight="400" >⋮</text>
<text x="195.0" y="437" text-anchor="middle" font-size="12" fill="#6e6557" font-weight="400" >⋮</text>
<text x="263.0" y="437" text-anchor="middle" font-size="12" fill="#6e6557" font-weight="400" >⋮</text>
<rect x="78" y="338" width="210" height="33" rx="5" fill="none" stroke="#8c6a2a" stroke-width="2.4"/>
<text x="160" y="331" text-anchor="middle" font-size="11" fill="#8c6a2a" font-weight="400" >W  (parameters)</text>
<text x="300" y="359.5" text-anchor="start" font-size="9.5" fill="#6e6557" font-weight="400" >← top row = output ① (the neuron above)</text>
<text x="300" y="374.5" text-anchor="start" font-size="9.5" fill="#6e6557" font-weight="400" >columns = inputs · rows = outputs</text>
<text x="58" y="457" text-anchor="start" font-size="10" fill="#6e6557" font-weight="400" >3 of m rows shown; each row is a different output (its own neuron)</text>
<text x="551" y="385.5" text-anchor="middle" font-size="16" fill="#6e6557" font-weight="400" >×</text>
<text x="593" y="331" text-anchor="middle" font-size="11" fill="#963d2c" font-weight="400" >x: inputs</text>
<rect x="566" y="340" width="54" height="27" rx="4" fill="#f3ece1" stroke="#963d2c" stroke-width="1.3"/>
<text x="593.0" y="357.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">0.31</text>
<rect x="566" y="367" width="54" height="27" rx="4" fill="#f3ece1" stroke="#963d2c" stroke-width="1.3"/>
<text x="593.0" y="384.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">−1.20</text>
<rect x="566" y="394" width="54" height="27" rx="4" fill="#f3ece1" stroke="#963d2c" stroke-width="1.3"/>
<text x="593.0" y="411.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">0.05</text>
<rect x="566" y="421" width="54" height="27" rx="4" fill="#f3ece1" stroke="#963d2c" stroke-width="1.3"/>
<text x="593.0" y="438.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">⋮</text>
<rect x="566" y="448" width="54" height="27" rx="4" fill="#f3ece1" stroke="#963d2c" stroke-width="1.3"/>
<text x="593.0" y="465.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">0.12</text>
<text x="628" y="385.5" text-anchor="middle" font-size="16" fill="#6e6557" font-weight="400" >+</text>
<text x="668" y="331" text-anchor="middle" font-size="11" fill="#8c6a2a" font-weight="400" >b: biases</text>
<rect x="644" y="340" width="48" height="27" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="668.0" y="357.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">0.10</text>
<rect x="644" y="367" width="48" height="27" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="668.0" y="384.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">−0.04</text>
<rect x="644" y="394" width="48" height="27" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="668.0" y="411.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">0.21</text>
<rect x="644" y="421" width="48" height="27" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="668.0" y="438.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">⋮</text>
<text x="700" y="385.5" text-anchor="middle" font-size="16" fill="#6e6557" font-weight="400" >=</text>
<text x="742" y="331" text-anchor="middle" font-size="11" fill="#5f6c33" font-weight="400" >y: outputs</text>
<rect x="716" y="340" width="48" height="27" rx="4" fill="#eceadb" stroke="#5f6c33" stroke-width="1.3"/>
<text x="740.0" y="357.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">0.62</text>
<rect x="716" y="367" width="48" height="27" rx="4" fill="#eceadb" stroke="#5f6c33" stroke-width="1.3"/>
<text x="740.0" y="384.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">−1.07</text>
<rect x="716" y="394" width="48" height="27" rx="4" fill="#eceadb" stroke="#5f6c33" stroke-width="1.3"/>
<text x="740.0" y="411.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">0.38</text>
<rect x="716" y="421" width="48" height="27" rx="4" fill="#eceadb" stroke="#5f6c33" stroke-width="1.3"/>
<text x="740.0" y="438.5" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="400" font-family="ui-monospace,Menlo,monospace">⋮</text>
<text x="58" y="491" text-anchor="start" font-size="9.5" fill="#6e6557" font-weight="400" >Each output is its own ①-style neuron: all 256 inputs × that output's own weights + its own bias → one number.</text>
<text x="58" y="506" text-anchor="start" font-size="9.5" fill="#6e6557" font-weight="400" >So y₁ = 0.62 is exactly panel ① (from ALL of x, it does NOT line up with x₁); rows 2, 3, … are more outputs, each from the same 256 inputs.</text>
<text x="58" y="521" text-anchor="start" font-size="9.5" fill="#6e6557" font-weight="400" >A layer stacks MANY outputs: m of them (3 shown, as x shows a few of 256). So y and b each have m entries; m is the output size (e.g. 256 → 1,024), independent of the 256 inputs.</text>
<text x="58" y="536" text-anchor="start" font-size="9.5" fill="#6e6557" font-weight="400" >One token (256 numbers) goes IN → a NEW vector of m numbers comes OUT, not a single number, passed to the next layer. Only the final head → softmax gives next-token probabilities.</text>
<text x="58" y="557" text-anchor="start" font-size="12" fill="#231f18" font-weight="700" >Written compactly, the whole layer is  <tspan fill="#5f6c33">y</tspan> = <tspan fill="#8c6a2a">W</tspan><tspan fill="#963d2c">x</tspan> + <tspan fill="#8c6a2a">b</tspan>.</text>
<line x1="40" y1="575" x2="820" y2="575" stroke="#ddd4c2" stroke-width="1.5"/>
<text x="58" y="601" text-anchor="start" font-size="13.5" fill="#231f18" font-weight="700" >③ Zoom out: one such layer is a tiny slice of the whole model</text>
<rect x="62" y="621" width="94" height="44" rx="4" fill="#f3ece1" stroke="#963d2c" stroke-width="1.3"/>
<text x="109.0" y="641" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="700" >tokens</text>
<text x="109.0" y="655" text-anchor="middle" font-size="9.5" fill="#6e6557" font-weight="400" >input</text>
<line x1="157" y1="643.0" x2="167" y2="643.0" stroke="#6e6557" stroke-width="1.6" marker-end="url(#aA)"/>
<rect x="168" y="621" width="94" height="44" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="215.0" y="641" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="700" >Block 1</text>
<text x="215.0" y="655" text-anchor="middle" font-size="9.5" fill="#6e6557" font-weight="400" >attn + MLP</text>
<line x1="263" y1="643.0" x2="273" y2="643.0" stroke="#6e6557" stroke-width="1.6" marker-end="url(#aA)"/>
<rect x="274" y="621" width="94" height="44" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="321.0" y="641" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="700" >Block 2</text>
<text x="321.0" y="655" text-anchor="middle" font-size="9.5" fill="#6e6557" font-weight="400" >attn + MLP</text>
<line x1="369" y1="643.0" x2="379" y2="643.0" stroke="#6e6557" stroke-width="1.6" marker-end="url(#aA)"/>
<rect x="380" y="621" width="94" height="44" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="427.0" y="641" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="700" >Block 3</text>
<text x="427.0" y="655" text-anchor="middle" font-size="9.5" fill="#6e6557" font-weight="400" >attn + MLP</text>
<line x1="475" y1="643.0" x2="485" y2="643.0" stroke="#6e6557" stroke-width="1.6" marker-end="url(#aA)"/>
<rect x="486" y="621" width="94" height="44" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="533.0" y="641" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="700" >Block 4</text>
<text x="533.0" y="655" text-anchor="middle" font-size="9.5" fill="#6e6557" font-weight="400" >attn + MLP</text>
<line x1="581" y1="643.0" x2="591" y2="643.0" stroke="#6e6557" stroke-width="1.6" marker-end="url(#aA)"/>
<rect x="592" y="621" width="94" height="44" rx="4" fill="#f3ecd9" stroke="#8c6a2a" stroke-width="1.3"/>
<text x="639.0" y="648" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="700" >head</text>
<line x1="687" y1="643.0" x2="697" y2="643.0" stroke="#6e6557" stroke-width="1.6" marker-end="url(#aA)"/>
<rect x="698" y="621" width="94" height="44" rx="4" fill="#eceadb" stroke="#5f6c33" stroke-width="1.3"/>
<text x="745.0" y="641" text-anchor="middle" font-size="11.5" fill="#231f18" font-weight="700" >next token</text>
<text x="745.0" y="655" text-anchor="middle" font-size="9.5" fill="#6e6557" font-weight="400" >probs</text>
<text x="162.0" y="615" text-anchor="middle" font-size="9" fill="#6e6557" font-weight="400" >embed</text>
<rect x="271" y="618" width="100" height="50" rx="6" fill="none" stroke="#8c6a2a" stroke-width="2.4"/>
<text x="321.0" y="681" text-anchor="middle" font-size="10" fill="#8c6a2a" font-weight="400" >↑ a layer like ①② is one W in here</text>
<text x="58" y="703" text-anchor="start" font-size="10" fill="#6e6557" font-weight="400" >Each block's output vector feeds the next; only the head (then softmax) turns the last token's vector into next-token probabilities.</text>
<text x="58" y="721" text-anchor="start" font-size="10.5" fill="#6e6557" font-weight="400" >Of the ~3.24M parameters: ~56k embedding tables (each token's 256-number profile); ~3.16M the 4 blocks' shared W's; ~24k the head.</text>
<text x="58" y="739" text-anchor="start" font-size="11.5" fill="#231f18" font-weight="700" >So a token's 256 numbers are a tiny slice; the bulk is the model's shared weights, the same set applied to every token (fixed after training).</text>
</svg>'''

EMBED_SCATTER_SVG = r'''<svg viewBox="0 0 560 392" role="img" aria-label="Embedding space: tokens as points in 256-dimensional space (2 dimensions shown); animals cluster, function words and actions elsewhere.">
<defs><marker id="ar" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#6e6557"/></marker></defs>
<line x1="64" y1="330" x2="525" y2="330" stroke="#6e6557" stroke-width="1.3" marker-end="url(#ar)"/>
<line x1="64" y1="330" x2="64" y2="45" stroke="#6e6557" stroke-width="1.3" marker-end="url(#ar)"/>
<text x="290" y="352" text-anchor="middle" font-size="10.5" fill="#6e6557" font-weight="600" font-family="-apple-system,Segoe UI,sans-serif">Attribute A  (dimension 1) — loosely, &#8220;animal-ness&#8221; →</text>
<text x="32" y="190" transform="rotate(-90 32 190)" text-anchor="middle" font-size="10.5" fill="#6e6557" font-weight="600" font-family="-apple-system,sans-serif">Attribute B  (dimension 2) — loosely, &#8220;concreteness&#8221; ↑</text>
<text x="300" y="376" text-anchor="middle" font-size="9.5" fill="#6e6557" font-weight="400" font-family="-apple-system,Segoe UI,sans-serif">(2 of fox's 256 dimensions shown)</text>
<circle cx="420" cy="135" r="78" fill="none" stroke="#cfc5ae" stroke-width="1.3" stroke-dasharray="5 4"/>
<text x="420" y="51" text-anchor="middle" font-size="11" fill="#6e6557" font-weight="700" font-family="-apple-system,Segoe UI,sans-serif">animals</text>
<circle cx="395" cy="120" r="4" fill="#963d2c"/>
<text x="403" y="124" text-anchor="start" font-size="11.5" fill="#231f18" font-weight="600" font-family="-apple-system,Segoe UI,sans-serif">cat</text>
<circle cx="440" cy="140" r="4" fill="#963d2c"/>
<text x="448" y="144" text-anchor="start" font-size="11.5" fill="#231f18" font-weight="600" font-family="-apple-system,Segoe UI,sans-serif">fox</text>
<circle cx="405" cy="168" r="4" fill="#963d2c"/>
<text x="413" y="172" text-anchor="start" font-size="11.5" fill="#231f18" font-weight="600" font-family="-apple-system,Segoe UI,sans-serif">dog</text>
<circle cx="455" cy="108" r="4" fill="#963d2c"/>
<text x="463" y="112" text-anchor="start" font-size="11.5" fill="#231f18" font-weight="600" font-family="-apple-system,Segoe UI,sans-serif">wolf</text>
<circle cx="262" cy="200" r="52" fill="none" stroke="#cfc5ae" stroke-width="1.3" stroke-dasharray="5 4"/>
<text x="262" y="142" text-anchor="middle" font-size="11" fill="#6e6557" font-weight="700" font-family="-apple-system,Segoe UI,sans-serif">actions</text>
<circle cx="242" cy="190" r="4" fill="#963d2c"/>
<text x="250" y="194" text-anchor="start" font-size="11.5" fill="#231f18" font-weight="600" font-family="-apple-system,Segoe UI,sans-serif">ran</text>
<circle cx="277" cy="215" r="4" fill="#963d2c"/>
<text x="285" y="219" text-anchor="start" font-size="11.5" fill="#231f18" font-weight="600" font-family="-apple-system,Segoe UI,sans-serif">jumped</text>
<circle cx="150" cy="285" r="52" fill="none" stroke="#cfc5ae" stroke-width="1.3" stroke-dasharray="5 4"/>
<text x="150" y="227" text-anchor="middle" font-size="11" fill="#6e6557" font-weight="700" font-family="-apple-system,Segoe UI,sans-serif">function words</text>
<circle cx="130" cy="290" r="4" fill="#963d2c"/>
<text x="138" y="294" text-anchor="start" font-size="11.5" fill="#231f18" font-weight="600" font-family="-apple-system,Segoe UI,sans-serif">the</text>
<circle cx="173" cy="278" r="4" fill="#963d2c"/>
<text x="181" y="282" text-anchor="start" font-size="11.5" fill="#231f18" font-weight="600" font-family="-apple-system,Segoe UI,sans-serif">a</text>
<circle cx="128" cy="262" r="4" fill="#963d2c"/>
<text x="136" y="266" text-anchor="start" font-size="11.5" fill="#231f18" font-weight="600" font-family="-apple-system,Segoe UI,sans-serif">of</text>
</svg>'''

EMBED_HEATMAP_SVG = r'''<svg viewBox="0 0 560 268" role="img" aria-label="Embeddings as colored strips: each row a token, each column one of the 256 dimensions; fox cat dog similar, the differs.">
<text x="96" y="20" text-anchor="start" font-size="10.5" fill="#6e6557" font-weight="400" font-family="-apple-system,Segoe UI,sans-serif">each row = a token   ·   each column = one dimension / attribute (1, 2, 3, …, 256) →</text>
<text x="108.5" y="38" text-anchor="middle" font-size="8.5" fill="#6e6557" font-weight="400" font-family="-apple-system,Segoe UI,sans-serif">1</text>
<text x="135.5" y="38" text-anchor="middle" font-size="8.5" fill="#6e6557" font-weight="400" font-family="-apple-system,Segoe UI,sans-serif">2</text>
<text x="162.5" y="38" text-anchor="middle" font-size="8.5" fill="#6e6557" font-weight="400" font-family="-apple-system,Segoe UI,sans-serif">3</text>
<text x="405.5" y="38" text-anchor="middle" font-size="8.5" fill="#6e6557" font-weight="400" font-family="-apple-system,Segoe UI,sans-serif">256</text>
<text x="84" y="63.0" text-anchor="end" font-size="12.5" fill="#963d2c" font-weight="700" font-family="-apple-system,Segoe UI,sans-serif">fox</text>
<rect x="96" y="46" width="25" height="26" fill="rgb(223,83,83)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="123" y="46" width="25" height="26" fill="rgb(231,126,126)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="150" y="46" width="25" height="26" fill="rgb(191,206,239)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="177" y="46" width="25" height="26" fill="rgb(219,62,62)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="204" y="46" width="25" height="26" fill="rgb(105,140,217)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="231" y="46" width="25" height="26" fill="rgb(247,212,212)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="258" y="46" width="25" height="26" fill="rgb(235,148,148)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="285" y="46" width="25" height="26" fill="rgb(169,189,233)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="312" y="46" width="25" height="26" fill="rgb(227,105,105)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="339" y="46" width="25" height="26" fill="rgb(251,234,234)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="366" y="46" width="25" height="26" fill="rgb(126,156,222)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="393" y="46" width="25" height="26" fill="rgb(239,169,169)" stroke="#ddd4c2" stroke-width="0.8"/>
<text x="428" y="63.0" text-anchor="start" font-size="13" fill="#6e6557" font-weight="400" font-family="-apple-system,Segoe UI,sans-serif">⋯</text>
<text x="84" y="97.0" text-anchor="end" font-size="12.5" fill="#963d2c" font-weight="700" font-family="-apple-system,Segoe UI,sans-serif">cat</text>
<rect x="96" y="80" width="25" height="26" fill="rgb(227,105,105)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="123" y="80" width="25" height="26" fill="rgb(227,105,105)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="150" y="80" width="25" height="26" fill="rgb(212,222,244)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="177" y="80" width="25" height="26" fill="rgb(223,83,83)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="204" y="80" width="25" height="26" fill="rgb(126,156,222)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="231" y="80" width="25" height="26" fill="rgb(243,191,191)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="258" y="80" width="25" height="26" fill="rgb(239,169,169)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="285" y="80" width="25" height="26" fill="rgb(148,173,228)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="312" y="80" width="25" height="26" fill="rgb(231,126,126)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="339" y="80" width="25" height="26" fill="rgb(247,212,212)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="366" y="80" width="25" height="26" fill="rgb(148,173,228)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="393" y="80" width="25" height="26" fill="rgb(235,148,148)" stroke="#ddd4c2" stroke-width="0.8"/>
<text x="428" y="97.0" text-anchor="start" font-size="13" fill="#6e6557" font-weight="400" font-family="-apple-system,Segoe UI,sans-serif">⋯</text>
<text x="84" y="131.0" text-anchor="end" font-size="12.5" fill="#963d2c" font-weight="700" font-family="-apple-system,Segoe UI,sans-serif">dog</text>
<rect x="96" y="114" width="25" height="26" fill="rgb(219,62,62)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="123" y="114" width="25" height="26" fill="rgb(235,148,148)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="150" y="114" width="25" height="26" fill="rgb(169,189,233)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="177" y="114" width="25" height="26" fill="rgb(221,73,73)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="204" y="114" width="25" height="26" fill="rgb(116,148,220)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="231" y="114" width="25" height="26" fill="rgb(251,234,234)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="258" y="114" width="25" height="26" fill="rgb(233,137,137)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="285" y="114" width="25" height="26" fill="rgb(180,198,236)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="312" y="114" width="25" height="26" fill="rgb(225,94,94)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="339" y="114" width="25" height="26" fill="rgb(253,245,245)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="366" y="114" width="25" height="26" fill="rgb(105,140,217)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="393" y="114" width="25" height="26" fill="rgb(241,180,180)" stroke="#ddd4c2" stroke-width="0.8"/>
<text x="428" y="131.0" text-anchor="start" font-size="13" fill="#6e6557" font-weight="400" font-family="-apple-system,Segoe UI,sans-serif">⋯</text>
<text x="84" y="165.0" text-anchor="end" font-size="12.5" fill="#231f18" font-weight="700" font-family="-apple-system,Segoe UI,sans-serif">the</text>
<rect x="96" y="148" width="25" height="26" fill="rgb(126,156,222)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="123" y="148" width="25" height="26" fill="rgb(83,123,211)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="150" y="148" width="25" height="26" fill="rgb(227,105,105)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="177" y="148" width="25" height="26" fill="rgb(212,222,244)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="204" y="148" width="25" height="26" fill="rgb(235,148,148)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="231" y="148" width="25" height="26" fill="rgb(62,107,206)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="258" y="148" width="25" height="26" fill="rgb(191,206,239)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="285" y="148" width="25" height="26" fill="rgb(231,126,126)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="312" y="148" width="25" height="26" fill="rgb(148,173,228)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="339" y="148" width="25" height="26" fill="rgb(223,83,83)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="366" y="148" width="25" height="26" fill="rgb(247,212,212)" stroke="#ddd4c2" stroke-width="0.8"/>
<rect x="393" y="148" width="25" height="26" fill="rgb(105,140,217)" stroke="#ddd4c2" stroke-width="0.8"/>
<text x="428" y="165.0" text-anchor="start" font-size="13" fill="#6e6557" font-weight="400" font-family="-apple-system,Segoe UI,sans-serif">⋯</text>
<text x="96" y="190" text-anchor="start" font-size="10.5" fill="#231f18" font-weight="700" font-family="-apple-system,Segoe UI,sans-serif">fox, cat, dog → similar patterns (similar meaning).   "the" → different.</text>
<text x="238" y="223" text-anchor="end" font-size="9" fill="#6e6557" font-weight="400" font-family="-apple-system,Segoe UI,sans-serif">low</text>
<rect x="246" y="214" width="13" height="13" fill="rgb(40,90,200)" stroke="#ddd4c2" stroke-width="0.5"/>
<rect x="259" y="214" width="13" height="13" fill="rgb(83,123,211)" stroke="#ddd4c2" stroke-width="0.5"/>
<rect x="272" y="214" width="13" height="13" fill="rgb(126,156,222)" stroke="#ddd4c2" stroke-width="0.5"/>
<rect x="285" y="214" width="13" height="13" fill="rgb(170,190,234)" stroke="#ddd4c2" stroke-width="0.5"/>
<rect x="298" y="214" width="13" height="13" fill="rgb(213,223,245)" stroke="#ddd4c2" stroke-width="0.5"/>
<rect x="311" y="214" width="13" height="13" fill="rgb(255,255,255)" stroke="#ddd4c2" stroke-width="0.5"/>
<rect x="324" y="214" width="13" height="13" fill="rgb(247,212,212)" stroke="#ddd4c2" stroke-width="0.5"/>
<rect x="337" y="214" width="13" height="13" fill="rgb(239,169,169)" stroke="#ddd4c2" stroke-width="0.5"/>
<rect x="350" y="214" width="13" height="13" fill="rgb(231,126,126)" stroke="#ddd4c2" stroke-width="0.5"/>
<rect x="363" y="214" width="13" height="13" fill="rgb(223,83,83)" stroke="#ddd4c2" stroke-width="0.5"/>
<rect x="376" y="214" width="13" height="13" fill="rgb(214,40,40)" stroke="#ddd4c2" stroke-width="0.5"/>
<text x="395" y="223" text-anchor="start" font-size="9" fill="#6e6557" font-weight="400" font-family="-apple-system,Segoe UI,sans-serif">high</text>
</svg>'''

# Animated generation loop (§9). Six real steps of the v2 checkpoint continuing
# "Once upon a time" at temperature 0.8 — every number below was measured by
# docs/walkthrough/gen_generation_trace.py (seed 1); rerun it to regenerate them.
# Pure CSS/SMIL-free animation on a 21 s cycle; prefers-reduced-motion shows the
# final frame (full sentence + step 6's menu) as a static figure.
GENLOOP_SVG = r'''<svg viewBox="0 0 720 306" role="img" aria-label="Autoregressive generation, animated: the prompt Once upon a time grows one word-chunk at a time. At each of six steps the model's real top-4 next-chunk probabilities appear as bars, the sampled chunk is outlined and then appended to the sentence. Steps 1 to 5 pick the favourite (comma 87.5%, there 98.7%, was 99.1%, a 98.6%, little 81.5%); at step 6 the weighted die lands on boy at 13.9% instead of the favourite girl at 83.4%, finishing: Once upon a time, there was a little boy.">
<style>
.gl-anim{}
.gl-s1,.gl-s2,.gl-s3,.gl-s4,.gl-s5{opacity:0}
.gl-s6,.gl-m1,.gl-m2,.gl-m3,.gl-m4,.gl-m5,.gl-m6,.gl-t1,.gl-t2,.gl-t3,.gl-t4,.gl-t5,.gl-t6{opacity:1}
.gl-s1{animation:glw1 21s linear infinite}.gl-s2{animation:glw2 21s linear infinite}
.gl-s3{animation:glw3 21s linear infinite}.gl-s4{animation:glw4 21s linear infinite}
.gl-s5{animation:glw5 21s linear infinite}.gl-s6{animation:glw6 21s linear infinite}
.gl-m1{animation:glm1 21s linear infinite}.gl-m2{animation:glm2 21s linear infinite}
.gl-m3{animation:glm3 21s linear infinite}.gl-m4{animation:glm4 21s linear infinite}
.gl-m5{animation:glm5 21s linear infinite}.gl-m6{animation:glm6 21s linear infinite}
.gl-t1{animation:glt1 21s linear infinite}.gl-t2{animation:glt2 21s linear infinite}
.gl-t3{animation:glt3 21s linear infinite}.gl-t4{animation:glt4 21s linear infinite}
.gl-t5{animation:glt5 21s linear infinite}.gl-t6{animation:glt6 21s linear infinite}
@keyframes glw1{0%{opacity:0}1.4%{opacity:1}14.29%{opacity:1}15.24%{opacity:0}100%{opacity:0}}
@keyframes glw2{0%{opacity:0}15.24%{opacity:0}16.64%{opacity:1}29.52%{opacity:1}30.48%{opacity:0}100%{opacity:0}}
@keyframes glw3{0%{opacity:0}30.48%{opacity:0}31.88%{opacity:1}44.76%{opacity:1}45.71%{opacity:0}100%{opacity:0}}
@keyframes glw4{0%{opacity:0}45.71%{opacity:0}47.11%{opacity:1}59.99%{opacity:1}60.95%{opacity:0}100%{opacity:0}}
@keyframes glw5{0%{opacity:0}60.95%{opacity:0}62.35%{opacity:1}75.24%{opacity:1}76.19%{opacity:0}100%{opacity:0}}
@keyframes glw6{0%{opacity:0}76.19%{opacity:0}77.59%{opacity:1}100%{opacity:1}}
@keyframes glm1{0%{opacity:0}10.5%{opacity:0}11.9%{opacity:1}100%{opacity:1}}
@keyframes glm2{0%{opacity:0}25.74%{opacity:0}27.14%{opacity:1}100%{opacity:1}}
@keyframes glm3{0%{opacity:0}40.98%{opacity:0}42.38%{opacity:1}100%{opacity:1}}
@keyframes glm4{0%{opacity:0}56.21%{opacity:0}57.61%{opacity:1}100%{opacity:1}}
@keyframes glm5{0%{opacity:0}71.45%{opacity:0}72.85%{opacity:1}100%{opacity:1}}
@keyframes glm6{0%{opacity:0}86.69%{opacity:0}88.09%{opacity:1}100%{opacity:1}}
@keyframes glt1{0%{opacity:0}12.4%{opacity:0}13.8%{opacity:1}100%{opacity:1}}
@keyframes glt2{0%{opacity:0}27.64%{opacity:0}29.04%{opacity:1}100%{opacity:1}}
@keyframes glt3{0%{opacity:0}42.88%{opacity:0}44.28%{opacity:1}100%{opacity:1}}
@keyframes glt4{0%{opacity:0}58.11%{opacity:0}59.51%{opacity:1}100%{opacity:1}}
@keyframes glt5{0%{opacity:0}73.35%{opacity:0}74.75%{opacity:1}100%{opacity:1}}
@keyframes glt6{0%{opacity:0}88.59%{opacity:0}89.99%{opacity:1}100%{opacity:1}}
@media (prefers-reduced-motion: reduce){.gl-anim{animation:none !important}}
</style>
<text x="30" y="28" font-size="14.5" font-weight="700" fill="#231f18" font-family="ui-monospace,Menlo,monospace" xml:space="preserve">Once upon a time<tspan class="gl-anim gl-t1" fill="#963d2c">,</tspan><tspan class="gl-anim gl-t2" fill="#963d2c"> there</tspan><tspan class="gl-anim gl-t3" fill="#963d2c"> was</tspan><tspan class="gl-anim gl-t4" fill="#963d2c"> a</tspan><tspan class="gl-anim gl-t5" fill="#963d2c"> little</tspan><tspan class="gl-anim gl-t6" fill="#963d2c"> boy</tspan></text>
<text x="30" y="48" font-size="10.5" fill="#6e6557">the story so far — after every pick, the whole line is fed back in and the menu below is re-scored from scratch</text>
<text x="690" y="76" text-anchor="end" font-size="10" fill="#998f7d" font-family="ui-monospace,Menlo,monospace">real scores · temperature 0.8</text>
<g class="gl-anim gl-s1">
<text x="30" y="76" font-size="11" fill="#998f7d" font-family="ui-monospace,Menlo,monospace">step 1 of 6 — the menu for what comes next</text>
<text x="212" y="102" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">,</text>
<rect x="222" y="88" width="341" height="20" rx="4" fill="#963d2c"/>
<text x="571" y="102" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">87.5%</text>
<text x="212" y="131" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">there</text>
<rect x="222" y="117" width="49" height="20" rx="4" fill="#963d2c"/>
<text x="279" y="131" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">12.5%</text>
<text x="212" y="160" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">in</text>
<rect x="222" y="146" width="2" height="20" fill="#963d2c"/>
<text x="232" y="160" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">&lt;0.1%</text>
<text x="212" y="189" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">.</text>
<rect x="222" y="175" width="2" height="20" fill="#963d2c"/>
<text x="232" y="189" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">&lt;0.1%</text>
<text x="212" y="218" text-anchor="end" font-size="11" font-style="italic" fill="#6e6557">everything else (~8,000 chunks)</text>
<rect x="222" y="204" width="2" height="20" fill="#cfc5ae"/>
<text x="232" y="218" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">&lt;0.1%</text>
<g class="gl-anim gl-m1"><rect x="16" y="84" width="658" height="28" rx="5" fill="none" stroke="#963d2c" stroke-width="1.3"/><text x="24" y="102" font-size="12" fill="#963d2c" font-weight="700">&#9656;</text><text x="212" y="102" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#963d2c">,</text></g>
</g>
<g class="gl-anim gl-s2">
<text x="30" y="76" font-size="11" fill="#998f7d" font-family="ui-monospace,Menlo,monospace">step 2 of 6 — the menu for what comes next</text>
<text x="212" y="102" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">there</text>
<rect x="222" y="88" width="385" height="20" rx="4" fill="#963d2c"/>
<text x="615" y="102" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">98.7%</text>
<text x="212" y="131" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">in</text>
<rect x="222" y="117" width="3" height="20" fill="#963d2c"/>
<text x="233" y="131" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">0.7%</text>
<text x="212" y="160" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">a</text>
<rect x="222" y="146" width="2" height="20" fill="#963d2c"/>
<text x="232" y="160" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">0.6%</text>
<text x="212" y="189" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">the</text>
<rect x="222" y="175" width="2" height="20" fill="#963d2c"/>
<text x="232" y="189" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">&lt;0.1%</text>
<text x="212" y="218" text-anchor="end" font-size="11" font-style="italic" fill="#6e6557">everything else (~8,000 chunks)</text>
<rect x="222" y="204" width="2" height="20" fill="#cfc5ae"/>
<text x="232" y="218" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">&lt;0.1%</text>
<g class="gl-anim gl-m2"><rect x="16" y="84" width="658" height="28" rx="5" fill="none" stroke="#963d2c" stroke-width="1.3"/><text x="24" y="102" font-size="12" fill="#963d2c" font-weight="700">&#9656;</text><text x="212" y="102" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#963d2c">there</text></g>
</g>
<g class="gl-anim gl-s3">
<text x="30" y="76" font-size="11" fill="#998f7d" font-family="ui-monospace,Menlo,monospace">step 3 of 6 — the menu for what comes next</text>
<text x="212" y="102" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">was</text>
<rect x="222" y="88" width="387" height="20" rx="4" fill="#963d2c"/>
<text x="617" y="102" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">99.1%</text>
<text x="212" y="131" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">were</text>
<rect x="222" y="117" width="2" height="20" fill="#963d2c"/>
<text x="232" y="131" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">0.6%</text>
<text x="212" y="160" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">lived</text>
<rect x="222" y="146" width="2" height="20" fill="#963d2c"/>
<text x="232" y="160" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">0.3%</text>
<text x="212" y="189" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">is</text>
<rect x="222" y="175" width="2" height="20" fill="#963d2c"/>
<text x="232" y="189" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">&lt;0.1%</text>
<text x="212" y="218" text-anchor="end" font-size="11" font-style="italic" fill="#6e6557">everything else (~8,000 chunks)</text>
<rect x="222" y="204" width="2" height="20" fill="#cfc5ae"/>
<text x="232" y="218" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">&lt;0.1%</text>
<g class="gl-anim gl-m3"><rect x="16" y="84" width="658" height="28" rx="5" fill="none" stroke="#963d2c" stroke-width="1.3"/><text x="24" y="102" font-size="12" fill="#963d2c" font-weight="700">&#9656;</text><text x="212" y="102" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#963d2c">was</text></g>
</g>
<g class="gl-anim gl-s4">
<text x="30" y="76" font-size="11" fill="#998f7d" font-family="ui-monospace,Menlo,monospace">step 4 of 6 — the menu for what comes next</text>
<text x="212" y="102" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">a</text>
<rect x="222" y="88" width="385" height="20" rx="4" fill="#963d2c"/>
<text x="615" y="102" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">98.6%</text>
<text x="212" y="131" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">an</text>
<rect x="222" y="117" width="5" height="20" fill="#963d2c"/>
<text x="235" y="131" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">1.4%</text>
<text x="212" y="160" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">one</text>
<rect x="222" y="146" width="2" height="20" fill="#963d2c"/>
<text x="232" y="160" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">&lt;0.1%</text>
<text x="212" y="189" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">no</text>
<rect x="222" y="175" width="2" height="20" fill="#963d2c"/>
<text x="232" y="189" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">&lt;0.1%</text>
<text x="212" y="218" text-anchor="end" font-size="11" font-style="italic" fill="#6e6557">everything else (~8,000 chunks)</text>
<rect x="222" y="204" width="2" height="20" fill="#cfc5ae"/>
<text x="232" y="218" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">&lt;0.1%</text>
<g class="gl-anim gl-m4"><rect x="16" y="84" width="658" height="28" rx="5" fill="none" stroke="#963d2c" stroke-width="1.3"/><text x="24" y="102" font-size="12" fill="#963d2c" font-weight="700">&#9656;</text><text x="212" y="102" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#963d2c">a</text></g>
</g>
<g class="gl-anim gl-s5">
<text x="30" y="76" font-size="11" fill="#998f7d" font-family="ui-monospace,Menlo,monospace">step 5 of 6 — the menu for what comes next</text>
<text x="212" y="102" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">little</text>
<rect x="222" y="88" width="318" height="20" rx="4" fill="#963d2c"/>
<text x="548" y="102" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">81.5%</text>
<text x="212" y="131" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">big</text>
<rect x="222" y="117" width="23" height="20" rx="4" fill="#963d2c"/>
<text x="253" y="131" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">5.9%</text>
<text x="212" y="160" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">boy</text>
<rect x="222" y="146" width="12" height="20" rx="4" fill="#963d2c"/>
<text x="242" y="160" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">3.0%</text>
<text x="212" y="189" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">girl</text>
<rect x="222" y="175" width="7" height="20" rx="4" fill="#963d2c"/>
<text x="237" y="189" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">1.7%</text>
<text x="212" y="218" text-anchor="end" font-size="11" font-style="italic" fill="#6e6557">everything else (~8,000 chunks)</text>
<rect x="222" y="204" width="31" height="20" rx="4" fill="#cfc5ae"/>
<text x="261" y="218" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">7.9%</text>
<g class="gl-anim gl-m5"><rect x="16" y="84" width="658" height="28" rx="5" fill="none" stroke="#963d2c" stroke-width="1.3"/><text x="24" y="102" font-size="12" fill="#963d2c" font-weight="700">&#9656;</text><text x="212" y="102" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#963d2c">little</text></g>
</g>
<g class="gl-anim gl-s6">
<text x="30" y="76" font-size="11" fill="#998f7d" font-family="ui-monospace,Menlo,monospace">step 6 of 6 — the menu for what comes next</text>
<text x="212" y="102" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">girl</text>
<rect x="222" y="88" width="325" height="20" rx="4" fill="#963d2c"/>
<text x="555" y="102" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">83.4%</text>
<text x="212" y="131" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">boy</text>
<rect x="222" y="117" width="54" height="20" rx="4" fill="#963d2c"/>
<text x="284" y="131" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">13.9%</text>
<text x="212" y="160" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">bird</text>
<rect x="222" y="146" width="2" height="20" fill="#963d2c"/>
<text x="232" y="160" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">0.6%</text>
<text x="212" y="189" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#231f18">bunny</text>
<rect x="222" y="175" width="2" height="20" fill="#963d2c"/>
<text x="232" y="189" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">0.6%</text>
<text x="212" y="218" text-anchor="end" font-size="11" font-style="italic" fill="#6e6557">everything else (~8,000 chunks)</text>
<rect x="222" y="204" width="6" height="20" rx="4" fill="#cfc5ae"/>
<text x="236" y="218" font-size="11" fill="#6e6557" font-family="ui-monospace,Menlo,monospace">1.5%</text>
<g class="gl-anim gl-m6"><rect x="16" y="113" width="658" height="28" rx="5" fill="none" stroke="#963d2c" stroke-width="1.3"/><text x="24" y="131" font-size="12" fill="#963d2c" font-weight="700">&#9656;</text><text x="212" y="131" text-anchor="end" font-size="12" font-family="ui-monospace,Menlo,monospace" fill="#963d2c">boy</text></g>
</g>
<text x="30" y="244" font-size="10.5" fill="#998f7d" font-family="ui-monospace,Menlo,monospace">outlined row = the weighted die&#8217;s pick — watch it join the line above</text>
<text x="30" y="270" font-size="10.5" fill="#6e6557">Measured, not staged: the model&#8217;s real menus — the upgraded word-chunk checkpoint (§11–14) continuing the prompt at</text>
<text x="30" y="286" font-size="10.5" fill="#6e6557">temperature 0.8. Five rolls land on the favourite; then step 6&#8217;s die picks &#8201;boy (13.9%) over &#8201;girl (83.4%). That&#8217;s</text>
<text x="30" y="302" font-size="10.5" fill="#6e6557">sampling: a loaded die, not a lookup. (§9&#8217;s character model runs this identical loop, one letter at a time.)</text>
</svg>'''

SECTIONS = [

# ---------------------------------------------------------------- ORIENTATION --
{
 "id": "what", "num": "0", "title": "What we're actually building",
 "part": "Orientation",
 "part_banner": "Stage 1 · Orientation",
 "blocks": [
  ("prose", r"""
<p>This page is the <strong>build</strong>. For <em>what</em> a model is and how it works (next-token
prediction, tokens, embeddings, attention, training) see <a href="../ideas/">Part 0 · Concepts</a>
(no code); we lean on it throughout. The one thing worth restating here: a real model is the
<em>same</em> idea at enormous scale, so building a <em>tiny</em> one where every part is visible teaches
the shape of the whole field.</p>
<p>We do it in <strong>two passes</strong>, which separates <em>knowing the parts</em> from
<em>knowing what matters</em>:</p>
"""),
  ("table", r"""
<table>
<thead><tr><th>Pass</th><th>What it does</th><th>Result</th></tr></thead>
<tbody>
<tr><td>Notebook 01 (<em>from scratch</em>)</td>
    <td>The simplest possible GPT, working one <strong>character</strong> at a time, built
    from raw parts so every moving piece is visible.</td>
    <td>English-shaped <strong>gibberish</strong>, on purpose. The goal is transparency, not quality.</td></tr>
<tr><td>Notebook 02 (<em>tuned</em>)</td>
    <td>Same architecture, plus the handful of upgrades that genuinely move quality
    (chiefly: working in word-chunks, not letters).</td>
    <td>Recognisable <strong>little stories</strong>, the ceiling of a from-scratch model on a laptop.</td></tr>
</tbody></table>
"""),
  ("callout", "key", "Why two passes", r"""
<p>The jump from gibberish to coherent stories (same architecture, a few changes) is the
most instructive thing in the project. It separates <em>knowing the parts</em> from
<em>knowing what matters</em>. We build the parts first (the from-scratch pass), then turn the dials (the tuned pass).</p>
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
 "part_banner": "Stage 2 · Building it from scratch (notebook 01)",
 "blocks": [
  ("prose", r"""
<p>Every program starts by laying its tools on the bench. Here we load the array library, the
neural-network building blocks, and the optimizer (the part that will adjust the model as it
learns). One line prints the compute device, confirming the Mac's GPU is in play.</p>
"""),
  ("code", "01", "MLX device:"),
  ("gloss", r"""
<p><b>Reading it:</b> the <code>import</code> lines bring in pre-written toolkits.
<code>np</code> is <strong>NumPy</strong>, Python's classic, decades-old library for arrays of
numbers, the workhorse under most of scientific computing (here it does a little data prep on the
CPU). <code>mx</code> is <strong>MLX</strong>, Apple's array library that runs on the Mac's GPU;
it's deliberately NumPy-like, so the two look almost identical in use. <code>nn</code> holds the
neural-net building blocks (layers and such), and <code>optim</code> is the optimizer, the part
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
<strong>tokenisation</strong>, a fixed dictionary that maps text to whole numbers and back.
Notebook 01 uses the simplest scheme imaginable: <strong>one number per character</strong>.
Every distinct character it sees (every letter, space, comma) gets its own id. It's
inefficient, but maximally transparent: you can see <em>exactly</em> what the model sees.</p>
<p>(<a href="../ideas/#tokens">Part 0</a> described a token as a word or word-piece; here we start one notch simpler, one token per <em>character</em>, for maximum transparency, then switch to word-chunks in <a href="#bpe">§11</a>.)</p>
<p>The text itself is <strong>TinyStories</strong>: thousands of very simple children's
stories, written with a small vocabulary on purpose, so that a small model can actually learn
coherent English from them.</p>
"""),
  ("code", "01", "N_STORIES = 4000", "Stream a few thousand stories (no full download)."),
  ("gloss", r"""
<p><b>Reading it:</b> <code>N_STORIES = 4000</code> sets how many stories to grab. The
<code>try:</code> / <code>except:</code> pair is a safety net (&ldquo;<em>attempt</em> this;
if anything goes wrong, do that instead&rdquo;) so the notebook never hard-fails if you happen
to be offline.</p>
<ul>
<li><code>load_dataset(..., streaming=True)</code>: open the TinyStories dataset as a
<b>stream</b>: pull stories one at a time on demand, rather than downloading the whole thing.</li>
<li>the <code>for ... in ds:</code> loop walks through the stream, tidies each story
(<code>.strip()</code> trims stray whitespace) and adds it to a growing <code>stories</code> list.
<code>if len(stories) >= N_STORIES: break</code> means &ldquo;once we have 4,000, stop.&rdquo;</li>
<li><code>text = "\n\n".join(stories)</code> glues all the stories into one big string, with a
blank line between each. That single string is the raw material everything downstream learns from.</li>
<li>the <code>except</code> branch only runs if the download failed; it swaps in a tiny
built-in corpus so the rest of the notebook still works.</li>
</ul>
<p>(The &ldquo;unauthenticated requests&rdquo; warning you'll see in the output below is
harmless: the dataset is public and needs no login; setting a token just lifts rate limits.)</p>
"""),
  ("output", "01", "N_STORIES = 4000", "what it prints", 600),
  ("prose", r"""
<p>Now we build the dictionary and convert the entire corpus into one long ribbon of integers.
The last 10% is held back as a <strong>validation set</strong> (text the model never trains
on) which later lets us tell genuine learning apart from mere memorising.</p>
"""),
  ("code", "01", "chars = sorted(set(text))"),
  ("gloss", r"""
<p><b>Line by line:</b></p>
<ul>
<li><code>chars = sorted(set(text))</code> finds every <em>distinct</em> character and puts
them in a fixed order. That ordered list <em>is</em> the vocabulary.</li>
<li><code>stoi</code> / <code>itos</code> are two lookup tables: <b>s</b>tring-<b>to</b>-<b>i</b>nteger
and back. (&ldquo;<code>a</code> is 27,&rdquo; &ldquo;27 is <code>a</code>.&rdquo;)</li>
<li><code>encode</code> / <code>decode</code> are small recipes that run those lookups over a
whole string. Encode turns text into numbers; decode turns numbers back into text.</li>
<li><code>train_data, val_data</code> split the encoded ribbon 90/10. The model studies the
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
windows together (a &ldquo;batch&rdquo;) lets the GPU practise on all of them simultaneously,
which is what makes training fast.</p>
"""),
  ("callout", "aside", "Why &ldquo;shifted by one&rdquo; is clever", r"""
<p>It means we never have to label data by hand. The text <em>is</em> its own answer key:
the next character is always sitting right there. This is why language models can train on raw
text from the internet: the supervision is free.</p>
"""),
 ],
},

{
 "id": "knobs", "num": "4", "title": "The dials (hyperparameters)",
 "blocks": [
  ("prose", r"""
<p>Before building the model we choose its size and how hard it will train. These are
<strong>hyperparameters</strong>: settings <em>we</em> pick, as opposed to the millions of
numbers the model will learn on its own. A founding principle of this lab is &ldquo;no magic
numbers,&rdquo; so each one carries a note on what it does and which way to push it.</p>
"""),
  ("code", "01", "block_size = 128"),
  ("gloss", r"""
<p>The four shape dials decide capacity: <code>block_size</code> is how far back the model can
see; <code>n_embd</code> is how many numbers describe each token: that list of numbers is the
token's <strong>vector</strong> (a vector being simply an ordered list of numbers, e.g.
<code>[0.31, -1.20, 0.05, …]</code>) and <code>n_embd</code> (256) is how long it is (the
token's &ldquo;richness&rdquo;); <code>n_head</code> is how many relationships attention tracks
in parallel; <code>n_layer</code>
is how many times the whole reasoning block is stacked (depth). The training dials
(<code>batch_size</code>, <code>learning_rate</code>, <code>max_steps</code>) decide how
steadily and how long it learns. Bigger or longer is generally better and always slower; the
art is the balance.</p>
"""),
 ],
},

{
 "id": "attention", "num": "5", "title": "Attention: the heart of it",
 "blocks": [
  ("prose", r"""
<p>This is the one idea that makes a transformer a transformer. Everything else is plumbing.</p>
<p><strong>The intuition.</strong> To predict the next word, a position needs to pull in
relevant context from earlier words, but <em>which</em> earlier words matters, and it depends
on the sentence. In &ldquo;the dragon looked at the boy and <u>it</u>…&rdquo;, the word
&ldquo;it&rdquo; should pay attention to &ldquo;dragon.&rdquo; <strong>Attention</strong> is
the mechanism that lets every position decide, on the fly, how much to listen to each earlier
position.</p>
<p>The standard analogy is a <em>search</em>. Each token emits three things:</p>
<ul>
<li>a <strong>query</strong>: &ldquo;here's what I'm looking for,&rdquo;</li>
<li>a <strong>key</strong>: &ldquo;here's what I'm about,&rdquo; and</li>
<li>a <strong>value</strong>: &ldquo;here's what I'll hand over if you attend to me.&rdquo;</li>
</ul>
<p>A token compares its query against every earlier token's key. Good matches get high
attention; the token then takes a weighted blend of those tokens' values. Strong match → big
say in the blend. That blend is how information moves between positions.</p>
"""),
  ("callout", "key", "Causal = no peeking", r"""
<p>When predicting the next character, a token may only look <em>backward</em>. If it could see
the future, the &ldquo;guess the next character&rdquo; game would be trivial: it would just
read the answer. We enforce this with a <strong>mask</strong> that blocks every forward-looking
connection. This is what the &ldquo;causal&rdquo; in <em>causal self-attention</em> means.</p>
"""),
  ("code", "01", "def causal_mask(T):", "The mask, then attention itself."),
  ("gloss", r"""
<p><b>The mask</b> (<code>causal_mask</code>) builds a grid where allowed (past) connections
are 0 and forbidden (future) ones are a huge negative number. Added to the raw scores, those
−1,000,000,000 entries become effectively zero probability after the next step: future tokens
are silenced.</p>
<p><b>Inside the attention</b> (<code>__call__</code>), reading the important lines:</p>
<ul>
<li><code>q, k, v = mx.split(self.c_attn(x), 3, …)</code>: one matrix multiply produces all
three vectors (query, key, value) for every token at once, then splits them apart.</li>
<li>the <code>reshape</code>/<code>transpose</code> lines split the work across several
attention <em>heads</em>, so the model can track multiple kinds of relationship in parallel
(one head might follow grammar, another who-did-what).</li>
<li><code>scores = q @ transpose(k) … + mask</code> compares every query against every key
(that's the match score), scales for stability, and adds the mask to block the future.</li>
<li><code>weights = mx.softmax(scores)</code> turns raw scores into clean percentages that sum
to 100% across the allowed past.</li>
<li><code>out = weights @ v</code> is the weighted blend of values. <em>This single line is
where information actually flows between positions.</em></li>
</ul>
"""),
  ("callout", "math", "For the curious: the actual formula", r"""
<p>Everything above is one compact equation. For queries <code>Q</code>, keys <code>K</code>,
and values <code>V</code>:</p>
<div class="formula">Attention(Q, K, V) = softmax( (Q · Kᵀ) / √d + mask ) · V</div>
<p><code>Q · Kᵀ</code> scores every query against every key. Dividing by <code>√d</code> (the
square root of the head size) keeps those scores from growing too large as the model widens.
<code>softmax</code> normalises each row into probabilities; the <code>mask</code> adds −∞ to
future positions so they vanish. Multiplying by <code>V</code> blends the values by those
probabilities. The code above implements exactly this, plus the bookkeeping to run several
attention heads in parallel.</p>
"""),
 ],
},

{
 "id": "block", "num": "6", "title": "The block, and the whole model",
 "blocks": [
  ("prose", r"""
<p>Attention gathers information across positions. The other half of a transformer block is a
small <strong>MLP</strong>: two linear layers with a nonlinear &ldquo;bend&rdquo; (a GELU
activation) between them, applied to each position on its own, giving the model room to
&ldquo;think&rdquo; about what attention just collected. A <strong>block</strong> is simply:
attention, then MLP. A GPT is just this block stacked <code>n_layer</code> times.</p>
<p>Two supporting tricks make deep stacks trainable, and they're worth naming because they're
everywhere in modern models:</p>
<ul>
<li><strong>Residual connections</strong> (<code>x = x + sublayer(x)</code>). Instead of
replacing its input, each sub-layer <em>adds an adjustment</em> to it. This keeps a clean
signal flowing through even a deep stack, which is what makes deep networks learnable at all.</li>
<li><strong>LayerNorm</strong>: a normalisation step that keeps the numbers in a sane range so
the maths stays stable.</li>
</ul>
"""),
  ("prose", r"""
<p>Almost all of a block is two operations: a <strong>linear layer</strong> (<code>y = Wx + b</code>,
a weighted sum) and a nonlinear <strong>activation</strong> (a &ldquo;bend,&rdquo; GELU here). Stacked
with attention, an <em>embedding</em> at the bottom and a <em>head</em> at the top, that's the whole
network. The <em>why</em>, with the diagrams (what a linear layer computes, what an embedding is, how the
256 numbers form a &ldquo;meaning space&rdquo;) is in <a href="../ideas/#linear">Part 0 · Concepts</a>.
Here we build the block in code.</p>
"""),
  ("code", "01", "class Block(nn.Module):", "One block, then the full GPT assembled from blocks."),
  ("gloss", r"""
<p><b>The block</b> is the two-line heart: <code>x = x + self.attn(self.ln1(x), mask)</code>
(normalise, attend, add back) then <code>x = x + self.mlp(self.ln2(x))</code> (normalise,
think, add back). That &ldquo;add back&rdquo; is the residual connection.</p>
<p><b>The full GPT</b> wires the ends on:</p>
<ul>
<li><code>self.tok</code> is an <b>embedding</b> table turning each token id into a vector of
<code>n_embd</code> learnable numbers (its meaning, to be discovered during training).</li>
<li><code>self.pos</code> is a second embedding for <em>position</em>, because attention has no
built-in sense of order; we must tell it where each token sits.</li>
<li><code>self.blocks</code> is the stack of transformer blocks, run in sequence.</li>
<li><code>self.head</code> is a final layer that turns each position's vector into a
<strong>score for every possible next character</strong>. Those scores are called
<em>logits</em>; they're the model's raw opinion about what comes next.</li>
</ul>
<p>The print line counts the model's learnable numbers, its <strong>parameters</strong>. This
tiny one has about 3.2 million. (Frontier models have hundreds of <em>billions</em>: same
parts, more of them.)</p>
<p>Running an input all the way through these layers to produce the logits (that whole
left-to-right journey, <code>model(idx)</code>) is the model's <strong>forward pass</strong>
(&ldquo;forward propagation&rdquo;). Right now it produces nonsense, because the weights are
random. The next section is about fixing that, and the forward pass becomes step one of the
loop that does it.</p>
"""),
  ("output", "01", "class Block(nn.Module):", "what it prints"),
  ("prose", r"""
<h3>Our model, by the numbers</h3>
<p>So how big is the thing we just built? (&ldquo;How many neurons?&rdquo; has no clean answer for
a transformer: the honest measures are its <em>width</em>, its <em>depth</em>, and its
<em>parameter count</em>.)</p>
"""),
  ("table", r"""
<table>
<thead><tr><th>Property</th><th>Notebook 01 (this model)</th></tr></thead>
<tbody>
<tr><td>Transformer blocks, the depth (<code>n_layer</code>)</td><td>4</td></tr>
<tr><td>Width, numbers describing each token (<code>n_embd</code>)</td><td>256</td></tr>
<tr><td>Attention heads (<code>n_head</code>)</td><td>8</td></tr>
<tr><td>MLP hidden units per block (4 × width)</td><td>1,024</td></tr>
<tr><td><b>Total learnable parameters</b> (every <code>W</code> and <code>b</code>)</td><td><b>≈ 3.24 million</b></td></tr>
</tbody></table>
"""),
  ("prose", r"""
<p>Where do those 3.24 million <strong>parameters</strong> live? Almost all (~3.16 million) are
in the four blocks' <code>Wx + b</code> layers; only ~56k in the two embedding tables and ~24k in
the output head. (Notebook 02 scales every row up to 6 blocks, width 384, ≈17 million, and that
extra capacity is much of what makes its writing better.)</p>
<p>Two things about that number. First, <strong>it <em>is</em> the model's &ldquo;size&rdquo;</strong>,
the same count meant by &ldquo;a 7-billion-parameter model&rdquo; (distinct from the file size on
disk, which is roughly the count × a few bytes per number). Second, <strong>who picks those millions
of values? Not us.</strong> We choose the architecture and the count, and start them as small random
numbers; <em>training</em> then sets every value by gradient descent, nudging each toward whatever
lowers the loss. So the <em>process</em> is no black box; it's the loop in the next section. What
stays opaque is what any <em>single</em> parameter <em>means</em>: the knowledge is smeared across
all of them, not stored in readable slots. We know precisely how they're set; we mostly can't read
them, which is the open research field of <strong>interpretability</strong>.</p>
"""),
 ],
},

{
 "id": "train", "num": "7", "title": "Training: making the guesses less wrong",
 "blocks": [
  ("prose", r"""
<p>A freshly built model is random; its guesses are no better than chance. <strong>Training</strong> is
the loop that fixes that: <em>measure</em> how wrong each guess is (the <strong>loss</strong>, read it as
&ldquo;surprise&rdquo;), then <em>nudge</em> every parameter a little to lower it (<strong>gradient
descent</strong>). The <em>why</em> (loss, gradients, backpropagation, the downhill-in-a-landscape
picture) is in <a href="../ideas/#learn">Part 0 · Concepts</a>. Here is that loop, in code.</p>
"""),
  ("code", "01", "optimizer = optim.AdamW(learning_rate=learning_rate)",
   "The loss function, then the training loop."),
  ("gloss", r"""
<p><b>The loop is four steps, and every one is a line of code</b> (the
<code>for step in range(...)</code> block, plus the <code>loss_fn</code> above it):</p>
<ol>
<li><b>Forward pass</b>: <code>logits = model(x)</code> (inside <code>loss_fn</code>). Run the
batch of windows through the network to get its predictions. This is the same forward pass you
met when we built the model.</li>
<li><b>Loss</b>: <code>cross_entropy(...)</code>. Score how wrong those predictions are, the
surprise, one number.</li>
<li><b>Backward pass</b>: <code>loss, grads = loss_and_grad(model, x, y)</code>. Work backwards
through the network to get the <b>gradient</b> for every parameter: which way to nudge each one
to lower the loss. Doing this efficiently, end to end, is <b>backpropagation</b>, the central
algorithm of deep learning. (One call returns both the loss and all the gradients.)</li>
<li><b>Gradient-descent step</b>: <code>optimizer.update(model, grads)</code>. Take one small
step downhill, every parameter at once. The step size is the <code>learning_rate</code>.</li>
</ol>
<p><code>mx.eval(...)</code> just tells the GPU to actually run all of that now (MLX is lazy by
default). Repeat a couple of thousand times: each pass the model is microscopically less wrong,
and in aggregate, language emerges.</p>
"""),
  ("output", "01", "optimizer = optim.AdamW(learning_rate=learning_rate)",
   "watching it learn (loss falling)"),
  ("prose", r"""
<p>Read that output top to bottom: the loss starts near the &ldquo;knows nothing&rdquo;
baseline (~4.5) and falls fast to ~2.3 as the model picks up the statistics of English. The
<strong>validation</strong> loss falls alongside the training loss: proof it's learning the
<em>language</em>, not just memorising these particular stories.</p>
"""),
 ],
},

{
 "id": "curve", "num": "8", "title": "The loss curve: the single most important plot",
 "blocks": [
  ("prose", r"""
<p>This plot has a name: the <strong>loss curve</strong> (sometimes <em>learning curve</em>). It
is the loss from the last section, tracked across the whole training run, so don't confuse it
with the loss <em>function</em>: the <em>function</em> is the formula that scores a single batch;
the <em>curve</em> is that score plotted step after step. Reading it is how every practitioner
judges the health of a run at a glance. The <strong style="color:#84493a">blue</strong> line is
the training loss; the <strong style="color:#b06a2c">orange</strong> line (with dots) is the
validation loss; the grey dashed line is the &ldquo;knows nothing&rdquo; baseline.</p>
"""),
  ("figure", "loss_curve.png", "Notebook 01: both losses falling together toward the floor for a model this size."),
  ("gloss", r"""
<p><b>How to read it:</b> a healthy run drops fast, then flattens. The crucial signal is the
gap between the two lines. While validation loss keeps falling, the model is genuinely
<b>learning</b>. If validation loss ever turned <em>upward</em> while training loss kept
dropping, that widening gap would be <b>overfitting</b>: the model memorising its study
material instead of learning the general pattern. Here both fall together: no overfitting, just
the natural floor for a model this small.</p>
"""),
 ],
},

{
 "id": "generate", "num": "9", "title": "Generating text, and the honest result",
 "blocks": [
  ("prose", r"""
<p>Now we let it write. Generation is a loop: feed in a prompt, look at the model's scores for
the <em>next</em> character, turn them into probabilities, and <strong>sample</strong> one.
Append it, then feed the whole thing back in and repeat. This one-step-at-a-time process is
called <strong>autoregressive</strong> generation, and it's exactly how the largest models
write too.</p>
"""),
  ("diagram", GENLOOP_SVG,
   "The loop, replaying live: score the menu, roll the weighted die, append the pick, feed the whole "
   "line back in. Every probability shown is real, and so is the ending &mdash; reproduce the trace with "
   "<code>docs/walkthrough/gen_generation_trace.py</code>."),
  ("code", "01", "def generate(prompt, n_new=400", "Predict one character, append, repeat."),
  ("gloss", r"""
<p><b>Step by step:</b> encode the prompt to numbers, then loop <code>n_new</code> times. Each
pass takes the scores for the last position, divides by <code>temperature</code> (more on that under temperature, below), and <code>mx.random.categorical</code> rolls a weighted die to pick the next
character (likelier characters chosen more often, but not always). Glue it on and continue.</p>
"""),
  ("callout", "aside", "Generation vs. inference: which is which", r"""
<p>Each pass through this loop is one step of <strong>inference</strong>: a single forward run
of the model to get the next-token scores. &ldquo;Inference&rdquo; is the umbrella term for
<em>using</em> a trained model (any forward pass), as opposed to <em>training</em> it. Wrapping
inference in this sample-and-append loop, to emit a whole sequence, is what we call
<strong>generation</strong> (or <em>decoding</em>). So generation isn't a different thing from
inference; it's inference run autoregressively, one token at a time.</p>
"""),
  ("output", "01", "def generate(prompt, n_new=400", "what a from-scratch char-level model writes"),
  ("callout", "key", "This gibberish is the point", r"""
<p>It looks like English (real spacing, plausible letter runs, the ghost of words) but it's
nonsense. That is the <em>correct</em> outcome for a 3.2-million-parameter model that works one
letter at a time and trained for four minutes. It proves the whole pipeline works end to end;
it just hasn't the capacity for meaning. Closing the gap between &ldquo;looks like
language&rdquo; and &ldquo;is coherent&rdquo; is the job of the upgrades stage that follows.</p>
"""),
 ],
},

# ====================== PART III — THE UPGRADES ============================
{
 "id": "upgrades", "num": "10", "title": "The upgrades that move quality",
 "part": "Making it good",
 "part_banner": "Stage 3 · The upgrades that move quality (notebook 02)",
 "blocks": [
  ("prose", r"""
<p>Notebook 02 keeps the <em>exact same architecture</em> and layers on the five changes that
actually improve a from-scratch run. Holding the architecture fixed is deliberate: it isolates
what each upgrade buys. One of these, the tokenizer, does most of the work.</p>
"""),
  ("table", r"""
<table>
<thead><tr><th>Upgrade</th><th>Notebook 01</th><th>Notebook 02</th><th>Why it helps</th></tr></thead>
<tbody>
<tr><td>Tokenizer</td><td>one per character</td><td><b>8k word-chunks (BPE)</b></td>
    <td>the big win: the model reasons in word-pieces, not letters</td></tr>
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
how to spell. Real models (and notebook 02) use <strong>sub-word tokenisation</strong>,
specifically <strong>BPE (Byte-Pair Encoding)</strong>. Starting from raw bytes (essentially
the individual characters), BPE repeatedly merges the most common adjacent pair into a single
new token. After enough merges,
frequent chunks like <code>" the"</code>, <code>"ing"</code>, or <code>" robot"</code> each
become <em>one</em> token. The model then reasons over meaningful units, and coherence appears
far faster at the same size.</p>
<p>Crucially, we <em>train</em> the tokenizer on our own corpus, so all 8,192 tokens are
relevant to these stories: no wasted vocabulary.</p>
"""),
  ("code", "02", "tok = Tokenizer(models.BPE", "Train a byte-level BPE tokenizer on the corpus."),
  ("gloss", r"""
<p><b>What's happening:</b> set up a BPE tokenizer, then <code>train_from_iterator</code> learns
the merges from our text, building an 8,192-token vocabulary. We then re-encode the whole
corpus with it. The print-outs report the <b>compression ratio</b> (characters per token)
and a round-trip check (encode then decode gets the original text back). At ~4 characters per
token, sequences are roughly 4× shorter, so the model effectively sees 4× more story within the
same context window.</p>
"""),
  ("output", "02", "tok = Tokenizer(models.BPE", "what it prints"),
  ("callout", "aside", "Notice the tokens for &ldquo;Once upon a time&rdquo;", r"""
<p>It encodes to just four numbers: four chunks, not sixteen characters. That compression is
the whole point: fewer, more meaningful units for the model to reason over. This is also a
preview of Part 2, where a model is fine-tuned for clinical-trial readouts using exactly this
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
<code>STD / math.sqrt(2 * n_layer)</code> on the <code>c_proj</code> and second MLP layer,
the two places where each block writes back into the residual stream. Scaling those down by an
amount that grows with depth keeps the signal's size stable from the first layer to the last.
Everything else (attention, the block, the embeddings, the head) is identical to notebook 01.</p>
"""),
  ("output", "02", "STD = 0.02", "model size"),
  ("callout", "aside", "Same idea, written tighter", r"""
<p>You'll notice this code is more densely packed than notebook 01's. It's the same components
(attention, block, GPT) just written compactly now that the concepts are familiar. If you can
read notebook 01's version, you can read this one.</p>
"""),
 ],
},

{
 "id": "schedule", "num": "13", "title": "A smarter training schedule",
 "blocks": [
  ("prose", r"""
<p>Two upgrades live in the training loop. Both are about <em>stability</em>: letting us train
harder without things breaking.</p>
<ul>
<li><strong>Learning-rate schedule.</strong> Instead of a constant step size, we
<em>warm up</em> (start near zero and ramp up over the first stretch; a cold, random model
hates big steps), then <em>cosine-decay</em> smoothly back down. The gentle landing lets the
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
line, which caps the size of each update. The rest of the loop is the same grab-batch → measure →
nudge rhythm from before.</p>
"""),
  ("figure", "loss_curve_tuned.png",
   "Left: a longer, steadier descent than notebook 01. Right: the learning rate ramping up, then decaying."),
  ("gloss", r"""
<p>The right-hand panel is the schedule made visible: the rate climbs during warm-up, then
follows a smooth cosine curve down to its floor. The left panel shows the payoff: a cleaner,
deeper descent than the constant-rate run. (The loss values aren't directly comparable to
notebook 01's, because the vocabulary is different now; it's the <em>shape</em> that matters.)</p>
"""),
 ],
},

{
 "id": "result", "num": "14", "title": "The payoff: from gibberish to little stories",
 "blocks": [
  ("prose", r"""
<p>Same generation loop as before, but now each step samples a word-chunk, not a single
letter. Here is what the tuned model writes, at two different temperatures:</p>
"""),
  ("output", "02", "def generate(prompt, n_new=200", "what the tuned model writes", 1400),
  ("callout", "key", "Look what changed", r"""
<p>Real words. Names that persist across sentences (&ldquo;Timmy,&rdquo; &ldquo;Jack&rdquo;).
Dialogue with quotation marks. The arc of a little story. It still wanders and contradicts
itself (it's a 17-million-parameter model trained for twenty minutes on a laptop) but set it
beside the character-level gibberish from the from-scratch pass and the leap is unmistakable. <em>Same
architecture.</em> The difference is almost entirely the five upgrades, and mostly the tokenizer.</p>
"""),
  ("callout", "tryit", "Want to feel each upgrade?", r"""
<p>The notebooks invite an <em>ablation</em>: turn one upgrade off, re-run, compare.</p>
<ul>
<li><b>Tokenizer:</b> notebook 01 already <em>is</em> the &ldquo;no-BPE&rdquo; version; compare
its samples to these.</li>
<li><b>Init:</b> remove the depth-scaling and watch the early loss misbehave.</li>
<li><b>Schedule:</b> swap in a constant learning rate; the final loss creeps up.</li>
<li><b>Capacity:</b> push the steps or layers higher for more.</li>
</ul>
"""),
 ],
},

{
 "id": "ceiling", "num": "15", "title": "The honest ceiling, and where this leads",
 "blocks": [
  ("prose", r"""
<p>Even fully tuned, this is a 17-million-parameter model that trained for about twenty minutes on
simple children's stories. It will produce believable words and short phrases — never reasoning
or reliable facts. That gap, between &ldquo;looks like language&rdquo; and &ldquo;is actually
useful,&rdquo; is exactly the gap a <strong>pretrained</strong> model closes: it has already
done the equivalent of this training across <em>trillions</em> of tokens and thousands of
GPU-hours.</p>
<p>And that is the whole point of building the tiny one first. You've now seen, in real code,
every mechanism a frontier model uses: tokenisation, embeddings, attention, the transformer
block, the loss, backpropagation, the optimizer, sampling. The giants are not different in
kind. They are this, scaled.</p>
"""),
  ("callout", "insight", "What &ldquo;Once upon a time&rdquo; reveals: the corpus is the model", r"""
<p>There's a second limit here, and it has nothing to do with size. Prompt this model with
&ldquo;Once upon a time&rdquo; and it spins a little fairy tale, but ask it a question, or for a
fact, or to reason, and it simply can't. It <em>only</em> tells toddler stories, because
<strong>TinyStories is the entire world it ever saw.</strong> A model learns the shape of its
training data and nothing outside it: the corpus doesn't merely feed the model, it
<em>defines</em> it.</p>
<p><strong>Practically,</strong> that makes the data your single most important design choice: it
fixes the model's competence, its vocabulary, and its blind spots. Train on legal contracts and it
speaks legalese; on toddler tales and it speaks toddler. (Part 2 pulls this lever on purpose:
feed a model clinical-trial readouts and you get a trial expert.)</p>
<p><strong>Socially,</strong> this is the root of what people mean by &ldquo;LLM bias.&rdquo; A
model mirrors its corpus (the patterns, the gaps, the over- and under-representation, the
omissions of whoever's text dominates) and at web scale that quietly carries human biases and
blind spots along with the knowledge. Our one narrow corpus shows the mechanism in miniature:
what goes in is what comes out. The training set is a choice, and every choice leaves its
fingerprint on the model.</p>
"""),
  ("callout", "key", "What you now understand end-to-end", r"""
<ul>
<li><b>Tokenisation</b>: text ↔ numbers (characters, then word-chunks).</li>
<li><b>Embeddings</b>: turning a token id and its position into a vector of meaning.</li>
<li><b>Weights, biases &amp; activations</b>: every layer is <code>y = Wx + b</code> followed by
a nonlinear bend (GELU); those W's and b's are exactly the parameters training tunes.</li>
<li><b>Attention</b>: how positions share information, and why looking forward is forbidden.</li>
<li><b>The transformer block</b>: attention + MLP, held together by residuals and LayerNorm.</li>
<li><b>The training loop</b>: the four-step cycle: forward pass → loss → backward pass
(backpropagation) → gradient-descent step.</li>
<li><b>The loss curve</b>: reading learning versus overfitting.</li>
<li><b>Autoregressive sampling</b>: generating one token at a time, and what temperature does.</li>
<li><b>The corpus is the model</b>: training data defines (and biases) what a model can do;
choosing it is the real design lever, and the root of &ldquo;LLM bias.&rdquo;</li>
</ul>
"""),
 ],
},

# ====================== PART IV — USE IT ============================
{
 "id": "use", "num": "16", "title": "Using the model you built",
 "part": "Use the thing you built",
 "part_banner": "Stage 4 · Use the thing you built (notebook 03)",
 "blocks": [
  ("prose", r"""
<p>Training took twenty-odd minutes. You should only ever pay that <em>once</em>. The last cell
of notebook 02 saves the trained model (its parameters, its tokenizer, and its configuration)
to a folder on disk. After that, a separate, tiny program can reload it in under a second and
generate text without any retraining at all.</p>
"""),
  ("code", "02", "import tiny_gpt", "Save the trained model so you never retrain just to use it."),
  ("gloss", r"""
<p><b>What's happening:</b> bundle up the three things you need to reuse a model (the learned
<b>weights</b>, the <b>tokenizer</b> so new text is chunked the same way, and the
<b>config</b>, the shape of the model) and write them to a checkpoint folder. That trio is,
in miniature, exactly what &ldquo;downloading a model&rdquo; gives you anywhere.</p>
"""),
  ("prose", r"""
<p>Reloading is the mirror image. A small library, <code>tiny_gpt.py</code>, rebuilds the model
from the config, pours the saved weights back in, and loads the tokenizer:</p>
"""),
  ("srccode", "lib", "def load(ckpt_dir):", "return model, tok, cfg", "tiny_gpt.load: rebuild and reload in under a second."),
  ("gloss", r"""
<p><b>The shape of it:</b> read the config, construct an empty model of that shape,
<code>load_weights</code> fills it with the trained numbers, and the tokenizer is read back from
its file. <code>model.eval()</code> flips it into inference mode. From here, generating text is
instant.</p>
"""),
  ("code", "03", "model, tok, cfg = tiny_gpt.load", "In a notebook: load once, then generate freely."),
  ("gloss", r"""
<p><b>In plain terms:</b> one line, <code>tiny_gpt.load("checkpoints/tiny_gpt_v2")</code>, does
all the rebuilding above and hands back three things: the <code>model</code>, its
<code>tok</code>enizer, and its <code>cfg</code> (configuration). The <code>time</code> calls
around it just measure how long it took, to make the point: a fraction of a second, versus the
twenty minutes of training. Load once at the top of a session, then generate as often as you like.</p>
"""),
  ("output", "03", "model, tok, cfg = tiny_gpt.load", "load time"),
 ],
},

{
 "id": "temperature", "num": "17", "title": "The one knob worth feeling: temperature",
 "blocks": [
  ("prose", r"""
<p>You met <code>temperature</code> in the generation code. It's the single most tangible dial
in all of language modelling, and the cheapest to experiment with: no retraining, just re-run.
It controls how boldly the model samples: <strong>low</strong> temperature makes it play it
safe (pick the likeliest token almost every time, coherent but repetitive);
<strong>high</strong> temperature makes it adventurous (give unlikely tokens a real chance,
creative but loopier).</p>
"""),
  ("code", "03", "for temp in (0.4, 0.7, 1.0, 1.2)", "Same prompt, rising temperature."),
  ("gloss", r"""
<p><b>What's happening:</b> run the same opening at four temperatures and print each. Reading the
results from low to high, you can watch the text loosen: tighter and more repetitive at 0.4,
freer and stranger by 1.2. It's the most direct way to <em>feel</em> what sampling does, and the
same knob you'll find in every model's API.</p>
"""),
  ("prose", r"""
<p>There's also a small terminal program, <code>chat.py</code>, that wraps all of this into an
interactive prompt: type an opener, watch the story stream in token by token, adjust the
temperature on the fly. It's the from-scratch model turned into something you can actually play
with.</p>
"""),
 ],
},

{
 "id": "endstory", "num": "18", "title": "Knowing when to stop: the end-of-story token",
 "blocks": [
  ("prose", r"""
<p>You can now generate text and shape it with temperature, but how does the model know when a
story is <em>over</em>? Left alone, it never stops: it just keeps predicting the next token until
you cut it off at a token limit. So every reply comes out the same length, and a long one runs
two stories together.</p>
<p>The fix is the one every real language model uses: a dedicated <strong>end-of-text
token</strong> (GPT-2 calls it <code>&lt;|endoftext|&gt;</code>; here it's
<code>&lt;|endstory|&gt;</code>). A tempting shortcut is to treat the blank line between stories
as the boundary, but that fails, because the blank line is <em>also</em> the paragraph break
inside almost every story, so the model can't tell &ldquo;end of paragraph&rdquo; from &ldquo;end
of story.&rdquo; A reserved token that appears <em>only</em> between stories has no such
ambiguity.</p>
"""),
  ("srccode", "train", "trainer = trainers.BpeTrainer", "data = np.array(ids",
   "Reserve a special token, then drop it after every story in the training stream."),
  ("gloss", r"""
<p><b>What's happening:</b> we add <code>&lt;|endstory|&gt;</code> to the tokenizer as a
<em>special</em> token (matched as one atomic unit, never split into characters) then build the
training stream story-by-story, appending that token's id after each one. The model now sees,
thousands of times over, that a finished story is followed by this exact marker. So it learns to
produce it precisely when a story is complete.</p>
"""),
  ("srccode", "lib", "def stream(model", "emitted = len(gen)",
   "At generation time, stop the instant that token appears."),
  ("gloss", r"""
<p><b>The payoff in code:</b> each step samples the next token; if it's the end-of-story token we
<code>return</code> immediately (<em>before</em> emitting it) so the story ends cleanly on its
last real word. If the model never emits it, the <code>n_new</code> cap still ends things
eventually. That single check is the whole mechanism behind &ldquo;the model decided it was
done.&rdquo;</p>
"""),
  ("rawoutput", """Once upon a time, there was a little girl named Lily. She loved to play outside in the sun and pretend to be a princess. One day, Lily went to the park and saw a little boy who was crying.

"Hello, little boy. What's wrong?" asked Lily.

"I lost my teddy bear," said the boy.

Lily nodded and said, "I will help you find your teddy bear."

Lily was happy to help, and said, "Thank you, I'm glad I could help you." The little boy smiled and said, "Thank you, Lily. You are a good friend.\"""",
   "a complete story from chat.py: it stopped on its own, well short of the token cap"),
  ("callout", "key", "Why this small change matters", r"""
<p>With a real boundary token, stories come out <em>self-contained and naturally varying in
length</em>: a short tale ends short, a longer one runs on, and neither bleeds into a stray new
&ldquo;Once upon a time.&rdquo; It's a tiny change to the <em>data</em>, not the model, but it's
the difference between a fixed-length text dump and something that knows when to stop. Every
chatbot you've used ends its turn in exactly this way.</p>
"""),
  ("callout", "key", "The thread that ties it all together", r"""
<p>Every concept in this walk-through (tokens, attention, the loss, the training loop,
temperature) reappears, unchanged in spirit, in <a href="../track-b/">Part 2</a> of this lab, where a
real pretrained model is fine-tuned into a useful clinical-trial expert. You built the tiny one to
<em>see</em> the mechanism. The same mechanism, scaled up and pointed at a real task, is the whole game.</p>
"""),
  ("callout", "aside", "Run it yourself", r"""
<p>Everything here is open source (the three notebooks, the terminal chat, and even the script
that builds this very page) at
<a href="https://github.com/JEM-Fizbit/small-model-lab">github.com/JEM-Fizbit/small-model-lab</a>.</p>
<p><strong>Just want to look?</strong> The notebooks render on GitHub <em>with their outputs</em>,
so you can read the real code and its results without installing anything.</p>
<p><strong>Want to run and chat with your own tiny GPT?</strong> You'll need an Apple-Silicon Mac
(the code uses Apple's MLX). The
<a href="https://github.com/JEM-Fizbit/small-model-lab/blob/main/docs/GETTING_STARTED.md">Getting Started
guide</a> takes you from zero (install, open a notebook, run it, chat) in about fifteen minutes,
with no prior coding assumed.</p>
"""),
  ("callout", "key", "Where to next", r"""
<p>That closes the build. The payoff is <strong><a href="../track-b/">Part 2 · Post-training</a></strong>:
start from a big pretrained open model and fine-tune it into a useful clinical-trial expert, the same
machinery you just built, now doing a real job. Want the ideas without the code, first or again?
<strong><a href="../ideas/">Part 0 · Concepts</a></strong>. ← back to <a href="../">the lab home</a>.</p>
"""),
 ],
},

]

# ---------------------------------------------------------------- LANDING --
LANDING_META = {
    "title": "small-model-lab: build a small language model, explained",
    "description": "A hands-on, no-black-box lab: the concepts, a tiny GPT built from "
                   "scratch, and a real open model fine-tuned into a useful expert — "
                   "explained for the curious.",
}

LANDING = {
    "kicker": "small-model-lab",
    "h1": "Build a small language model, and actually understand&nbsp;it",
    "lede": "A hands-on, no-black-box lab. <em>Build</em> a tiny language model from scratch, then "
            "<em>fine-tune</em> a real open model into a useful expert — with an optional, code-free "
            "<em>concepts</em> primer if you'd like the ideas first. Explained for the curious.",
}

LANDING_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{{ meta.title }}</title>
<meta name="description" content="{{ meta.description }}"/>
<meta property="og:title" content="{{ meta.title }}"/>
<meta property="og:description" content="{{ meta.description }}"/>
<meta property="og:type" content="website"/>
<link rel="apple-touch-icon" href="apple-touch-icon.png"/>
<link rel="icon" type="image/png" sizes="64x64" href="favicon.png"/>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064%2064%22%3E%3Crect%20width%3D%2264%22%20height%3D%2264%22%20rx%3D%2210%22%20fill%3D%22%23f7f3ea%22%2F%3E%3Crect%20x%3D%222.5%22%20y%3D%222.5%22%20width%3D%2259%22%20height%3D%2259%22%20rx%3D%228%22%20fill%3D%22none%22%20stroke%3D%22%23ddd4c2%22%20stroke-width%3D%222%22%2F%3E%3Ctext%20x%3D%2232%22%20y%3D%2246%22%20text-anchor%3D%22middle%22%20font-family%3D%22Georgia%2Cserif%22%20font-style%3D%22italic%22%20font-size%3D%2242%22%20fill%3D%22%23963d2c%22%3E%C2%A7%3C%2Ftext%3E%3C%2Fsvg%3E"/>
<meta property="og:image" content="https://jem-fizbit.github.io/small-model-lab/og-image.png"/>
<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300..700;1,6..72,300..700&family=IBM+Plex+Mono:ital,wght@0,400;0,500;0,600;1,400&display=swap');
:root{
  --ink:#231f18; --soft:#6e6557; --faint:#998f7d;
  --line:#ddd4c2; --bg:#f7f3ea;
  --accent:#963d2c; --accent-soft:#f0e2dc;
  --code-bg:#f0eadb;
  --serif:'Newsreader',Charter,'Iowan Old Style',Georgia,serif;
  --mono:'IBM Plex Mono','SF Mono',ui-monospace,Menlo,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--serif);
  -webkit-font-smoothing:antialiased;font-optical-sizing:auto;line-height:1.7;}
::selection{background:var(--accent-soft);}
a{color:inherit;}
.label{font-family:var(--mono);text-transform:uppercase;letter-spacing:.16em;
  font-size:11px;font-weight:500;color:var(--faint);}

/* top bar */
.topbar{border-bottom:1px solid var(--line);}
.topbar .inner{max-width:1140px;margin:0 auto;padding:22px 24px 18px;
  display:flex;align-items:baseline;gap:28px;}
.wordmark{font-family:var(--serif);font-size:21px;font-weight:500;letter-spacing:-.01em;
  color:var(--ink);text-decoration:none;margin-right:auto;}
.wordmark span{color:var(--accent);}
.topbar nav{display:flex;gap:26px;align-items:baseline;flex-wrap:wrap;}
.topbar nav a{font-family:var(--mono);font-size:11.5px;letter-spacing:.12em;
  text-transform:uppercase;color:var(--soft);text-decoration:none;white-space:nowrap;}
.topbar nav a:hover{color:var(--accent);}
.topbar nav a.hub{color:var(--faint);}
.topbar .hub-short{display:none;}

.wrap{max-width:1140px;margin:0 auto;padding:0 24px;}

/* hero */
.hero{padding:80px 0 60px;}
.hero .kicker{font-family:var(--mono);font-size:11px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--accent);margin:0 0 20px;font-weight:500;}
.hero .kicker a{color:var(--accent);text-decoration:none;border-bottom:1px solid var(--accent-soft);}
.hero .kicker .seg{display:inline-block;}
.hero h1{font-size:56px;line-height:1.06;font-weight:500;letter-spacing:-.022em;
  margin:0 0 26px;max-width:820px;}
.hero h1 .dot{color:var(--accent);}
.hero .lede{font-size:21px;line-height:1.6;color:var(--soft);margin:0;max-width:680px;}
.hero .lede em{font-style:italic;}

/* contents — book-style rows */
.contents{border-top:1px solid var(--ink);}
.row{display:grid;grid-template-columns:120px 1fr 300px;gap:36px;padding:34px 0;
  border-bottom:1px solid var(--line);align-items:start;
  text-decoration:none;color:inherit;}
a.row:hover .row-title{color:var(--accent);}
.row-num{font-size:52px;font-weight:300;color:var(--faint);line-height:1;margin-top:-5px;}
.row.live .row-num{color:var(--accent);}
.row-part{font-family:var(--mono);font-size:11px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--faint);margin-top:10px;font-weight:500;}
.row-title{font-size:29px;font-weight:500;letter-spacing:-.01em;line-height:1.2;
  transition:color .12s;}
.row-body{font-size:16.5px;line-height:1.6;color:var(--soft);margin:10px 0 0;max-width:460px;}
.row-body code{font-family:var(--mono);font-size:.82em;background:var(--code-bg);
  padding:1px 6px;border-radius:3px;}
.row-side{justify-self:end;text-align:right;padding-top:9px;}
.row-tag{font-family:var(--mono);font-size:11px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--faint);font-weight:500;}
.row.live .row-tag{color:var(--accent);}
.row-go{font-style:italic;font-size:16px;color:var(--accent);margin-top:14px;}
.row.soon{opacity:.66;}

/* why */
.why{padding:58px 0 0;}
.why-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:0 44px;margin-top:18px;}
.why-item{display:grid;grid-template-rows:subgrid;grid-row:span 3;border-top:1px solid var(--line);padding-top:14px;}
.why-item .rn{font-style:italic;font-size:19px;color:var(--accent);margin-bottom:10px;align-self:end;line-height:1;}
.why-item h3{font-size:17.5px;font-weight:600;line-height:1.4;margin:0 0 10px;text-wrap:balance;}
.why-item p{font-size:15px;line-height:1.62;color:var(--soft);margin:0;}

/* about */
.about{margin-top:58px;border-top:1px solid var(--line);padding-top:44px;
  display:grid;grid-template-columns:200px 1fr;gap:44px;align-items:start;}
.about .portrait{margin:30px 0 0;padding:9px;border:1px solid var(--line);background:#fbf8f1;}
.about .portrait img{width:100%;height:auto;aspect-ratio:4/5;object-fit:cover;display:block;
  border-radius:1px;filter:saturate(.82) contrast(.98);}
.about .inner{max-width:660px;}
.about p{font-size:16.5px;line-height:1.65;margin:0 0 12px;}
.about p.second{font-size:15.5px;color:var(--soft);}
.about p.cta{font-size:15.5px;color:var(--soft);margin-top:14px;}
.about a{color:var(--accent);text-decoration:none;border-bottom:1px solid var(--accent-soft);}
.about a:hover{border-color:var(--accent);}
.about .cta-link{font-style:italic;font-size:16px;display:inline-block;margin-top:4px;}

/* foot */
.foot{margin-top:52px;border-top:1px solid var(--line);padding:22px 0 48px;
  font-family:var(--mono);font-size:11.5px;color:var(--faint);line-height:1.9;}
.foot a{color:var(--accent);text-decoration:none;border-bottom:1px solid var(--accent-soft);}
.foot .seg{display:inline;}

@media (max-width:880px){
  .hero h1{font-size:38px;}
  .row{grid-template-columns:64px 1fr;gap:20px;}
  .row-num{font-size:36px;margin-top:7px;}
  .row-side{grid-column:2;justify-self:start;text-align:left;display:flex;gap:18px;align-items:baseline;}
  .row-go{margin-top:0;}
  .why-grid{grid-template-columns:1fr;gap:28px;}
  .why-item{display:block;}
  .about{grid-template-columns:1fr;gap:22px;}
  .about .portrait{max-width:220px;}
}
@media (max-width:680px){
  .topbar .inner{flex-wrap:wrap;padding:16px 16px 12px;gap:8px 18px;}
  .wordmark{font-size:18px;}
  .topbar nav{gap:16px;}
  .topbar nav a{font-size:10px;letter-spacing:.08em;}
  .topbar .hub-long{display:none;}
  .topbar .hub-short{display:inline;}
}
</style>
</head>
<body>

<header class="topbar"><div class="inner">
  <a class="wordmark" href="./">small<span>·</span>model<span>·</span>lab</a>
  <nav>
    {% if concepts_live %}<a href="ideas/">Concepts</a>{% endif %}
    <a href="track-a/">Pre-training</a>
    {% if track_b_live %}<a href="track-b/">Post-training</a>{% endif %}
    <a class="hub" target="_blank" rel="noopener" href="{{ hub_url }}"><span class="hub-long">AI Knowledge Hub ↗</span><span class="hub-short">Hub ↗</span></a>
  </nav>
</div></header>

<div class="wrap">
  <section class="hero">
    <p class="kicker"><span class="seg">A walk-through in three parts&nbsp;&nbsp;·</span> <span class="seg">part of the <a target="_blank" rel="noopener" href="{{ hub_url }}">AI Knowledge Hub</a></span></p>
    <h1>{{ landing.h1 }}<span class="dot">.</span></h1>
    <p class="lede">{{ landing.lede }}</p>
  </section>

  <section class="contents">
    {% if concepts_live %}
    <a class="row" href="ideas/">
      <div><div class="row-num">0</div><div class="row-part">Concepts</div></div>
      <div>
        <div class="row-title">How a language model works</div>
        <p class="row-body">The plain-English ideas behind it all, no code: what a model <em>is</em>, how text becomes numbers, and what &ldquo;learning&rdquo; really means, with diagrams. Read it first if you like theory; dip back in as Parts 1 and 2 link to it.</p>
      </div>
      <div class="row-side"><div class="row-tag">optional primer</div><div class="row-go">Read Part 0&nbsp;→</div></div>
    </a>
    {% endif %}
    <a class="row live" href="track-a/">
      <div><div class="row-num">1</div><div class="row-part">Pre-training</div></div>
      <div>
        <div class="row-title">A GPT from scratch</div>
        <p class="row-body">Build and train a tiny GPT one piece at a time: tokens, attention, the training loop, <code>y = Wx + b</code>, sampling. The output is throwaway by design; the point is to <em>see</em> how it works.</p>
      </div>
      <div class="row-side"><div class="row-tag">start here</div><div class="row-go">Read Part 1&nbsp;→</div></div>
    </a>
    {% if track_b_live %}
    <a class="row" href="track-b/">
      <div><div class="row-num">2</div><div class="row-part">Post-training</div></div>
      <div>
        <div class="row-title">TrialScout: a useful expert</div>
        <p class="row-body">Take a <em>pretrained</em> open model and fine-tune it into a measurably useful tool that turns a clinical-trial record into a structured readout. Same concepts, now doing a real job.</p>
      </div>
      <div class="row-side"><div class="row-tag">the payoff</div><div class="row-go">Read Part 2&nbsp;→</div></div>
    </a>
    {% else %}
    <div class="row soon">
      <div><div class="row-num">2</div><div class="row-part">Post-training</div></div>
      <div>
        <div class="row-title">TrialScout: a useful expert</div>
        <p class="row-body">Take a <em>pretrained</em> open model and fine-tune it into a measurably useful tool that turns a clinical-trial record into a structured readout. Same concepts, now doing a real job.</p>
      </div>
      <div class="row-side"><div class="row-tag">in progress</div><div class="row-go">Coming soon</div></div>
    </div>
    {% endif %}
  </section>

  <section class="why">
    <p class="label">Why this exists</p>
    <div class="why-grid">
      <div class="why-item">
        <div class="rn">i.</div>
        <h3>The learning tools I wish I'd had.</h3>
        <p>When I started, explanations were either hand-wavy analogies or dense papers. This is the middle I wanted: real, runnable code with every step narrated in plain English.</p>
      </div>
      <div class="why-item">
        <div class="rn">ii.</div>
        <h3>To make AI's concepts accessible to non-specialists.</h3>
        <p>You shouldn't need to be an ML engineer to build intuition for how these models actually work, and what they can and can't do. No prior Python required to read along.</p>
      </div>
      <div class="why-item">
        <div class="rn">iii.</div>
        <h3>To leave reusable patterns, not just a demo.</h3>
        <p>Each chapter is a template you can lift: pre-training a model from scratch (Part 1), and the post-training playbook (Part 2) — distilling a big model's judgement into a small, cheap one.</p>
      </div>
    </div>
  </section>

  <section class="about">
    {% if headshot %}<figure class="portrait">
      <img src="{{ headshot }}" alt="John E. Milad"/>
    </figure>{% endif %}
    <div class="inner">
      <p class="label" style="margin:0 0 12px;">About me</p>
      <p>I'm <a target="_blank" rel="noopener" href="https://www.linkedin.com/in/johnemilad/"><strong>John E. Milad</strong></a>. I run a biotech company and have spent the last few years deep in modern AI, using it daily, building with it, and working out what's worth knowing. small-model-lab is one hands-on piece of that.</p>
      <p class="second">It's also a working example of the method: this whole lab (the code, the site, the diagrams) was built in close, mutually-challenging collaboration with <strong>Claude</strong>, both of us drafting, with me directing, editing, and deciding throughout.</p>
      <p class="cta"><strong>The bigger picture.</strong> small-model-lab is one project from my <a target="_blank" rel="noopener" href="{{ hub_url }}">AI Knowledge Hub</a>, a curated, regularly-updated library for the AI era: the tools, the practices, and a zero-to-shipping learning path.<br/>
      <a class="cta-link" target="_blank" rel="noopener" href="{{ hub_url }}">Explore the AI Knowledge Hub&nbsp;→</a></p>
    </div>
  </section>

  <p class="foot">
    <span class="seg">© 2026 John E. Milad&nbsp;·</span>
    <span class="seg"><a target="_blank" rel="noopener" href="https://github.com/JEM-Fizbit/small-model-lab/blob/main/LICENSE">MIT-licensed</a>, open source:</span>
    <span class="seg"><a target="_blank" rel="noopener" href="https://github.com/JEM-Fizbit/small-model-lab">github.com/JEM-Fizbit/small-model-lab</a>&nbsp;·</span>
    <span class="seg">builds on nanoGPT, Apple MLX, and TinyStories.</span><br/>
    <span class="seg">Built in collaboration with Claude</span>
    <span class="seg">(via Claude Code)&nbsp;·</span>
    <span class="seg">Spotted an error or have a comment?</span>
    <span class="seg"><a target="_blank" rel="noopener" href="https://github.com/JEM-Fizbit/small-model-lab/issues">Open a GitHub issue</a>.</span><br/>
    <span class="seg">Part of the <a target="_blank" rel="noopener" href="{{ hub_url }}">AI Knowledge Hub</a>.</span>
  </p>
</div>
</body>
</html>
"""
