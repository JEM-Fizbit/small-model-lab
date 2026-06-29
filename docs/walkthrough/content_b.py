"""content_b.py — Track B (TrialScout) chapter of the small-model-lab walk-through.

Same hybrid design as content.py (Track A): hand-authored narrative here; code
excerpts pulled live from the real Track B files by build.py's ("filecode", …)
blocks, so what the reader sees matches what ran. Results are the real numbers
from track-b-trialscout/eval/PHASE3_RESULTS.md / PHASE4_RESULTS.md.

build.py renders this to site/track-b/index.html whenever this module is present.
"""

META = {
    "title": "Fine-tuning a small model into a useful expert: TrialScout",
    "subtitle": "Part 2: take a pretrained open model and make it do a real job, locally and for free.",
}

# Part 2's own primer: the pipeline idioms its code excerpts actually use (Part 1's
# primer covers the reading basics and is linked for those).
PYTHON_PRIMER = r"""
<p>Part 2's code is <em>pipeline</em> code, so its recurring patterns differ from Part 1's. (New to
Python entirely? <a href="../track-a/#primer">Part 1's primer</a> covers the basics: variables,
functions, classes, loops.) These six cover most of what appears in this chapter's code boxes.</p>

<dl class="primer">
  <dt>{"phase": "Phase 2", "enrollment": 41}</dt>
  <dd><strong>A dictionary</strong>: named slots holding values, Python's all-purpose record. It's
  also exactly the shape of <strong>JSON</strong>, the text format APIs speak, which is why trial
  records and readouts move through this whole chapter as dictionaries.</dd>

  <dt>client.messages.create(model=..., temperature=0)</dt>
  <dd><strong>Keyword arguments.</strong> Each <code>name=value</code> names the setting it fills, so
  a call with many options stays readable. The teacher call in §2 is mostly this.</dd>

  <dt>cmd = ["mlx_lm", "lora", "--iters", "700"]</dt>
  <dd><strong>A command as a list.</strong> Each item is one word of a terminal command; Python hands
  the list to the operating system to run. The fine-tune in §4 is launched exactly this way, which is
  why its code box reads like flags rather than maths.</dd>

  <dt>todo[:10]</dt>
  <dd><strong>Slicing</strong>: take the first ten items of a list. The pilot gate in §3 labels
  <code>todo[:10]</code> and checks the results before risking money on the other 1,490.</dd>

  <dt>@mcp.tool(...)</dt>
  <dd><strong>A decorator</strong>: an <code>@</code> line just above a function that wraps or
  registers it. In §9 it's the line that tells the MCP server &ldquo;this function is a callable
  tool.&rdquo;</dd>

  <dt>def trial_readout(nct_id: str) -> str:</dt>
  <dd><strong>Type hints.</strong> The <code>: str</code> and <code>-&gt; str</code> declare what kind
  of value goes in and comes out (text, here). Python doesn't enforce them; they're documentation that
  tools and readers rely on.</dd>
</dl>
"""

# ----------------------------------------------------------------------- HERO --
HERO = r"""
<p class="kicker">small-model-lab · Part 2 · Post-training</p>
<h1>From a toy to a tool</h1>
<p class="lede">In Part 1 we built a tiny GPT from scratch and hit its ceiling: it learned the
<em>shape</em> of language but never anything useful. This chapter is the other half of the arc:
how real models are made <em>useful</em>. We take a <strong>pretrained</strong> open model and
fine-tune it into <strong>TrialScout</strong>: a small expert that turns an oncology clinical-trial
record into a structured, investor-relevant readout, running on a laptop, for free.</p>

<div class="bigidea">
  <p><strong>The whole idea:</strong> a giant model already knows language; we don't re-teach that.
  We just <em>specialise</em> it for one narrow, structured task, by showing it ~1,500
  worked examples and nudging a tiny set of its parameters. The result beats a sensible baseline
  by a mile and nearly matches the expensive model that taught it.</p>
  <p>And none of this is new machinery. The model is the same animal you built in Part 1 &mdash; a
  transformer, attention blocks and all, just ~1,200&times; bigger &mdash; and fine-tuning is the
  same training loop (tokens, the loss, gradient descent), now in service of something that does
  a job.</p>
</div>

<p class="readnote"><strong>How to read this.</strong> Same as Part 1: the idea first, then the
real code, then a plain-English gloss. Part 2 is more <em>pipeline</em> than algorithm, so the
code boxes show the excerpts that do the real work (pulled straight from the
<a href="https://github.com/JEM-Fizbit/small-model-lab/tree/main/track-b-trialscout">repo</a>) rather than
every line. Haven't read <a href="../track-a/">Part 1</a> yet? Start there; this chapter assumes
its vocabulary.</p>
"""

