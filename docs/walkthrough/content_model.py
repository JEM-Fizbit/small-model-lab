"""Shared tuned-model figures and a native reference page.

The chapter gives the route and totals; this reference retains the detailed
definitions and parameter arithmetic. Both use the site's chapter template.
"""

OVERVIEW = r"""
<figure class="imgfig model-figure" id="model-architecture" aria-labelledby="architecture-caption">
<ol class="model-flow">
<li>
<span class="model-step">1 · Embed</span>
<strong>Token + position</strong>
<p>Look up the two learned vectors and add them.</p>
<span class="model-shape">384 values per token position</span>
</li>
<li>
<span class="model-step">2 · Process</span>
<strong>Six transformer blocks</strong>
<div class="model-stack" aria-hidden="true"><span>1</span><span>2</span><span>3</span><span>4</span><span>5</span><span>6</span></div>
<p>Attention shares context; the MLP transforms each position.</p>
<span class="model-shape">384 values in and out of each block</span>
</li>
<li>
<span class="model-step">3 · Predict</span>
<strong>Normalise, then score</strong>
<p>Final LayerNorm, then the separate output head.</p>
<span class="model-shape">8,192 scores; softmax gives probabilities, sampling picks the next token</span>
</li>
</ol>
<figcaption id="architecture-caption">The model reuses this path for every next-token prediction.
The six blocks have the same structure and separate learned weights.
</figcaption>
</figure>
"""

PARAMETER_TABLE = r"""
<table class="model-tally">
<thead><tr><th scope="col">Component</th><th scope="col">Calculation</th><th scope="col">Parameters</th></tr></thead>
<tbody>
<tr><th scope="row">Token embeddings</th><td>8,192 × 384</td><td>3,145,728</td></tr>
<tr><th scope="row">Learned position embeddings</th><td>256 × 384</td><td>98,304</td></tr>
<tr><th scope="row">Six transformer blocks</th><td>6 × 1,774,464</td><td>10,646,784</td></tr>
<tr><th scope="row">Final layer normalisation</th><td>2 × 384</td><td>768</td></tr>
<tr><th scope="row">Separate output head</th><td>384 × 8,192 + 8,192 biases</td><td>3,153,920</td></tr>
<tr><th scope="row">Total</th><td>All five components</td><td><strong>17,045,504 ≈ 17.05 million</strong></td></tr>
</tbody></table>
"""

BLOCK_FLOW = r"""<figure class="imgfig model-figure" id="block-flow" aria-labelledby="block-flow-caption">
<div class="block-flow">
<div>
<span class="model-step">First · Gather context</span>
<div class="block-route"><span>Norm</span><span aria-hidden="true">→</span><strong>Attention</strong><span aria-hidden="true">→</span><span aria-label="add incoming vector">+</span></div>
<div class="block-skip">incoming vector</div>
<p>Use information from the current and earlier positions, never future tokens.</p>
</div>
<div>
<span class="model-step">Then · Transform features</span>
<div class="block-route mlp"><span>Norm</span><span aria-hidden="true">→</span><strong>MLP</strong><span aria-hidden="true">→</span><span aria-label="add this stage's incoming vector">+</span></div>
<div class="block-skip">this stage’s incoming vector</div>
<p>The same feedforward weights work on each position independently.</p>
<span class="model-shape">384 → 1,536 → 384; GELU between the layers</span>
</div>
</div>
<figcaption id="block-flow-caption">Each stage normalises its input, computes an adjustment,
then adds that stage's incoming vector back. This addition is the residual connection.
The MLP is one part of the block.</figcaption>
</figure>"""

BLOCK_NOTES = r"""
<p>The <strong>transformer blocks</strong> hold most of the parameters. All six have the same
architecture and parameter count, but each block has its <strong>own learned weights</strong>.
Within a block, those weights are shared across token positions: there is no separate set for
every token.</p>
"""

