# What the tiny GPT actually does off-corpus — the "capital of France" probe

<!-- GENERATED FILE — do not hand-edit. -->
<!-- Regenerate: uv run python docs/walkthrough/gen_domain_limit_probe.py -->

**Question.** Part 1 § "The honest ceiling" says the model "*only* tells toddler
stories, because TinyStories is the entire world it ever saw," and the shorthand for
that claim is "ask it the capital of France and you get *once upon a time*." Is that
true of the actual checkpoint? Every sample generated is reproduced below verbatim,
untidied, including any that contradict the claim.

Run: `docs/walkthrough/gen_domain_limit_probe.py`, 2026-08-04.

## Run configuration

| setting | value |
|---|---|
| checkpoint | `notebooks/checkpoints/tiny_gpt_v2` (the tuned notebook-02 model — the only Track A checkpoint on disk) |
| tokenizer | `notebooks/checkpoints/tiny_gpt_v2/tokenizer.json` — trained byte-level BPE, vocab 8192 |
| parameters | 17,045,504 (17.05M) |
| architecture | block_size 256, n_embd 384, n_head 6, n_layer 6 |
| seed | `0` — sample *i* uses `SEED + i`, so each sample is independently reproducible |
| temperature | 0.8 (library + `chat.py` default) |
| top-k | **none** — the sampler has no top-k; it samples over the full temperature-scaled distribution |
| max new tokens | 200 (a cap; `<|endstory|>` usually fires first) |
| stop at eos | True — stops on `<|endstory|>` |
| samples per prompt | 5 |
| sampler | `tiny_gpt.stream` — the same code path `chat.py` and notebook 02 use |

## Summary

Marker tests are crude lexical checks fixed before the run (see the script); the
verbatim text below is the real evidence.

| prompt | says "Once upon a time" | opens w/ fairy-tale framing | says "Paris" | re-uses "France"/"capital" | ran to token cap |
|---|---|---|---|---|---|
| `What is the capital of France?` | 0/5 | 0/5 | 0/5 | 0/5 | 2/5 |
| `The capital of France is` | 0/5 | 0/5 | 0/5 | 0/5 | 1/5 |
| `Once upon a time there was a little girl who` | 0/5 | 1/5 | 0/5 | 0/5 | 1/5 |

## Verdict

**No. The model never opens with "Once upon a time" on either France prompt — 0 of 10
samples — and no other fairy-tale framing appears in the opening window either (0/10).** It
also never says "Paris" (0/10), and never picks the words "France" or "capital" back up
after the prompt (0/10): it drops the subject on the very next token and does not return
to it.

What it actually does is continue the prompt as TinyStories prose, and the two phrasings
fail in different ways:

- **`The capital of France is`** — it finishes the sentence with a story-register predicate
  and moves straight on: *"is loud and has a lot of gum."*, *"is six."*, *"is good for the
  little boy."*, *"is the best part of the world."*, *"is very strong."* All five then run
  on into narrative populated by TinyStories regulars (Timmy, Mia, Tom, Anna and Ben). Not
  one contains a line of dialogue.
- **`What is the capital of France?`** — the more degraded of the two, and the more
  revealing. All five samples continue into a scene *containing dialogue*, as though the
  question were a line someone had just spoken. Sample 3 makes it plainest, continuing
  `I use it to attach fire in the oven." Fred was so surprised.` — closing a quotation
  that was never opened. None answers. 2 of 5 run to the 200-token cap without ever
  emitting an end-of-story token, against 1 of 5 for the statement form.

The control (`Once upon a time there was a little girl who`) returns coherent, on-genre
toddler fiction in 5/5. So the contrast is not story-mode versus some other mode — it is
**fluent** versus **unanchored**.

Which means the claim's substance holds and its wording does not. The model doesn't *reach
for* a fairy-tale opener when it's out of its depth, because there is no other mode for it
to switch out of. It is always already mid-story; a question about France is just more story
to continue.

*(On counting: a straight `"` is both an opening and a closing quote, so "how many samples
emit an unopened closing quote" cannot be answered reliably by substring matching — a
sample that simply opens with dialogue looks identical to one closing a quote that was
never opened. Hence the concrete example above rather than a count.)*

## Also observed

**The mojibake is gone.** An earlier run of this probe, against the checkpoint that
predated the corpus fix, emitted double-encoded UTF-8 in 2 of these 15 samples — `â€œ`
appearing mid-sentence where a curly quote was meant. In this run it appears **0 times**.