# ---------------------------------------------------------------- DIAGRAMS --
DISTILL_SVG = r'''<svg viewBox="0 0 820 210" role="img" aria-label="Distillation flow: oncology trials are read by the Claude Sonnet teacher, which writes gold JSON labels, which fine-tune the Qwen student model.">
<defs><marker id="arD" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#6e6557"/></marker></defs>
<!-- box 1: trials -->
<rect x="12" y="50" width="165" height="84" rx="11" fill="#f3ece1" stroke="#963d2c" stroke-width="1.5"/>
<text x="94" y="80" text-anchor="middle" font-size="13.5" font-weight="700" fill="#231f18">Oncology trials</text>
<text x="94" y="100" text-anchor="middle" font-size="11" fill="#6e6557">ClinicalTrials.gov</text>
<text x="94" y="118" text-anchor="middle" font-size="11" fill="#6e6557">1,500 records</text>
<!-- box 2: teacher (purple) -->
<rect x="222" y="50" width="165" height="84" rx="11" fill="#e3eaea" stroke="#3d6a72" stroke-width="1.5"/>
<text x="304" y="80" text-anchor="middle" font-size="13.5" font-weight="700" fill="#2c4a52">Claude Sonnet</text>
<text x="304" y="100" text-anchor="middle" font-size="11" fill="#3d6a72">the teacher</text>
<text x="304" y="118" text-anchor="middle" font-size="10.5" fill="#3d6a72">forced tool-use</text>
<!-- box 3: gold -->
<rect x="432" y="50" width="165" height="84" rx="11" fill="#f3ece1" stroke="#963d2c" stroke-width="1.5"/>
<text x="514" y="80" text-anchor="middle" font-size="13.5" font-weight="700" fill="#231f18">Gold labels</text>
<text x="514" y="100" text-anchor="middle" font-size="11" fill="#6e6557">structured JSON</text>
<text x="514" y="118" text-anchor="middle" font-size="10.5" fill="#6e6557">1,200 train / 150 test</text>
<!-- box 4: student -->
<rect x="642" y="50" width="165" height="84" rx="11" fill="#eceadb" stroke="#5f6c33" stroke-width="1.5"/>
<text x="724" y="80" text-anchor="middle" font-size="13.5" font-weight="700" fill="#4c5829">Qwen3-4B</text>
<text x="724" y="100" text-anchor="middle" font-size="11" fill="#5f6c33">the student</text>
<text x="724" y="118" text-anchor="middle" font-size="10.5" fill="#5f6c33">learns to reproduce</text>
<!-- arrows -->
<line x1="177" y1="92" x2="220" y2="92" stroke="#6e6557" stroke-width="2" marker-end="url(#arD)"/>
<line x1="387" y1="92" x2="430" y2="92" stroke="#6e6557" stroke-width="2" marker-end="url(#arD)"/>
<line x1="597" y1="92" x2="640" y2="92" stroke="#6e6557" stroke-width="2" marker-end="url(#arD)"/>
<text x="198" y="84" text-anchor="middle" font-size="10" fill="#998f7d">read</text>
<text x="408" y="84" text-anchor="middle" font-size="10" fill="#998f7d">writes answers</text>
<text x="618" y="84" text-anchor="middle" font-size="10" fill="#998f7d">fine-tune</text>
</svg>'''

LORA_SVG = r'''<svg viewBox="0 0 720 220" role="img" aria-label="LoRA: the big base model is frozen; only a small adapter of weight deltas is trained; together they make TrialScout.">
<defs><marker id="arL2" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#963d2c"/></marker></defs>
<!-- base, frozen -->
<rect x="20" y="35" width="300" height="150" rx="12" fill="#f1ece0" stroke="#a89d89" stroke-width="1.5" stroke-dasharray="6 4"/>
<text x="170" y="78" text-anchor="middle" font-size="15" font-weight="700" fill="#5c5446">Qwen3-4B (base)</text>
<text x="170" y="104" text-anchor="middle" font-size="12" fill="#8b816d">frozen · 4-bit · ~2 GB</text>
<text x="170" y="126" text-anchor="middle" font-size="12" fill="#8b816d">billions of parameters,</text>
<text x="170" y="143" text-anchor="middle" font-size="12" fill="#8b816d">left untouched ❄</text>
<!-- plus -->
<text x="345" y="118" text-anchor="middle" font-size="30" fill="#6e6557">+</text>
<!-- adapter, trained -->
<rect x="372" y="72" width="168" height="78" rx="11" fill="#f3ece1" stroke="#963d2c" stroke-width="2"/>
<text x="456" y="100" text-anchor="middle" font-size="13.5" font-weight="700" fill="#231f18">LoRA adapter</text>
<text x="456" y="120" text-anchor="middle" font-size="11" fill="#963d2c">28 MB of weight deltas</text>
<text x="456" y="138" text-anchor="middle" font-size="11" fill="#963d2c">the only part trained</text>
<!-- arrow to result -->
<line x1="540" y1="111" x2="566" y2="111" stroke="#963d2c" stroke-width="2" marker-end="url(#arL2)"/>
<rect x="568" y="76" width="132" height="70" rx="11" fill="#eceadb" stroke="#5f6c33" stroke-width="1.5"/>
<text x="634" y="106" text-anchor="middle" font-size="13.5" font-weight="700" fill="#4c5829">TrialScout</text>
<text x="634" y="126" text-anchor="middle" font-size="11" fill="#5f6c33">base + adapter</text>
</svg>'''

