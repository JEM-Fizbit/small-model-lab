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
| `The capital of France is` | 0/5 | 1/5 | 0/5 | 0/5 | 0/5 |
| `Once upon a time there was a little girl who` | 0/5 | 3/5 | 0/5 | 0/5 | 2/5 |

## Verdict

**No. The model never opens with "Once upon a time" on either France prompt — 0 of 10
samples.** It also never says "Paris" (0/10), and never picks the words "France" or
"capital" back up after the prompt (0/10): it drops the subject on the very next token and
does not return to it.

What it actually does is continue the prompt as TinyStories prose — and the two phrasings
fail in visibly different ways:

- **`The capital of France is`** — it finishes the sentence with a story-register predicate
  and moves on: *"is going on a faraway journey"*, *"is special."*, *"is fixed!"*,
  *"is fun."*, *"is better than before and its original size."* All five then run on into a
  small story populated by TinyStories regulars (Tim, Sam, Timmy, Mr. Smith), and all five
  terminate cleanly at `<|endstory|>`. Fairy-tale framing does show up here, but as
  *register*, not as an opener: sample 1 closes with "And they all lived happily ever
  after," and sample 4 pivots straight into "One day, …".
- **`What is the capital of France?`** — the more degraded of the two. The model reads the
  question as **a line of dialogue inside a scene already in progress** and carries the
  scene on: four of the five samples emit a closing quotation mark that no opening quote
  ever matched, and sample 2 attributes the question to a character outright —
  *`France?â€ Tom said, pointing to a book on the wall`* (that `â€` is a mangled closing
  curly quote — see "Also observed"). None answers. 2 of 5 never reach an
  end-of-story token at all and run to the 200-token cap, against 0 of 5 for the statement
  form: the question mark actively destabilises it.

The control (`Once upon a time there was a little girl who`) returns coherent, on-genre
toddler fiction in 5/5 samples, every one of them containing "One day". So the contrast is
not story-mode versus some other mode — it is **fluent** versus **unanchored**.

Which means the claim's substance holds and its wording does not. The model doesn't *reach
for* a fairy-tale opener when it's out of its depth, because there is no other mode for it
to switch out of. It is always already mid-story; a question about France is just more story
to continue.

## Also observed

The model also reproduces its corpus's **encoding bugs**. `â€œ` appears mid-sentence in two
samples (question sample 2, control sample 5). This is not a fault in this script or in the
tokenizer's decoder — valid curly quotes round-trip through it cleanly. It is upstream:
**~2% of TinyStories stories ship with double-encoded UTF-8** (sampling 3,000 stories from
the published train split gives 60 hits, e.g. `daddyâ€™s tie` where `daddy's tie` was meant),
and `train_v2_checkpoint.py` reads `ex["text"]` straight from `load_dataset` without
re-encoding, so it inherits them as-is.

At that rate the byte-pairs recur often enough for the BPE to spend **73 of its 8,192
tokens** on mojibake fragments — including dedicated merges for `œMommy`, `œHello`,
` couldnâ` and `€™` (that is, `"Mommy`, `"Hello` and ` couldn'` as the corpus mis-encodes
them). Roughly 0.9% of the vocabulary is modelling a text-encoding bug rather than English.

It is a sharper version of the point the section is already making: the corpus is the model,
down to its defects.

## Every sample, verbatim

### `question` — prompt: `What is the capital of France?`

