"""content_concepts.py — Part 0 · Concepts (How it works) of the slm-lab walk-through.

A code-free conceptual tour. It REUSES the diagrams authored in content.py (imported
below, byte-for-byte) and the most-iterated callouts, with tightened connective prose.
The runnable code lives in Part 1 (content.py); this page links across to it.

build.py renders this to site/ideas/index.html.
"""

from content import (  # diagrams + the Python primer live in content.py
    LANDSCAPE_SVG, CYCLE_SVG, LINEAR_SVG, EMBED_SCATTER_SVG, EMBED_HEATMAP_SVG,
)

META = {
    "title": "How a language model works: the ideas",
    "subtitle": "Part 0 · Concepts: the plain-English principles behind the build, no code.",
}

HERO = r"""
<p class="kicker">slm-lab · Part 0 · Concepts</p>
<h1>How a language model works</h1>
<p class="lede">The ideas, in plain English, with no code: what a language model actually <em>is</em>,
how text becomes numbers, what &ldquo;learning&rdquo; means, and how the pieces fit. Read this first;
then <a href="../track-a/">Part 1</a> builds every one of these ideas in real, runnable code, and
<a href="../track-b/">Part 2</a> fine-tunes a real model into a useful expert.</p>

<div class="bigidea">
  <p><strong>The whole thing in one breath:</strong> a language model is a <strong>mathematical
  function</strong> with millions of adjustable numbers (its <strong>parameters</strong>) that, given
  some text so far, predicts what comes next. <em>Training</em> tunes those numbers (millions of tiny
  nudges) until coherent language falls out. <em>Generation</em> runs the function in a loop to write.</p>
  <p>Everything below unpacks that: how text becomes numbers, how the model &ldquo;looks back&rdquo; at
  what it has read, how it measures its own mistakes, and how it slowly improves.</p>
</div>

<p class="readnote"><strong>No Python here.</strong> This page is concepts and pictures only. Every idea
reappears as real code in <a href="../track-a/">Part 1 · Pre-training</a>; each section links across to
where it's built.</p>
"""