BLOCK_DETAIL = r"""
<p>Start with the model's <strong>width: 384 numbers per token position</strong>. A token is a
piece of text mapped to an ID (<a href="../ideas/#tokens">the token primer</a>); its position is
where that piece sits in the sequence. The embedding table's stored numbers are learned
<strong>parameters</strong>. Once looked up, added to position embeddings and processed by the
blocks, the flowing vectors are <strong>activations</strong>: input-dependent values computed
using those parameters. Producing another vector does not create or learn another set of weights.</p>
<p>Every block receives and returns a vector of width 384, so the blocks fit together and their
residual connections can add vectors of the same size. A whole transformer block includes
<strong>attention and an MLP</strong>, plus normalisation and residual connections; the MLP is
just one part. Within each block, the two stages run in this order:</p>
<figure class="imgfig model-figure" id="block-flow" aria-labelledby="block-flow-caption">
<div class="block-flow">
<div>
<span class="model-step">First · Gather context</span>
<div class="block-route"><span>Norm</span><span aria-hidden="true">→</span><strong>Attention</strong><span aria-hidden="true">→</span><span aria-label="add incoming vector">+</span></div>
<div class="block-skip">incoming vector</div>
<p>Use information from the current and earlier positions, never future tokens.</p>
</div>
<div>
<span class="model-step">Then · Transform features</span>
<div class="block-route mlp"><span>Norm</span><span aria-hidden="true">→</span><strong>MLP</strong><span aria-hidden="true">→</span><span aria-label="add this stage's incoming vector">+</span></div>
<div class="block-skip">this stage’s incoming vector</div>
<p>The same feedforward weights work on each position independently.</p>
<span class="model-shape">384 → 1,536 → 384; GELU between the layers</span>
</div>
</div>
<figcaption id="block-flow-caption">Each stage normalises its input, computes an adjustment,
then adds that stage's incoming vector back. This addition is the residual connection.
The MLP is one part of the block.</figcaption>
</figure>
<p>The width and the MLP's expansion determine the sizes of the two main sets of matrices:</p>
<ul>
<li><strong>Attention mixes information across token positions</strong>, drawing on the current
and earlier positions. Its query, key and value projections each map 384 numbers to 384 numbers,
and the output projection does the same. That makes <strong>4 × 384 × 384 = 589,824
weights</strong>. The code packs the first three into one larger matrix, but the count is the same.</li>
<li><strong>The feedforward MLP transforms each position independently</strong>, using the same
weights at every position. Its first layer expands 384 numbers to 1,536, GELU adds a nonlinear
bend, and its second layer brings 1,536 back to 384. The wider middle gives the block more room
to transform features before returning to the shared width. We chose a <strong>4× expansion</strong>, so these two matrices contain
<strong>384 × 1,536 + 1,536 × 384 = 1,179,648 weights</strong>.</li>
</ul>
<p>Add <strong>3,456 biases</strong> across those projections and feedforward layers, plus
<strong>1,536 learned scales and offsets</strong> in the block's two layer normalisations, and
one block totals <strong>1,774,464 parameters</strong>. Six separately learned blocks therefore
contribute <strong>6 × 1,774,464 = 10,646,784</strong>.</p>
<p>Width, the feedforward expansion multiplier and the number of blocks are related design
choices. Keeping the multiplier fixed, block parameters grow roughly with the <strong>square of
width</strong>: doubling width makes the matrices about four times as large. Doubling the number
of blocks instead doubles the stack's parameter count. A larger expansion multiplier increases
the feedforward part. These choices trade capacity against memory and compute, so their value
needs evaluation rather than an assumption that bigger is always better.</p>
<p>Vocabulary size determines the input embedding table and output head, but does not change
these block matrices at a fixed width. A longer context makes attention do more work without
enlarging those matrices, although this model's learned position table grows with its maximum
context length. The six attention heads divide the 384 numbers into 64 per head; at a fixed
width, changing the number of heads does not multiply the projection parameter count.</p>
"""