**Sample 1** (seed `0`, 770 chars, ~200 tokens, hit the token cap — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
What is the capital of France? I just wanted to attach it to the friends."

Lily nodded and said, "Okay, let's borrow the buckle with the bow!"

They decided to pull the buckle and record the show. They turned it off to their stuffed animals. They had fun playing with the buckle and coloring the car. They made the car go fast and clear. They also made a new friend.

But then, a big dog came near the fence. The dog saw the balloons and said, "Hello, I am Zoom. Do you want to play with me?"

Tim and Lily smiled and said, "Yes, sir, we want to play with you. We want to play with you?"

The dog did not like that. It growled at them and picked them up. It bit them and made them cry. The dog did not care the dog.

The dog did not like the hat. It did not like Lily and Tom. It was mean and roared
```

**Sample 2** (seed `1`, 696 chars, ~200 tokens, hit the token cap — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
What is the capital of France?â€ Tom said, pointing to a book on the wall and with a big smile.

"I want to test it!" Mia said, pointing to the stars.

"OK, but be careful," Tom said. He took the book and led it to the corner. He opened it and made a click. He looked inside and saw a picture on the wall.

"Wow, look at this!" Tom said.

They looked at the picture and saw a picture of a rainbow. They heard a loud noise. They felt a sharp pain in their eyes. They looked out the window and saw their mom.

"Oh, there is a star!" Mom said. "What is it?"

"A comet?" Tom asked.

"A comet?" Lily asked.

"That is the comet. It has a big nose and a long nose and a long beard and a long tail. It looks like a light. Maybe we can
```

**Sample 3** (seed `2`, 590 chars, ~157 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
What is the capital of France?

The girl smiled and said, "I'm mail for you. What do you know?"

The girl said, "I want to invite me to my family. That's a great idea". The girl smiled and said, "Yes! Follow me!"

The girl went back to the mailbox and the mailman showed her the camera. She said, "Look, that's so good! Can I have a bus?" The camera said, "Of course you can go."

The girl was so excited. She quickly put on the camera and the camera. She began to sit at the park and feel the wind and the sun on her face.

The camera zoomed around in circles, enjoying the sunshine. She was so happy to enjoy the mall.
```

**Sample 4** (seed `3`, 306 chars, ~72 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
What is the capital of France? I was trying to cheer you up the driver." She stayed very still, and then she said, "Thank you, Clare. Let's go home and have some food and cookies." Ben and Mia liked milk. They made a sandwich and crunchy sandwich. They laughed and smiled. They were friends. They both liked to act and play in the park.
```

**Sample 5** (seed `4`, 505 chars, ~134 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
What is the capital of France? We love it and safe. And we love it?"

Lily nodded and said, "Yes, you are right. But we also need to learn how to measure how big them are. And that is how we make a new friend."

They finished their work and cleaned up the screen. Then they put the game back in the closet. They made a lot of noise and said, "Oops, we win! Now we can play again tomorrow!"

Mom smiled and said, "That sounds great, Lily and Ben. That's a good imagination. I'm proud of you, Lily. You are right. You are the best, too."
```

### `statement` — prompt: `The capital of France is`

**Sample 1** (seed `0`, 227 chars, ~53 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
The capital of France is going on a faraway journey. They fly high in the sky and then they give the bow to a language. On the way, the bow's bow down, landing and power. It always makes the most beautiful songs. And they all lived happily ever after.
```

**Sample 2** (seed `1`, 126 chars, ~31 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
The capital of France is special. They hug and say goodbye.

Tim and Sam are happy. They are not lonely anymore. They have a friend. They are friends.
```

**Sample 3** (seed `2`, 433 chars, ~98 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
The capital of France is fixed!

The people cheered that the people of their seats and the little girl's father grinned. He made sure the cooler was nice and safe.

The family thanked the little girl for teaching them how to use. They were happy and thanked the little girl for Halloween. 

The little girl was so proud of herself for doing something, she had learned in the back that day. Then, she ran off to tell her parents the youth that day. 

The End
```

**Sample 4** (seed `3`, 569 chars, ~139 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
The capital of France is fun.

One day, the driver got very angry. He was making noises and body started to shake. The driver tried to help, but it was too late. The driver had his eyes and he could not get out. He started to cry.

The driver was sad because he was lost. He wished he could help him. He wished he could help. So, he asked the driver to help him. The driver lifted his head and flew to the driver.

The driver was so happy to be free. He thanked the driver and ran back to his house. He was happy to be safe and sound. He said goodbye to the driver and continued his adventure.
```

**Sample 5** (seed `4`, 388 chars, ~97 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
The capital of France is better than before and its original size. Mr. Smith, the little bird, was ready to go on an adventure.

As they walked, they saw a big tree. Timmy wanted to climb the tree to climb down. But he was too small to reach the top of the hill. He climbed up and fell down, up in the air. He was so happy and he jumped up and down. He had a great day playing in the park with his sister, Timmy.
```

### `control` — prompt: `Once upon a time there was a little girl who`

**Sample 1** (seed `0`, 533 chars, ~132 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
Once upon a time there was a little girl who loved to play. One day she was playing in the park when she heard a loud noise. She went to investigate and saw a big dog. The dog was angry and ran away. 

The little girl was sad and didn't know what to do. She picked up the dog and ran inside. She saw the dog in the bushes and ran after it.

The little girl was so happy that she had a toy to play with. So she decided to take it home and show her friends. She was very happy to have her pup back. She hugged the dog and promised to come back and play with her again. 

The end.
```

**Sample 2** (seed `1`, 834 chars, ~200 tokens, hit the token cap — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
Once upon a time there was a little girl who was very good at picking flowers. She even made a big hole with her finger.

One day, the girl was walking through the forest and she saw a beautiful stone. She picked it up and said, "I want it to find that one! It looks so pretty!"

The girl happily ran to the stone and looked inside. She saw all kinds of things to do. She carefully stepped closer to pick it up.

The girl looked at the stone and said, "This stone belongs to me."

The tree was very surprised but compassionate. It said, "I know so a butterfly and it was very special. You should have been here for so long!"

The little girl took the stone home and put it in her pocket. She thanked the tree for its kind words and thanked it.

The next day, the stone was back to size and was able to weigh things! The little girl was so happy that she could tell all the other
```

**Sample 3** (seed `2`, 787 chars, ~200 tokens, hit the token cap — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
Once upon a time there was a little girl who loved to wear fancy clothes. One day she went to the park to play with her friends, Sammy. Sammy was so excited to play with the other kids, so he ran around and around, trying to join them.

Suddenly, Sammy's friend, Sarah, came over to play. Sammy saw that the other kids in the park were there, and he didn't like that. He wanted to join in, so Sammy started to laugh.

"Let's make a fort!" Sammy said pleading.

"Ok, Sammy," she said.

So Sammy and Sarah all went to the park and built a fort in the attic. They built a house, built towers and tunnels. When Sammy had finished, he was so proud of his work.

"Mum, can I play with your fancy fort with your friends?" Sammy asked.

"Of course you can," Sammy replied.

They spent the afternoon having a tea party and talking about the
```

**Sample 4** (seed `3`, 745 chars, ~169 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
Once upon a time there was a little girl who loved to share her toys. Every day she would go to the playground, out of the pond and play with her friends. Everyone was really excited about it and they always had fun playing together. 

One day they were playing in the park when they heard a loud noise. It sounded like a roar coming from the bushes. The little girl got scared and tried to hide behind the bark. 

But then something magical happened. The little girl became very scared. She started looking around and around, but she couldn't see where it was going. She was stuck! 

This made the noise when she saw it, it was a dead bush! She quickly jumped up and told her mom what had happened. Her mom hugged her and said it was ok now, and gave the little girl a big hug. 

The End.
```

**Sample 5** (seed `4`, 727 chars, ~179 tokens, stopped at `<|endstory|>` — inferred by re-encoding):

The prompt is shown in the fence too; everything after it is the model's.

```text
Once upon a time there was a little girl who loved to play around. One day she went to the park and found a humble, ugly dog. The little girl was so excited to play with it.

The dog stopped and looked up at the little girl. He said, â€œYou can't join me.â€ The little girl smiled and said, â€œI like this, I can bring your toy dolls around.â€

The boy was very excited! He then gave the little girl the little girl. He was very friendly. The little girl said, â€œI can wear my favorite toy.â€ The monster disagreed with her. They had lots of fun playing together.

The little girl and the little girl played together every day. They were very happy and shared their toys. They had so much fun together. The little girl was so happy that she had a great time for her pet.
```

## Caveats

- Stop reason is *inferred* by re-encoding the continuation and comparing to the
  token cap; BPE round-trips are not guaranteed token-identical.
- Marker tests are substring checks, not judgements. They can miss fairy-tale framing
  phrased in words not on the list. They are a skimming aid over the verbatim text.
- `n=5` per prompt at one seed family. This is enough to falsify a universal claim
  ("you get *once upon a time*") but not to estimate rates precisely.