SECTIONS = [

{
 "id": "what", "num": "1", "title": "What a model actually does",
 "part": "The idea", "part_banner": "Part 0 · Concepts",
 "blocks": [
  ("prose", r"""
<p>Strip away the mystique and a language model does one narrow thing: <strong>given the text so far,
it predicts what comes next.</strong> Not whole thoughts, just the next small chunk (a <em>token</em>:
a word or word-piece). To write a sentence it just does this over and over, each new token appended and
fed back in. That's it. Everything else is machinery in service of making that one prediction good.</p>
<p>So &ldquo;a model that writes&rdquo; is really a model that <em>scores what's likely next</em>, run in
a loop. The skill isn't generating; it's the prediction underneath.</p>
"""),
  ("callout", "key", "A model is a function, not a mind", r"""
<p>It helps to picture a giant mathematical function: text in → a probability for every possible next
token out. The function's behaviour is fixed by its <strong>parameters</strong>: millions of numbers
set during training. No look-ups of &ldquo;facts,&rdquo; no rules someone wrote, just numbers, multiplied
and added, shaped by training to make good predictions.</p>
"""),
 ],
},

{
 "id": "tokens", "num": "2", "title": "Step 1: text becomes numbers (tokens)",
 "blocks": [
  ("prose", r"""
<p>A model can't do arithmetic on letters, so the first move is to turn text into numbers. The text is
chopped into <strong>tokens</strong>: common chunks (whole words like <code>fox</code>, or word-pieces),
each with an integer <strong>ID</strong> (its index in a fixed list called the <em>vocabulary</em>).
&ldquo;fox&rdquo; might be token #1234. That's all a token is to the model: an ID.</p>
<p>The reverse runs at the end: the model's predicted ID is mapped back to its chunk of text, and the
pieces are glued together into words. <a href="../track-a/#data">Part 1 builds the tokenizer →</a></p>
"""),
 ],
},

{
 "id": "embed", "num": "3", "title": "Step 2: tokens become vectors (embeddings)",
 "blocks": [
  ("prose", r"""
<p>An ID like #1234 carries no <em>meaning</em>: #1235 isn't &ldquo;one more&rdquo; than fox. So each
token is turned into a <strong>list of numbers</strong>, its <strong>embedding</strong> (256 numbers in
our tiny model). Think of those numbers as coordinates that place the token in a vast &ldquo;meaning
space,&rdquo; where tokens used in similar ways land near each other.</p>
"""),
  ("diagram", EMBED_SCATTER_SVG,
   "Each token is its own point in 256-dimensional space (2 dimensions shown here); similar meanings "
   "cluster. The axes are two of the 256 learned attributes/dimensions: loosely, fuzzy 'animal-ness' / "
   "'size' (held lightly)."),
  ("diagram", EMBED_HEATMAP_SVG,
   "The same embeddings as colours: each row is a token, each column one of the 256 dimensions, each "
   "cell the token's value on it (red high, blue low). Similar tokens — fox, cat, dog — show similar "
   "patterns; \"the\" differs."),
  ("callout", "aside", "Attributes = dimensions", r"""
<p>A token's embedding is a point in <strong>256-dimensional space</strong>: 256 numbers, one per
dimension. Each dimension is a <strong>learned attribute (feature)</strong>: a mathematical abstraction
capturing some statistically-shared pattern across tokens. They <strong>don't map cleanly to human
concepts</strong>, but it's often genuinely helpful to imagine them, loosely, as fuzzy attributes —
&ldquo;animal-ness&rdquo;, &ldquo;furriness&rdquo;, &ldquo;size&rdquo; — held lightly. (A token's
<em>values</em> on the dimensions are part of the model's parameters; the dimensions themselves are the
embedding's axes.)</p>
"""),
  ("callout", "key", "Where do the embeddings come from?", r"""
<p>Not from the letters, and not computed on the fly: they're <strong>learned, then looked up</strong>.
The model keeps an <strong>embedding table</strong> (one row per vocabulary token). &ldquo;fox&rdquo;
becomes an integer ID, and that ID simply <em>indexes the table</em>; row #ID <em>is</em> its 256 numbers.
There's no arithmetic on <code>f-o-x</code>.</p>
<p>Those numbers start as <strong>small random values</strong> and are <strong>parameters</strong> like any
other: gradient descent nudges them, step by step, to lower the loss. After training the table is frozen, so
the lookup is deterministic (same token → same row), but the row was <em>learned</em>, not derived from the
spelling. (Train again with a different random seed and &ldquo;fox&rdquo; settles on a different,
equally-good vector.) Tokens used in similar contexts get pushed toward similar rows, which is exactly why
the clusters above emerge on their own, with no one labelling them.</p>
"""),
 ],
},

{
 "id": "linear", "num": "4", "title": "Step 3: the linear layer (the core operation)",
 "blocks": [
  ("prose", r"""
<p>Almost the entire network is one operation, repeated: the <strong>linear layer</strong>,
<code>y = Wx + b</code>. It takes a vector of numbers in and produces a new vector out, where each output
is a <em>weighted sum</em> of all the inputs plus an offset. Stack the per-output weight-rows into a grid
<code>W</code> and the offsets into a vector <code>b</code>, and that's the whole layer: the school-line
<code>y = mx + c</code>, vectorised. The diagram below builds it from one output up to the whole model.</p>
"""),
  ("diagram", LINEAR_SVG,
   "A linear layer, drawn. ① one output (a \"neuron\") is a weighted sum of one token's numbers; ② stack "
   "a row of weights per output → the matrix W, so the layer is y = Wx + b (a vector in, a new vector "
   "out); ③ one such layer is a tiny slice of the whole ~3.24M-parameter model, whose weights are shared "
   "across every token."),
  ("callout", "key", "Parameters vs. tokens: the part people mix up", r"""
<p>A token doesn't <em>have</em> parameters. The parameters (every <code>W</code> and <code>b</code>)
<strong>are the model</strong>: fixed after training and <strong>shared</strong>, so the exact same
weights process every token, at every position. A token is just data flowing through them.</p>
<p>And the weights in the picture are a tiny slice: <em>one output of one layer</em>. Our tiny GPT stacks
4 blocks (each with several <code>W</code>s) plus the embedding and the head; add them all up and you get
the ~3.2M parameters. One layer's <code>W</code> might be 256×1024 (~262k numbers); the whole model is ~3.2M.</p>
<p>And a linear layer transforms <em>one token at a time</em>. The model's real job (read a <em>string</em>
of tokens and predict the next) needs tokens to share information, which is <em>attention</em>'s job
(next section), not the linear layers. After the stack, the last position's vector is read out to predict
the next token. <a href="../track-a/#block">Part 1 builds the block →</a></p>
"""),
 ],
},

{
 "id": "activation", "num": "5", "title": "Step 4: the bend (activations)",
 "blocks": [
  ("prose", r"""
<p>Stacking linear layers alone is pointless: a stack of straight-line operations collapses into one
straight line, and the model could only ever draw <em>lines</em>. So after each linear step the model
applies one simple <strong>nonlinear</strong> function: a <em>bend</em>. That bend is what lets depth
model curves and combinations, not just proportions.</p>
<p>Ours is <strong>GELU</strong> (a smooth version of ReLU). The famous textbook ones are <strong>ReLU</strong>
(keep positives, zero the rest) and the <strong>sigmoid</strong> (squash any number into 0–1). The whole kit
is just this: <code>Wx + b</code>, then a bend, stacked — plus the two ideas below.</p>
"""),
 ],
},

{
 "id": "attention", "num": "6", "title": "Step 5: attention, letting tokens talk",
 "blocks": [
  ("prose", r"""
<p>Linear layers process each token on its own. But meaning depends on context: &ldquo;bank&rdquo; near
&ldquo;river&rdquo; vs near &ldquo;money.&rdquo; <strong>Attention</strong> is the one step where positions
<em>look at each other</em>: each token forms a query and asks &ldquo;which earlier tokens matter to me?&rdquo;,
then pulls in a blend of their information. It's how the model carries context forward, the part that makes
it a <em>language</em> model and not a bag of independent words.</p>
"""),
  ("callout", "aside", "Why it's the heart of it", r"""
<p>Everything else (embeddings, linear layers, the bend) works token-by-token. Attention is the <em>only</em>
place information moves <em>between</em> tokens. Stack several attention+MLP blocks and the model can build
up rich, context-aware meaning before it ever makes a prediction. <a href="../track-a/#attention">Part 1
builds attention →</a></p>
"""),
 ],
},

{
 "id": "learn", "num": "7", "title": "How it learns: loss, gradients, gradient descent",
 "part": "Learning", "part_banner": "Part 0 · How learning works",
 "blocks": [
  ("prose", r"""
<p>Where do the millions of parameters come from? <strong>Training.</strong> Show the model real text with
the next token hidden, let it guess, and measure how wrong the guess was with a single number: the
<strong>loss</strong> (low = confident and right; high = wrong). Training is nothing more than making that
number smaller, over and over.</p>
<p>The trick is knowing <em>which way</em> to nudge each of the millions of parameters. That's the
<strong>gradient</strong>: for every parameter, the slope of the loss, telling you which direction, and how hard,
reduces the error. Nudge every parameter a little down its slope, and the loss drops. Do it a few thousand
times and coherent language emerges. This is <strong>gradient descent</strong>.</p>
"""),
  ("diagram", LANDSCAPE_SVG,
   "Gradient descent: picture the loss as a landscape and the model as a ball. The gradient is the "
   "downhill direction; each training step rolls the ball one step lower. Repeat a few thousand times and "
   "it settles near a valley: low loss, good predictions."),
  ("prose", r"""
<p>One pass of training is a loop of four steps, repeated on batch after batch of text:</p>
"""),
  ("diagram", CYCLE_SVG,
   "The training loop: a forward pass (guess the next tokens) → compute the loss (how wrong) → a backward "
   "pass (backpropagation: work the slopes back through every layer to get each parameter's gradient) → "
   "update (nudge every parameter a little downhill). Then repeat."),
  ("callout", "aside", "Backpropagation, in one line", r"""
<p>The <strong>backward pass</strong> (&ldquo;backprop&rdquo;) is just the chain rule from calculus run at
scale: starting from the loss, it works the slopes backward through every layer to find each parameter's
gradient efficiently. It's the engine that makes training millions of parameters feasible.
<a href="../track-a/#train">Part 1 runs the training loop →</a></p>
"""),
 ],
},

{
 "id": "generate", "num": "8", "title": "Generating text, and the one knob: temperature",
 "blocks": [
  ("prose", r"""
<p>Once trained, the model <em>generates</em> by running its prediction in a loop: feed the text so far,
get a probability for every next token, pick one, append it, repeat. &ldquo;Inference&rdquo; and
&ldquo;generation&rdquo; are the same thing: running the function forward (no learning).</p>
<p>How you <em>pick</em> from the probabilities is the one knob worth feeling: <strong>temperature</strong>.
Low temperature (~0.5) always grabs the most likely token: safe, repetitive. High (~1.1) samples more
adventurously: varied, riskier, sometimes incoherent. It's the dial between &ldquo;careful&rdquo; and
&ldquo;creative,&rdquo; and it changes nothing in the model — only how its output is sampled.
<a href="../track-a/#temperature">Part 1 lets you feel it →</a></p>
"""),
 ],
},

{
 "id": "ceiling", "num": "9", "title": "The honest ceiling, and where this goes",
 "blocks": [
  ("prose", r"""
<p>That's the whole machine: text → tokens → embeddings → stacks of (attention + <code>Wx+b</code> + a bend)
→ a final prediction, all tuned by gradient descent. A <em>frontier</em> model is exactly this, scaled up:
more dimensions, more layers, vastly more text and compute. Same ideas; different magnitude.</p>
<p>A from-scratch tiny model trained on a laptop will produce believable <em>shapes</em> of language but no
real knowledge — that's the honest ceiling, and it's the point: you can see every moving part. To get
something <em>useful</em>, you start from a model that has already paid the scale cost and
<strong>specialise</strong> it, which is Part 2.</p>
"""),
  ("callout", "key", "Now see it built", r"""
<p>Every idea here is built in real, runnable code next: <strong><a href="../track-a/">Part 1 ·
Pre-training</a></strong> trains this tiny GPT from scratch, one piece at a time. Then
<strong><a href="../track-b/">Part 2 · Post-training</a></strong> fine-tunes a real open model into a
useful clinical-trial expert, the same concepts doing a real job. ← back to
<a href="../">the lab home</a>.</p>
"""),
 ],
},

]