EVAL_SVG = r'''<svg viewBox="0 0 800 230" role="img" aria-label="Evaluation: the student predicts a readout for each held-out trial; six structured fields are scored by accuracy and F1, the free-text note by Claude-as-judge, into an overall score versus the baseline.">
<defs><marker id="arE" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#6e6557"/></marker></defs>
<rect x="12" y="80" width="150" height="64" rx="10" fill="#f3ece1" stroke="#963d2c" stroke-width="1.5"/>
<text x="87" y="106" text-anchor="middle" font-size="12.5" font-weight="700" fill="#231f18">Gold test set</text>
<text x="87" y="124" text-anchor="middle" font-size="10.5" fill="#6e6557">150 held-out trials</text>
<rect x="205" y="80" width="150" height="64" rx="10" fill="#eceadb" stroke="#5f6c33" stroke-width="1.5"/>
<text x="280" y="106" text-anchor="middle" font-size="12.5" font-weight="700" fill="#4c5829">TrialScout</text>
<text x="280" y="124" text-anchor="middle" font-size="10.5" fill="#5f6c33">predicts a readout</text>
<rect x="400" y="30" width="210" height="58" rx="10" fill="#fff" stroke="#d8cfbd" stroke-width="1.5"/>
<text x="505" y="54" text-anchor="middle" font-size="12" font-weight="700" fill="#231f18">6 structured fields</text>
<text x="505" y="72" text-anchor="middle" font-size="10.5" fill="#6e6557">→ accuracy / F1 per field</text>
<rect x="400" y="136" width="210" height="58" rx="10" fill="#fff" stroke="#d8cfbd" stroke-width="1.5"/>
<text x="505" y="160" text-anchor="middle" font-size="12" font-weight="700" fill="#231f18">investor_note (free text)</text>
<text x="505" y="178" text-anchor="middle" font-size="10.5" fill="#6e6557">→ Claude-as-judge</text>
<rect x="648" y="78" width="140" height="70" rx="10" fill="#eceadb" stroke="#5f6c33" stroke-width="1.5"/>
<text x="718" y="104" text-anchor="middle" font-size="12.5" font-weight="700" fill="#4c5829">Overall score</text>
<text x="718" y="123" text-anchor="middle" font-size="11" fill="#5f6c33">0.368 → 0.922</text>
<text x="718" y="139" text-anchor="middle" font-size="9.5" fill="#5f6c33">vs baseline</text>
<line x1="162" y1="112" x2="203" y2="112" stroke="#6e6557" stroke-width="2" marker-end="url(#arE)"/>
<line x1="355" y1="104" x2="398" y2="62" stroke="#6e6557" stroke-width="2" marker-end="url(#arE)"/>
<line x1="355" y1="120" x2="398" y2="162" stroke="#6e6557" stroke-width="2" marker-end="url(#arE)"/>
<line x1="610" y1="60" x2="646" y2="100" stroke="#6e6557" stroke-width="2" marker-end="url(#arE)"/>
<line x1="610" y1="164" x2="646" y2="126" stroke="#6e6557" stroke-width="2" marker-end="url(#arE)"/>
</svg>'''