OUTPUT_NOTES = r"""<p>The <strong>final LayerNorm</strong> normalises the feature values within each position's vector
before the output head reads it. Its 384 learned scales and 384 shifts account for
<strong>768 parameters</strong>; it does not mix positions.</p>
<p>The <strong>output head</strong> maps each final 384-number vector to 8,192 vocabulary scores,
one for each possible next token. <strong>384 → 8,192 describes the input and output shapes</strong>;
the parameter count is <strong>384 × 8,192 = 3,145,728 weights</strong>, plus
<strong>8,192 biases</strong>, totalling <strong>3,153,920</strong>. This is a separate,
<em>untied</em> matrix: it does not reuse the input embedding table.</p>
<p>These scores are called <strong>logits</strong>. At generation time, <strong>softmax</strong>
converts the last position's temperature-adjusted scores into probabilities that sum to 1; it has no learned
parameters. Sampling uses those probabilities to choose the next token, which is appended to
the input for the next step (<a href="../track-a/#generate">the generation loop in §9</a>).</p>
"""

META = {
    "is_model_reference": True,
    "title": "Inside the tuned GPT · Model reference",
    "subtitle": "The model's components, definitions and all 17,045,504 learned parameters.",
}

HERO = r"""
<p class="kicker">small-model-lab · Model reference</p>
<h1>Inside the tuned GPT</h1>
<p class="lede">A guide to the model in Notebook 02: what flows through it, what each
component does, and where all <strong>17,045,504 learned parameters</strong> live.</p>
<p><a href="../track-a/#tuned-model">← Return to Part 1 · §11, the tuned model</a></p>
<nav class="reference-jumps" aria-label="On this reference page">
<strong>On this page</strong>
<a href="#overview">The whole path</a>
<a href="#embeddings">Tokens &amp; embeddings</a>
<a href="#block-size">Inside a block</a>
<a href="#prediction">The output head</a>
<a href="#parameter-count">All parameters</a>
</nav>
"""

MAIN_BLOCKS = [
    ("prose", r"""
<p>Before looking at the individual upgrades, put their model in view. Notebook 02 uses
8,192 tokens, a width of 384 and six transformer blocks. Those dimensions describe different
parts of the same path from text to a next-token prediction.</p>
<p class="reference-link"><strong>Keep the full model reference to hand:</strong>
<a href="../model/">Inside the tuned GPT — definitions, diagrams and every parameter →</a></p>
"""),
    ("prose", OVERVIEW),
    ("prose", r"""
<h3 id="parameter-count">Where all 17.05 million parameters live</h3>
<p><strong>8,192 tokens × 384 numbers = 3,145,728 parameters</strong> counts only the token
embedding table. The position table, six blocks, final normalisation and separate output head
bring the total to <strong>17,045,504</strong>. This is Notebook 02's tuned model, separate from
Notebook 01's smaller character-level model in <a href="#block">§6</a>.</p>
"""),
    ("table", PARAMETER_TABLE),
    ("prose", BLOCK_NOTES),
    ("prose", r"""
<h3 id="block-size">Inside each transformer block</h3>
<p>Every block receives and returns <strong>384 values per token position</strong>. The flowing
vectors are <strong>activations</strong>: values computed from the current input using the learned
parameters. They are not another set of learned weights. Each block contains attention and a
feedforward MLP, with normalisation and a residual connection around each stage.</p>
"""),
    ("prose", BLOCK_FLOW),
    ("prose", r"""
<p>The MLP expands 384 values to 1,536 and brings them back to 384. Together, attention, the MLP
and the two layer norms contain <strong>1,774,464 parameters per block</strong>. Six blocks account
for <strong>10,646,784</strong> of the model's parameters. The
<a href="../model/#block-size">full reference breaks down the matrices, biases and layer norms</a>
and explains how width, depth, heads and context affect the count.</p>
<p>After the blocks, final LayerNorm and a separate output head produce 8,192 scores. At generation
time, softmax turns the last position's temperature-adjusted scores into probabilities, and sampling
chooses the next token. The <a href="../model/#prediction">output-head reference</a> explains why its
384-to-8,192 shape means <strong>3,153,920 learned parameters</strong>.</p>
<p>With that structure in mind, the next sections return to the upgrades themselves: first the
tokenizer, then initialization and the training schedule.</p>
"""),
]