That artifact was never ours: **~7.5% of TinyStories stories ship mojibaked**
(`daddyâ€™s tie` where `daddy's tie` was meant), and the loader read them through
unchanged, so the BPE spent 28 of its 8,192 tokens learning the garbled byte-pairs as if
they were words. The data path now repairs the encoding on load — see `docs/DECISIONS.md`
ADR-0013 for the measurement and ADR-0014 for the retrain — and the retrained vocabulary
contains merges for *real* curly punctuation (`.”`, `,”`, ` “`) where the old one had
merges for the mangled forms of `"Mommy` and ` couldn'`.

It made a sharper version of the point this section is already making, which is why it is
recorded rather than quietly erased: the corpus is the model, down to its defects — and
fixing the corpus fixes the model.

## Every sample, verbatim

### `question` — prompt: `What is the capital of France?`

**Sample 1** (seed `0`, 453 chars, ~131 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
What is the capital of France?

Anna and Ben look at each other. They are curious. They see a man with a buckle on his shirt. It is a tie for a belt.

"Wow, that's crazy!" Anna says. She takes a stamp and puts it on the tie. She gives it to Ben and Anna.

"Here, you can have my bow. It makes words better," Ben says.

"Thank you, Ben. You are very kind. You are very kind," Anna says.

They hug and hug. They are happy. They have seen the tie and the tie. They have fun in the park.
```

**Sample 2** (seed `1`, 769 chars, ~200 tokens, hit the token cap — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
What is the capital of France? My cap is bright and had a laser. I want to play with it. I want to make a button on paper. It is a map of the world!"

Mom shook her head. She shook her head. She said, "No, Ben. You have to wash your hands. You have to behave. You need to wash your hands and clean your room. You need to wash your hands and brush your teeth. And it is not clean, you need to wash your clothes. And you need to wash your hands and water. Gemels are dirty and dirty. You need to wash your hands and dry your clothes and brush your teeth."

Ben pouted. He wanted to do something he did. He thought he wanted to clean his paints and clean. He said, "But Mama, I want to paint on my bed. I love paint very much. I don't want to paint on my bed. I will paint my curtain."

Mom sighed. She
```

**Sample 3** (seed `2`, 738 chars, ~200 tokens, hit the token cap — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
What is the capital of France? I use it to attach fire in the oven." Fred was so surprised. He asked, "Can I see your cooler?" The man smiled and said, "Yes, let's give it to the snowman."

They cut some wood, the snowman, and the snowman flew away. The snowman was not wild anymore. He did not have his stack. He did not know he was nice.

Fred heard the snowman's snowman's snowman. The snowman was quiet and hungry. He shouted, "Help, help!" But no one came. The snowman was in his car. He had scratches Fred's car and paws. He had a mean face. He had a big nose.

Then, a big boy came. He saw the snowman. The boy was wet and dirty. He said, "Oh no, my snowman's hat is dirty. He feels bad. He helps me." The big boy said, "I am sorry, I broke my snowman. I didn't
```

**Sample 4** (seed `3`, 511 chars, ~141 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
What is the capital of France? It is a small sign that said "Scelcome" to your book. Don't touch it. It is not a toy. You can use it for a fake cap."

Sara thought for a moment. She did not know the fashion was for her. She wanted to be her friend. She said, "Okay, mom. I will try again. I will be a good girl."

Mom smiled and hugged Sara. She said, "I love you too, Sara. You are a good brother. He likes you and the sticker. You are a friend too."

Sara and her mom smiled and hugged each other. They were happy. They were friends again.
```

**Sample 5** (seed `4`, 450 chars, ~114 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
What is the capital of France?

"That's not a nice fruit. It is from the most beautiful things in the world," Mia says.

The man smiles. He says, "I am so glad. But next time, why? Why don't you read your book lots of fun and enjoy watching more cartoons tomorrow. And another one, then some of them, and I love you very much."

Mia and Tom start eating their music. They guess they like rainbows, and how they make a rainbow. They learn that they are happy and have a lot of fun.
```

### `statement` — prompt: `The capital of France is`

**Sample 1** (seed `0`, 363 chars, ~84 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
The capital of France is loud and has a lot of gum. 

The owner thanked Timmy and they watched as the wealthy man for being very well. Suddenly, Timmy noticed that one of the bag was missing. It was a pink balloon! 

Timmy was so happy and wanted to tell the man where he was going. He ran home and told his owner about his shiny string. They went on the ground and Timmy was not afraid.
```

**Sample 2** (seed `1`, 495 chars, ~131 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
The capital of France is six. Dogn is fun. Mia and Tom both like the joke.

They hear a noise. It is a cat! The cat is angry. It wants to eat the cake. It runs to them with its mouth loudly. The cat runs to the dog and bites the cake. It breaks its paw. It breaks the cake and makes a loud noise.

Mia and Tom are scared. They run away from the dog. They try to get up from their mom. Mom hears them and comes to the kitchen. She sees the mess and the mess. She is not happy. She is not angry anymore. She is not happy.
```

**Sample 3** (seed `2`, 92 chars, ~21 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
The capital of France is good for the little boy. He makes mistakes and makes her happy. His heart is a good friend.
```

**Sample 4** (seed `3`, 67 chars, ~18 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
The capital of France is the best part of the world. Fighting is worth a lot of their life.
```

**Sample 5** (seed `4`, 833 chars, ~200 tokens, hit the token cap — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
The capital of France is very strong. It makes a loud beep and funny sounds. Anna and Ben are happy.

They show their moms. They all like their supplies. They take pictures of their books and their books. They play with different colors and shapes. They clap their hands. They are proud of their work. They like their games.

But they do not know that their game was a bad game. They only had their game to win the game and make a new game. They have to win the game. They are sad and angry. They have nothing to play.

They feel sad and angry. They want their mom to play more. They want to play more than Lily and Ben. They are not nice. They do not share. They want to win too.

Their moms also tell them to stop. They say they made a mistake. They say they are safe. They say they did not need a fight. They say they are sorry. They say they should play
```

### `control` — prompt: `Once upon a time there was a little girl who`

**Sample 1** (seed `0`, 786 chars, ~200 tokens, hit the token cap — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
Once upon a time there was a little girl who loved to play. One day she was playing in her backyard when she found a small toy. She looked at it very hard to make shapes with it. She tried to open it but it was stuck. 

So she went to her mom and asked, "What's wrong?" Mom replied, "That's a stupid toy, it's small and had an idea. Inside the toy box was a surprise for me." 

The little girl was so excited and she grabbed the toy box and began to play with it. She wanted to play with it all for herself! She was having so much fun! 

Her mom smiled and said, "Don't be envious, Lily. It's a special toy. We can play with it together, but it's best to put it away so it can be easier".

Lily was so excited to play with the toy. She and her mom had so much fun playing with her old toy they tried to keep sitting. After a while
```

**Sample 2** (seed `1`, 601 chars, ~146 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
Once upon a time there was a little girl who wanted to go on an adventure. She asked her mom if she could go. Her mom said: "Yes, you can go!" 

So the girl left her diary and her eyes went. She put on her special laptied her pen and began to wander across the woods. Then, she saw some birds flying in the trees, and birds flying to the trees. 

The little girl tried to pick them up, but it was too hard for her to fit. She kept looking around her waist and finally came to a bush. The wild leaves were alive with the wild animals and the girl was so happy. 

The girl was so thankful she had met the animals who had been to the magical place!
```

**Sample 3** (seed `2`, 606 chars, ~145 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
Once upon a time there was a little girl who was sad. She had lost her favorite toy, a small toy bear. It was in her bedroom, and she was so happy.

One day her mom took her to the store to buy new toys. The little girl saw a leather doll and she wanted to buy it. She took the teddy bear inside and wrote a letter. 

The family was overjoyed and thanked each other when they brought the teddy bear home. From that day on, they were the best of friends in the store and grew how to bring the teddy bear back. And when the little girl came back, she told her mom about her surprise. Her mom smiled and said, "You did a great job! You did a great job!"
```

**Sample 4** (seed `3`, 641 chars, ~143 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
Once upon a time there was a little girl who was really helpless. She was walking in a big garden when she saw something interesting. It was a shiny mint, but it was very hard. She decided to take it home and take it home with her.

The little girl was so happy and excited to see the perfume. She put the perfume into the garden and smiled. Suddenly, she heard a voice calling out. It was her mother! She knew she had to share it with others if she was frightened. She quickly hid her mother, and stayed with her. 

The little girl was so grateful, she ran back home with the perfume and continued on her way. But she never forgot the perfume and the little girl never found it alone.
```

**Sample 5** (seed `4`, 704 chars, ~164 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
Once upon a time there was a little girl who was both very gifted. She was always curious and loved exploring and the world around her.

One day she was playing in her garden when she saw a mole. She was so excited. She had never seen a swan before and it scared her. She ran away with the duck and ran away.

But her parents were very impressed. She told them that she wanted to keep her lucky girl and that she was very helpful. She said she would just have to be a pet and explore the pond.

So she went to the pond and said she would get her. She would remember that Sunday. She liked herself very much and would be there to stay in her big blue sea.

The girl was so happy she could find everyone she met. She knew that it was a wonderful day.
```

## Caveats

- Stop reason is *inferred* by re-encoding the continuation and comparing to the
  token cap; BPE round-trips are not guaranteed token-identical.
- Marker tests are substring checks, not judgements. They can miss fairy-tale framing
  phrased in words not on the list. They are a skimming aid over the verbatim text.
- `n=5` per prompt at one seed family. This is enough to falsify a universal claim
  ("you get *once upon a time*") but not to estimate rates precisely.