# ===========================================================================
#  SECTIONS
# ===========================================================================
SECTIONS = [

{
 "id": "shift", "num": "0", "title": "The shift: don't build, adapt",
 "part": "Orientation", "part_banner": "Stage 1 · Orientation",
 "blocks": [
  ("prose", r"""
<p>Part 1 ended on an honest ceiling: a from-scratch model, trained on a laptop, produces
believable <em>words</em> but no real knowledge or reasoning. Closing that gap from scratch would
take what the giants spent: trillions of tokens, thousands of GPU-hours. So we don't.</p>
<p>Instead we start from a model that has <em>already</em> paid that price: a <strong>pretrained
open model</strong> (here, Alibaba's Qwen3-4B, 4 billion parameters, freely downloadable). It
already knows English, clinical jargon, JSON, the lot. Our job is narrow: <strong>specialise</strong>
it for one task it isn't yet reliable at: reading a trial record and emitting a clean, structured
readout. That's <em>post-training</em>, and it's how almost every useful model you've met was made.</p>
"""),
  ("callout", "key", "Why a small model can win here", r"""
<p>A 4B model will never be a great general analyst, but it can be excellent at one
<em>narrow, structured</em> task. Trial-record → fixed-schema-JSON is exactly that shape: bounded
inputs, a controlled vocabulary out. Get it right and you have an expert that runs locally, costs
nothing per call, needs no internet, and answers in seconds: things a frontier API can't all
offer at once.</p>
"""),
 ],
},

{
 "id": "task", "num": "1", "title": "The task, and the contract",
 "part": "Teaching the model the task",
 "part_banner": "Stage 2 · Teaching the model the task",
 "blocks": [
  ("prose", r"""
<p>First, the domain, for anyone new to it. A <strong>clinical trial</strong> is a study that tests
whether a treatment (here, a cancer drug) is safe and actually works. Drug companies run thousands of
them, and to an investor each one is a potential <em>catalyst</em>: an upcoming result that can move a
company's value. The trouble is the raw information: every trial is written up in long, inconsistent
prose, and there are tens of thousands of them. So TrialScout's job is to turn each trial into a short,
<strong>uniform structured summary</strong>, so a whole <em>population</em> of trials becomes something
you can scan, filter, compare, and screen at a glance, instead of reading registry pages one at a time.</p>
<p>Concretely: every trial has a public record on <strong>ClinicalTrials.gov</strong>, the US government
registry of studies. Each record is semi-structured data (a title, phase, status, lead sponsor, the
conditions and drugs under test, the primary outcome measure, key dates, enrollment, trial design) plus
free text. We fetch it from the registry's API and trim it to the ~20 fields that matter:
<strong>that trimmed record is TrialScout's input.</strong> Its <em>output</em> is a compact nine-field
JSON readout: <code>nct_id</code>, <code>phase</code>, <code>indication</code>, <code>modality</code>,
<code>primary_endpoint_type</code>, <code>sponsor_type</code>, <code>est_readout</code> (its expected readout as a half-year, e.g. &ldquo;H2 2026&rdquo;), <code>risk_flags</code>, and a ≤2-sentence <code>investor_note</code>. Most output fields are
<strong>enums</strong> (a fixed menu of allowed values), so the readouts are directly comparable across
trials, and easy to score.</p>
"""),
  ("callout", "aside", "JSON, in thirty seconds", r"""
<p>If the term is new to you: <strong>JSON</strong> is the plain-text format most software uses to
pass structured data around. (The name stands for JavaScript Object Notation, but nothing here
involves JavaScript; the format long ago outgrew its origin.) A JSON object is just
<code>"name": value</code> pairs inside curly braces &mdash;
<code>{"phase": "Phase 2", "enrollment": 41}</code> &mdash; where a value can be text, a number,
true/false, a list, or another object nested inside. That's the whole format. It's everywhere
because both sides can read it: a person can eyeball it, and a program can check that every field
is present and valid &mdash; exactly what we'll need when we start scoring outputs. The two boxes
below are both JSON: a trial record in, a readout out.</p>
"""),
  ("prose", r"""
<p>The work is turning verbose, inconsistent registry data into normalised judgement: reading
&ldquo;Merck Sharp &amp; Dohme LLC&rdquo; and writing <code>large pharma</code>, or a raw
<code>2021-06-08</code> completion date into <code>H1 2021</code>. That's why it needs a <em>model</em>,
not a parser. Here is a real held-out trial (NCT03631407), with TrialScout's actual output:</p>
"""),
  ("rawoutput", '''{
  "brief_title": "Safety and Efficacy of Vicriviroc (MK-7690) in Combination With
                  Pembrolizumab (MK-3475) in Advanced/Metastatic Microsatellite
                  Stable (MSS) Colorectal Cancer (CRC)",
  "phases": ["PHASE2"],          "overall_status": "COMPLETED",
  "lead_sponsor": "Merck Sharp & Dohme LLC", "lead_sponsor_class": "INDUSTRY",
  "primary_completion_date": "2021-06-08",
  "conditions": ["Colorectal Neoplasms"],
  "interventions": [{"type": "DRUG", "name": "Vicriviroc"},
                    {"type": "BIOLOGICAL", "name": "Pembrolizumab"}],
  "primary_outcomes": [{"measure": "Objective Response Rate (ORR) per RECIST 1.1"}],
  "enrollment": 41, "allocation": "RANDOMIZED", "masking": "NONE", "n_arms": 2
}''', "the input: NCT03631407's record from ClinicalTrials.gov (trimmed)"),
  ("rawoutput", '''{
  "nct_id": "NCT03631407",
  "phase": "Phase 2",
  "indication": "Microsatellite stable (MSS) advanced/metastatic colorectal cancer",
  "modality": "combination",
  "primary_endpoint_type": "objective response rate (ORR)",
  "sponsor_type": "large pharma",
  "est_readout": "H1 2021",
  "risk_flags": ["open-label", "surrogate endpoint", "biomarker-restricted",
                 "small enrollment (<50)"],
  "investor_note": "This randomized Phase 2 trial tests whether adding vicriviroc (a CCR5
                    inhibitor) to pembrolizumab (anti-PD-1) improves ORR over pembrolizumab
                    alone in MSS-CRC, a population historically excluded from checkpoint
                    benefit. A positive result could support a new combination in this
                    immunotherapy-resistant subgroup. Key caveats are the small actual
                    enrollment of 41, ORR as a surrogate endpoint, and the biomarker-restricted
                    (MSS only) population limiting addressable market breadth."
}''', "TrialScout's actual output for this real trial"),
  ("filecode", "track-b-trialscout/schema/trial_readout.schema.json",
   "The output contract (excerpt): controlled vocabularies the model must pick from.",
   '"modality": {', "Empty array if none apply."),
  ("gloss", r"""
<p><b>What this is:</b> a JSON Schema, the <em>contract</em> for the model's output. Each enum
(<code>modality</code>, <code>primary_endpoint_type</code>, <code>sponsor_type</code>,
<code>risk_flags</code>) is a closed list of allowed strings. Constraining the output this way does
two jobs at once: it makes a small model's task tractable (pick from a menu, don't free-write), and
it lets us <em>measure</em> correctness later by simple comparison, with no human grading the bulk of it.</p>
"""),
  ("callout", "aside", "Structured-in, structured-out", r"""
<p>This shape (a messy record in, a strict object out) is where small models genuinely beat the
&ldquo;just ask a chatbot&rdquo; approach: it's cheap, deterministic enough to trust, and trivially
pluggable into a spreadsheet or a pipeline. It's also why the <em>same</em> recipe transfers to any
extraction task (SEC filings, lab reports, support tickets), not just trials.</p>
"""),
 ],
},

{
 "id": "distill", "num": "2", "title": "Distillation: a strong model writes the textbook",
 "blocks": [
  ("prose", r"""
<p>To fine-tune the student we need a pile of correct examples (1,500 here): trial in, perfect readout
out. Writing those by hand would take an analyst weeks. So we <strong>distill</strong>: a strong, expensive
model (Claude Sonnet) reads each trial and writes the gold answer, and the small student then learns
to reproduce those answers. The teacher's judgement becomes the student's training data.</p>
"""),
  ("prose", r"""
<p>Step back and name it: this is plain <strong>supervised learning</strong>, training on labeled
<code>(input → correct output)</code> pairs. Part 1 was <em>self-</em>supervised: the next character was
a free label already sitting in the text, so nobody had to annotate anything. Here there is no free label;
we must <em>supply</em> the right readout for each trial. (Done to an already-pretrained model, this is
called <strong>supervised fine-tuning</strong>.) The only unusual part is <em>where the labels come
from</em>: not human annotators, but a stronger model. Training a small model on a big model's outputs is
<strong>knowledge distillation</strong>.</p>
"""),
  ("diagram", DISTILL_SVG,
   "Distillation: the expensive teacher (Claude) writes structured answers for 1,500 trials; "
   "those become the gold labels the cheap student (Qwen) is fine-tuned to reproduce."),
  ("filecode", "track-b-trialscout/train/make_gold.py",
   "The teacher call: Claude is forced to answer through the schema, so every label is valid.",
   "r = client.messages.create(", 'Return the readout."}],'),
  ("gloss", r"""
<p><b>The key moves:</b></p>
<ul>
<li><code>tool_choice={"type": "tool", "name": "emit_readout"}</code>: <b>forced tool-use.</b> The
teacher can't free-write; it must call the <code>emit_readout</code> tool, whose arguments <em>are</em>
the schema. So every answer comes back already valid and parseable, with no JSON wrangling.</li>
<li><code>temperature=0</code>: deterministic, no creative drift; we want the teacher's single best call.</li>
<li><code>system=SYS</code>: the rules + worked examples, marked <em>prompt-cached</em> so the big
static prefix is billed once, not per trial. That (plus a cap and a pilot gate) kept the whole
labeling run to about <strong>$14</strong>.</li>
</ul>
"""),
  ("callout", "key", "Teacher quality caps student quality", r"""
<p>This is distillation's iron rule: the student can only get as good as the answers it's
shown. A weak teacher silently ceilings the whole project, so we pay for a strong one (Sonnet), not a
cheap one. The student will end up <em>near</em> the teacher, never above it. (We'll see that ceiling
bite, hard, in §8.)</p>
"""),
  ("callout", "aside", "Automating a job that used to be manual", r"""
<p>The slow, expensive part of supervised learning has always been <em>getting the labels</em>: a human
reading each example and hand-writing the answer. Labeling 1,500 trials that way would take an
analyst weeks. Distillation collapses it to a few hours and about <strong>$14</strong>: the teacher does
the tedious annotation. Cheap, fast, scalable labeled data is one of the biggest unlocks in modern ML,
and the same move works for <em>any</em> structured-extraction task, not just trials.</p>
"""),
 ],
},

{
 "id": "pipeline", "num": "3", "title": "The data pipeline (and not burning money)",
 "blocks": [
  ("prose", r"""
<p>Generating labels with a paid API, unattended, demands guardrails. The labeling script fetches
trials from the free ClinicalTrials.gov API, then calls the teacher with three safety nets: a hard
<strong>cost cap</strong>, a 10-trial <strong>pilot gate</strong> (abort before the bulk run if quality
is poor), and <strong>resumable</strong> writes (a crash loses nothing).</p>
"""),
  ("filecode", "track-b-trialscout/train/make_gold.py",
   "The pilot gate: label 10, check validity, and refuse the bulk spend if they're not good.",
   "pilot = todo[:10]", "out_f.close(); return"),
  ("gloss", r"""
<p><b>What this says:</b> label the first 10 trials, count how many come back schema-valid, and if
fewer than 8 pass, <em>stop before spending on the other 1,490</em>: a broken prompt fails cheap, not
at full cost. The bulk loop (not shown) adds the hard dollar cap and appends each result to disk as it
arrives. The clean gold is then split 80/10/10 into train / validation / test sets.</p>
"""),
  ("callout", "aside", "Why the held-out test set matters", r"""
<p>That final 10% (150 trials the model never trains on) is the only honest measure of whether it
learned the <em>task</em> versus memorised the training set. Every score in §6 is on this held-out set.
Keeping it frozen is what makes the numbers trustworthy.</p>
"""),
 ],
},

{
 "id": "lora", "num": "4", "title": "LoRA: a small patch on a big model",
 "part": "Fine-tuning", "part_banner": "Stage 3 · Fine-tuning",
 "blocks": [
  ("prose", r"""
<p>Now the fine-tune. The naïve way (update all 4 billion of Qwen's parameters) needs far more
memory than a laptop has, and risks the model forgetting everything else it knows. The standard fix is
<strong>LoRA</strong> (Low-Rank Adaptation): <em>freeze</em> the entire base model and train only a
small set of extra &ldquo;adapter&rdquo; weights that sit alongside it. You learn a tiny <em>patch</em>,
not a new model.</p>
<p>Two questions worth answering before the command. <em>Where does the adapter come from?</em> It's
created, not chosen: when the run starts, the trainer bolts small blank matrices alongside the frozen
weights, initialised so they have zero effect, and gradient descent writes into them &mdash; they are
the only parameters allowed to move. The 28&nbsp;MB file this run produces <em>is</em> the adapter; it
didn't exist before training, and on its own it's useless &mdash; it only means something snapped onto
its base model. <em>And is there a menu of adapters to pick from?</em> Not for a new task. What you pick
are its dials: how many of the model's layers get a patch (we adapt the top 16) and how wide each patch
is (the <em>rank</em>, which we leave at the trainer's default). Ready-made adapters do get shared
around for <em>existing</em> tasks &mdash; a downloadable &ldquo;LoRA&rdquo; for an image model is
exactly this kind of file &mdash; but nobody has trained one for trial readouts, which is rather the
point of this chapter.</p>
"""),
  ("diagram", LORA_SVG,
   "LoRA: the billions of base-model parameters stay frozen; training only adjusts a small adapter "
   "(~28 MB of weight deltas). At runtime you load the base and snap the adapter on top."),
  ("filecode", "track-b-trialscout/train/run_phase3.py",
   "The actual fine-tune command (MLX's LoRA trainer).",
   'cmd = [sys.executable, "-m", "mlx_lm", "lora",',
   '"--adapter-path", str(adapter), "--grad-checkpoint", "--mask-prompt", "--seed", "0"]'),
  ("gloss", r"""
<p><b>Reading the flags:</b> <code>--fine-tune-type lora</code> picks the adapter approach;
<code>--num-layers 16</code> attaches adapters to the top 16 layers; <code>--iters 700</code>,
<code>--batch-size 4</code>, <code>--learning-rate 1e-4</code> are the same training-loop dials from
Part 1 (steps, batch, step-size): gradient descent, unchanged, just pointed at this task.
<code>--mask-prompt</code> means the loss is computed only on the <em>answer</em> tokens, not the trial
text, so the model learns to <em>produce</em> readouts, not echo inputs.</p>
<p>The result: train loss fell <strong>2.56 → 0.16</strong> in ~50 minutes on the Mac, producing a
28 MB adapter. That's the whole trained model: a small delta you apply on top of the public base.</p>
"""),
 ],
},

{
 "id": "eval", "num": "5", "title": "Evaluation: the part that makes it real",
 "blocks": [
  ("prose", r"""
<p>In Part 1 we judged the model by <em>reading</em> its output: fine for &ldquo;does this look like
English?&rdquo;, useless for &ldquo;is this <em>correct</em>?&rdquo;. A useful model needs a real
scorecard. So the eval harness is a first-class deliverable, not an afterthought: it runs the student
over the 150 held-out trials and scores each field against the gold answer.</p>
"""),
  ("diagram", EVAL_SVG,
   "The eval: for every held-out trial, the student predicts a readout; structured fields are scored "
   "by accuracy/F1, the free-text note by a Claude judge, and rolled into one overall score vs the baseline."),
  ("filecode", "track-b-trialscout/eval/infer_and_score.py",
   "Load base + adapter, generate a readout per test trial, parse it, and score it.",
   "model, tok = load(args.model, adapter_path=args.adapter)", "res = score(test_set, preds)"),
  ("gloss", r"""
<p><b>What this says:</b> <code>load(model, adapter_path=...)</code> loads the frozen base and snaps the
LoRA adapter on top (that's how LoRA is consumed). For each trial it builds the <em>same</em> prompt used
in training, generates text, pulls the first <code>{…}</code> object out, and snaps any near-miss enum
value to the closest legal one (so eval matches what the deployed server does). <code>score()</code> then
compares the six scoreable fields to gold (accuracy and macro-F1 for the four enums, exact match for
<code>est_readout</code>, set-F1 for the risk-flag list; F1 is a 0–1 score balancing false positives
against misses, 1.0 perfect), exactly the metrics the baseline was measured with, so the comparison is fair.</p>
"""),
  ("callout", "aside", "Two kinds of grading", r"""
<p>Six structured fields grade themselves: the four enums by string match, <code>est_readout</code> by
exact match, and the <code>risk_flags</code> set by overlap. Free text can't: <code>investor_note</code>
is scored by <strong>Claude-as-judge</strong> (a separate model call rates the note for faithfulness),
and <code>indication</code>, free text too, isn't auto-scored at all. Automatic where possible,
model-graded where necessary.</p>
"""),
 ],
},

{
 "id": "result", "num": "6", "title": "The result",
 "part": "The result", "part_banner": "Stage 4 · The result",
 "blocks": [
  ("prose", r"""
<p>Here is the payoff, on the 150 trials the model never saw: the fine-tuned Qwen student against the
&ldquo;majority-class&rdquo; baseline (always guess the most common value for each field), which is the
floor any real model must clear:</p>
"""),
  ("table", r"""
<table>
<thead><tr><th>Field</th><th>Baseline (floor)</th><th>Qwen student</th><th>Lift</th></tr></thead>
<tbody>
<tr><td><b>overall structured</b></td><td>0.368</td><td><b>0.922</b></td><td><b>+0.554</b></td></tr>
<tr><td>valid JSON</td><td>—</td><td>1.000</td><td>—</td></tr>
<tr><td>phase</td><td>0.447</td><td>1.000</td><td>+0.553</td></tr>
<tr><td>modality</td><td>0.413</td><td>0.773</td><td>+0.360</td></tr>
<tr><td>primary_endpoint_type</td><td>0.280</td><td>0.900</td><td>+0.620</td></tr>
<tr><td>sponsor_type</td><td>0.673</td><td>0.980</td><td>+0.307</td></tr>
<tr><td>est_readout</td><td>0.033</td><td>0.993</td><td>+0.960</td></tr>
<tr><td>risk_flags (set-F1)</td><td>0.364</td><td>0.884</td><td>+0.520</td></tr>
</tbody></table>
"""),
  ("callout", "key", "What this number means", r"""
<p><strong>0.368 → 0.922.</strong> The fine-tuned 4B model (trained for under an hour on a laptop, run
for free) nearly reproduces the expensive Claude teacher, and produces valid JSON <em>every single
time</em>. The biggest lifts land where the task is most learnable: <code>est_readout</code> (a
deterministic date → &ldquo;H1/H2 YYYY&rdquo; rule, 0.03 → 0.99) and <code>phase</code> (perfect). This
is the win Part 1 was building toward: the same training loop (tokens, loss, gradient descent) now
doing a real job, well.</p>
<p>One field still lags: <code>modality</code>, at 0.77. Can we push it higher by running an improvement
<em>loop</em>? We try, in <a href="#ceiling">§8</a>.</p>
"""),
 ],
},

{
 "id": "ab", "num": "7", "title": "Decide by eval, not by faith",
 "blocks": [
  ("prose", r"""
<p>Which base model to fine-tune, Qwen3-4B or Google's Gemma 4 E2B? We didn't argue about it; we ran
both through the <em>same</em> harness and let the score decide. That's the discipline: model choice is a
measurement, not a preference.</p>
<p>In the end Qwen won by default and by margin. Gemma 4 E2B <em>failed to train at all</em>: the only
available checkpoint is a multimodal (vision+text) build whose weights the LoRA trainer couldn't target.
And Qwen's 0.922 is so near the ceiling that even a perfectly-trained Gemma would have to beat it to flip
the call, implausible on this task. So the measured decision is Qwen, robustly.</p>
"""),
  ("callout", "aside", "A failed arm is still a result", r"""
<p>&ldquo;Gemma didn't train&rdquo; isn't a gap in the write-up; it's a finding (and a real-world gotcha:
check whether a checkpoint is text-only before you plan around it). The honest version of an A/B includes
the arm that didn't work and why it doesn't change the conclusion.</p>
"""),
 ],
},

{
 "id": "ceiling", "num": "8", "title": "Can you beat the teacher? (The error-mining loop)",
 "blocks": [
  ("prose", r"""
<p>The weakest field was <code>modality</code> at 0.77. The natural next move is a
<strong>recursive improvement loop</strong>, a general pattern worth naming: <em>mine the model's errors
→ generate targeted new training data for exactly those cases → retrain → measure → repeat</em>, each
pass trying to climb a little higher. It's the honest, buildable kernel of the &ldquo;self-improving
AI&rdquo; idea. So we ran one turn of it: snapped near-miss enums for free (auto-correcting almost-right values to the nearest allowed one; that alone nudged overall 0.922 → 0.925), then added 300 fresh gold
examples of the rare modalities the model kept missing.</p>
<p>It barely moved further: a <strong>statistical wash</strong>, overall 0.925 → 0.930, with modality's gain
offset by a small dip elsewhere. That's the signature of a <strong>plateau</strong>: a loop like this
climbs at first, then flattens. Digging in showed why: the residual <code>modality</code> errors cluster
on the genuinely ambiguous <code>combination</code> boundary, cases where the <em>teacher's own labels</em>
disagree. You can't loop your way out of that with more data; it's <strong>label noise</strong>, and it
sets a hard ceiling.</p>
"""),
  ("callout", "key", "The two ceilings", r"""
<p>This is the honest lesson of the whole project: <strong>(1) you can't beat your teacher</strong>, the
student asymptotes <em>to</em> the teacher, not past it; and <strong>(2) you can't out-data label noise</strong>:
once the remaining errors are cases the teacher itself gets inconsistently, more examples just teach the
inconsistency. A <em>legitimately</em> self-improving model would need a cheap, non-gameable <em>verifier</em>
of truth, not just more teacher labels. That's the real frontier, and the honest place to stop here.</p>
"""),
 ],
},

{
 "id": "serve", "num": "9", "title": "Packaging it as a callable expert",
 "part": "Ship it", "part_banner": "Stage 5 · Ship it",
 "blocks": [
  ("prose", r"""
<p>A trained adapter on disk isn't useful yet. The last step makes TrialScout <em>callable</em>: wrapped
as an <strong>MCP</strong> tool (Model Context Protocol, the standard way to expose a tool to an AI client
like Claude). Now any assistant can ask it for a readout by trial ID, and it answers locally, no API spend.</p>
"""),
  ("filecode", "track-b-trialscout/serve/trial_readout_server.py",
   "The MCP tool: give it an NCT id, get back a schema-validated readout.",
   "@mcp.tool(", ") -> str:"),
  ("gloss", r"""
<p><b>What this says:</b> the <code>@mcp.tool</code> decorator registers <code>trial_readout</code> as a
callable tool with a typed input (an NCT id, validated by a regex) and a choice of markdown or JSON output.
Under the hood it fetches the trial from ClinicalTrials.gov, runs the fine-tuned model locally, and validates
the result against the schema before returning it. The annotations (<code>readOnlyHint</code>,
<code>idempotentHint</code>) tell the calling assistant it's a safe, repeatable read. This is the &ldquo;callable
expert&rdquo; the whole pipeline was for.</p>
"""),
 ],
},

{
 "id": "arc", "num": "10", "title": "The arc, closed: running it yourself",
 "blocks": [
  ("prose", r"""
<p>That's the full arc. Part 1 built a language model from nothing to <em>understand</em> the machinery;
Part 2 took a pretrained one and <em>specialised</em> it into a measurably useful expert, for the price of
some patience and about $14 of teacher calls. The giants are not different in kind; they are this, at scale.
And the techniques here (distillation, LoRA, eval-driven decisions) are exactly how a small team turns a
big open model into something that does <em>their</em> job.</p>
"""),
  ("filecode", "track-b-trialscout/README.md",
   "Reproduce it (read-along note below): the four commands of the pipeline.",
   "# 1. Fetch trials", "uv run python track-b-trialscout/eval/harness.py --pred"),
  ("callout", "aside", "Read-along vs. run-it-yourself", r"""
<p>Unlike Part 1, this chapter is mostly <strong>read-along</strong>: the gold dataset and the trained adapter
are gitignored (regenerable, not committed), and step 2 spends ~$14 of Anthropic API to recreate the labels.
Everything you need to reproduce it is above and in the
<a href="https://github.com/JEM-Fizbit/small-model-lab/tree/main/track-b-trialscout">repo</a>, but you can absolutely
just <em>read</em> it and take the method with you.</p>
"""),
  ("callout", "key", "Where this goes next", r"""
<p>The honest finding (§8) points at the real frontier: a model that improves itself needs a
<em>verifier</em> of truth it can't game, not just more teacher labels. TrialScout proved the
<em>method</em>. That harder idea is where this lab is headed, but the chapter isn't written yet:
for now, the arc ends here.</p>
<p>Retrace the arc: <strong><a href="../ideas/">Part 0 · Concepts</a></strong> (the ideas) ·
<strong><a href="../track-a/">Part 1 · Pre-training</a></strong> (the build) ·
<a href="../">the lab home</a>.</p>
"""),
 ],
},

]