SECTIONS = [
    {"id": "overview", "num": "1", "title": "The whole path", "blocks": [
        ("prose", "<p>A language model predicts the next piece of text. Training adjusts its learned "
         "parameters to improve predictions; generation reuses them unchanged to continue the text.</p>"),
        ("prose", OVERVIEW),
    ]},
    {"id": "embeddings", "num": "2", "title": "Tokens, positions and embeddings", "blocks": [
        ("prose", r"""
<p>A <strong>token</strong> is a piece of text mapped to an integer ID. Its <strong>position</strong>
is its index in the sequence: 0, 1, 2, and so on. A <strong>vector</strong> is a list of numbers;
an <strong>embedding</strong> is a learned vector looked up for a token or a position.</p>
<p>The token table contains <strong>8,192 × 384 = 3,145,728 parameters</strong> (18.45% of this model).
The position table contains <strong>256 × 384 = 98,304 parameters</strong> (0.58%). Look up one vector
from each table and add them: 384 numbers then flow forward per position. Adding the position vector
gives the model a sense of order.</p>
<p>The stored table entries are learned <strong>parameters</strong>. The flowing vectors are
<strong>activations</strong>, computed from this input using those parameters. Producing another
vector does not create or learn another set of weights.</p>
<p><a href="../ideas/#embed">Revisit embeddings in Concepts</a> ·
<a href="../track-a/#bpe">See the tokenizer built in Part 1</a></p>
"""),
    ]},
    {"id": "block-size", "num": "3", "title": "Inside a transformer block", "blocks": [
        ("prose", BLOCK_NOTES),
        ("prose", BLOCK_DETAIL),
        ("prose", r"""
<h3 id="block-inventory">The complete inventory for one block</h3>
<p>MLP means <strong>multilayer perceptron</strong>: here, two linear layers with GELU between them.
GELU supplies a nonlinear bend; GELU and residual additions have no learned parameters.</p>
"""),
        ("table", r"""
<table>
<thead><tr><th scope="col">Component</th><th scope="col">Weights, scales &amp; offsets</th><th scope="col">Parameters</th></tr></thead>
<tbody>
<tr><th scope="row">Attention</th><td>589,824 weights + 1,536 biases</td><td>591,360</td></tr>
<tr><th scope="row">Feedforward MLP</th><td>1,179,648 weights + 1,920 biases</td><td>1,181,568</td></tr>
<tr><th scope="row">Two layer norms</th><td>2 × (384 scales + 384 shifts)</td><td>1,536</td></tr>
<tr><th scope="row">One block</th><td>All three components</td><td><strong>1,774,464</strong></td></tr>
</tbody></table>
"""),
        ("prose", "<p>Six blocks contribute <strong>10,646,784 parameters</strong>, or 62.46% of the model. "
         "The diagrams show structure, not proportional parameter areas. "
         '<a href="../track-a/#init">Continue to initialization and stability in Part 1 →</a></p>'),
    ]},
    {"id": "prediction", "num": "4", "title": "From the final vector to the next token", "blocks": [
        ("prose", OUTPUT_NOTES),
        ("prose", "<p>The separate output head holds 18.50% of this model's parameters. Temperature "
         "adjustment, softmax and sampling add no learned parameters.</p>"),
    ]},
    {"id": "parameter-count", "num": "5", "title": "All 17,045,504 parameters", "blocks": [
        ("prose", "<p>Add the two embedding tables, six blocks, final LayerNorm and separate output "
         "head. The 384-to-8,192 output shape is not itself a parameter count: the matrix and biases "
         "are what we count.</p>"),
        ("table", PARAMETER_TABLE),
        ("prose", r"""
<p>These were practical design choices, not established optima.
<a href="../track-a/#upgrades">Part 1 explains how they were chosen and what a production
development process would test</a>.</p>
<p><a href="../track-a/#tuned-model">← Return to the tuned-model section in Part 1</a></p>
"""),
    ]},
]
