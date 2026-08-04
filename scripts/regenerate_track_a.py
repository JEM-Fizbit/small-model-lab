"""regenerate_track_a.py — rebuild everything downstream of the Track A checkpoint, in order.

WHY THIS EXISTS. Retraining the tiny GPT invalidates twelve separate surfaces scattered
across notebooks, generated figures and hand-pasted prose. Three of those figures rendered
real measurements with no script behind them, so a retrain silently falsified them and
nothing failed loudly. And the two trainers write to the SAME checkpoint path while
producing DIFFERENT models, so running them in the wrong order downgrades the shipped
checkpoint. Doing this by hand is how you end up publishing a figure whose caption
disagrees with its own numbers.

    uv run python scripts/regenerate_track_a.py --check      # what is stale? (no writes)
    uv run python scripts/regenerate_track_a.py --derived    # rebuild from the current checkpoint
    uv run python scripts/regenerate_track_a.py --all        # + retrain first (~65 min)

ORDER IS LOAD-BEARING (--all does this for you):
    1. notebook 02   — trains its own model and SAVES OVER checkpoints/tiny_gpt_v2 without
                       the <|endstory|> token (see its cell 19).
    2. producer      — train_v2_checkpoint.py, restores the shipped checkpoint WITH the
                       end-of-story token that chat.py / notebook 03 / the probe rely on.
    3. derived       — every figure and result, against the checkpoint from step 2.
Run 2 before 1 and you ship a model that never stops generating.

REPRODUCIBILITY. Every run writes TRACK_A_MANIFEST.json next to the walk-through: the
checkpoint's hash and config, the seeds and sampling settings each artifact was built
with, and which checkpoint hash each artifact came from. `--check` compares that record
against the checkpoint on disk, so "is the site consistent with the model?" is a question
with an answer instead of a guess.

NOTE the manifest records hashes for *staleness detection*, not for byte-equality testing:
MLX on the GPU is not bitwise deterministic, so the same seed and the same data give a
slightly different model each run (see docs/DECISIONS.md ADR-0013).
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WALK = REPO / "docs" / "walkthrough"
NOTEBOOKS = REPO / "notebooks"
CKPT = NOTEBOOKS / "checkpoints" / "tiny_gpt_v2"
MANIFEST = WALK / "TRACK_A_MANIFEST.json"

# --- figures whose SVG is emitted whole and spliced into a content module ------
SVG_ARTIFACTS = [
    ("PROBS_SVG", "gen_probs_figure.py", "content_concepts.py"),
    ("TEMP_SVG", "gen_temp_figure.py", "content_concepts.py"),
    ("ATTENTION_SVG", "gen_attention_figure.py", "content_concepts.py"),
    ("WE_MATRIX_SVG", "gen_embedding_matrix.py", "content_concepts.py"),
    # template-updater: rewrites only the measured values inside the hand-built animation
    ("GENLOOP_SVG", "gen_genloop_figure.py", "content.py"),
]
# --- generators that write their own output file ------------------------------
FILE_ARTIFACTS = [("DOMAIN_LIMIT_PROBE_RESULTS.md", "gen_domain_limit_probe.py")]

# --- surfaces a script CANNOT finish: they need a human decision ---------------
MANUAL = [
    ("TOKENIZE_SVG (content_concepts.py)",
     "renders four real token ids; --check verifies them against notebook 02's output."),
    ('rawoutput story (content.py, "a complete story from chat.py")',
     "a verbatim generated story pasted into the prose; --check re-runs its stated seed and "
     "confirms it still reproduces. Replace it by hand if it stops."),
]

# Curated excerpts record the seed/temp that produced them, so they can be re-derived rather
# than trusted. Two forms exist: a caption that states the seed, and inline headers in a
# multi-sample block.
STORY_CAPTION = r'"a complete story from chat\.py[^"]*seed (\d+), temp ([\d.]+)\)"'
STORY_MAX_NEW = 300
# "--- temperature 0.6 (seed 13) ---" followed by the sample it labels. The lookahead must
# stop at the block's closing quotes as well as the next header — anchoring the last sample
# on \Z instead swallows the rest of the file and reports a spurious drift.
INLINE_SAMPLE = re.compile(
    r'--- temperature ([\d.]+) \(seed (\d+)\) ---\n(.*?)(?=\n\n--- temperature|""")', re.S)
INLINE_MAX_NEW = 150
PROMPT = "Once upon a time"

TOKENIZE_PROMPT = " Once upon a time"   # the phrase whose ids TOKENIZE_SVG renders

# --- measured numbers quoted in PROSE, which no generator rewrites --------------
# Figure captions and body text cite values straight out of the figures. Nothing regenerates
# them, so a retrain leaves them quietly wrong — exactly the failure this whole script exists
# to prevent, and it bit us once (a caption still claimed 76% after the number became 43%).
# Each entry pulls the truth back out of the (regenerated, therefore current) figure.
PROSE_CITATIONS = [
    ("content_concepts.py", r"this head hands (\d+)% ", "ATTENTION_SVG", "content_concepts.py",
     r'font-weight="700"[^>]*>(\d+)%<',
     "attention caption vs the strongest arc in ATTENTION_SVG"),
    ("content.py", r"the die lands on a (\d+\.\d)% underdog", "GENLOOP_SVG", "content.py",
     r"A (\d+\.\d)% chunk wins about one roll",
     "generation-loop caption vs the sampled share in GENLOOP_SVG"),
]


def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def checkpoint_state():
    w = CKPT / "weights.safetensors"
    if not w.exists():
        return None
    cfg = json.loads((CKPT / "config.json").read_text())
    return {"weights_sha256": sha256(w), "tokenizer_sha256": sha256(CKPT / "tokenizer.json"),
            "config": cfg, "has_eos": "eos_token" in cfg}


def run(cmd, capture=False):
    print(f"    $ {' '.join(str(c) for c in cmd)}", flush=True)
    r = subprocess.run(cmd, cwd=REPO, capture_output=capture, text=True)
    if r.returncode != 0:
        if capture:
            sys.stderr.write(r.stdout or "")
            sys.stderr.write(r.stderr or "")
        sys.exit(f"!! FAILED: {' '.join(str(c) for c in cmd)}")
    return r.stdout if capture else None


def splice(module, name, svg):
    """Replace `NAME = r'''...'''` in a content module with freshly generated SVG."""
    path = WALK / module
    src = path.read_text()
    marker = f"{name} = r'''"
    i = src.index(marker)
    j = src.index("'''", i + len(marker))
    if "'''" in svg:
        sys.exit(f"!! {name}: generated SVG contains ''' and cannot be spliced into a raw string")
    if svg.endswith("\\"):
        sys.exit(f"!! {name}: generated SVG ends with a backslash, which breaks r'''...'''")
    # the closing ''' sits directly against </svg> in these modules — adding a newline here
    # makes every splice a no-op diff on an otherwise unchanged figure
    path.write_text(src[:i + len(marker)] + svg.strip() + src[j:])


def read_svg(module, name):
    src = (WALK / module).read_text()
    marker = f"{name} = r'''"
    i = src.index(marker)
    j = src.index("'''", i + len(marker))
    return src[i + len(marker):j].strip()


def current_token_ids():
    """Token ids TOKENIZE_SVG should be showing.

    Read from NOTEBOOK 02's committed output, not from the shipped checkpoint's tokenizer.
    The two disagree: the producer reserves an extra <|endstory|> token, which shifts every
    id. The figure sits beside notebook 02's own "what it prints" block on the same page,
    so it has to match THAT — and the notebook's tokenizer is never persisted (the producer
    overwrites it), which makes the committed output the only durable record of it.
    """
    nb = json.loads((NOTEBOOKS / "02_tiny_gpt_tuned.ipynb").read_text())
    for cell in nb["cells"]:
        for out in cell.get("outputs", []):
            text = out.get("text", "")
            text = "".join(text) if isinstance(text, list) else text
            m = re.search(r"example tokens for '.*?': \[([\d, ]+)\]", text)
            if m:
                return [int(x) for x in m.group(1).split(",")]
    return None


def check():
    state = checkpoint_state()
    if state is None:
        sys.exit(f"No checkpoint at {CKPT.relative_to(REPO)} — run with --all.")
    print(f"checkpoint {state['weights_sha256'][:16]}  eos_token={state['has_eos']}")
    if not state["has_eos"]:
        print("  !! this checkpoint has NO end-of-story token — notebook 02 wrote it last.")
        print("     Re-run notebooks/train_v2_checkpoint.py before regenerating anything.")

    if not MANIFEST.exists():
        print("\nno manifest yet — every artifact is of unknown provenance. Run --derived.")
        return 1
    man = json.loads(MANIFEST.read_text())
    # notebook-02 artifacts are self-trained, not built from the shipped checkpoint, so they
    # are never "stale" relative to it — see record_notebook_02
    stale = [n for n, rec in man.get("artifacts", {}).items()
             if rec.get("from_checkpoint") not in (state["weights_sha256"],
                                                   "notebook-02 self-trained")]
    print(f"\n{len(man.get('artifacts', {})) - len(stale)} artifact(s) current, {len(stale)} stale")
    for n in stale:
        print(f"  STALE  {n}")

    ids = current_token_ids()
    svg = read_svg("content_concepts.py", "TOKENIZE_SVG")
    # ids render as ">#5381</text>" — match the '#' prefix so a bare number that happens to
    # be an SVG coordinate can't masquerade as a present token id
    missing = list(ids or []) if ids is None else [i for i in ids if f"#{i}<" not in svg]
    print(f"\nTOKENIZE_SVG token ids for {TOKENIZE_PROMPT!r} (from notebook 02's output): {ids}")
    print("  OK — all present in the figure" if not missing
          else f"  STALE — {missing} missing; update the ids drawn in TOKENIZE_SVG")

    drifted = check_prose_citations()
    drifted += check_quoted_story()
    drifted += check_site_rebuilt()

    print("\nmanual surfaces (no script can finish these):")
    for name, why in MANUAL:
        print(f"  - {name}\n      {why}")
    return 1 if (stale or missing or drifted) else 0


SITE_PAGES = {"content_concepts.py": "ideas/index.html", "content.py": "track-a/index.html"}


def check_site_rebuilt():
    """Has docs/walkthrough/site/ been rebuilt since the content modules changed?

    Regenerating a figure updates content*.py, but the PUBLISHED page is the built HTML.
    Forget `build.py` and every check above passes while the live site still shows the old
    numbers — which is the same silent-staleness failure in a different place.
    """
    print("\nbuilt site vs content modules:")
    stale = []
    for name, _gen, module in SVG_ARTIFACTS:
        page = WALK / "site" / SITE_PAGES.get(module, "")
        if not page.exists():
            continue
        svg = read_svg(module, name)
        fingerprint = svg[:400]          # the opening tag + aria-label: changes on any edit
        if fingerprint not in page.read_text():
            stale.append(name)
    if stale:
        print(f"  STALE — {', '.join(stale)} differ from the built page.")
        print("     run: uv run python docs/walkthrough/build.py")
    else:
        print(f"  OK — all {len(SVG_ARTIFACTS)} figures match the built pages")
    return stale


def check_quoted_story():
    """Re-run the pasted story's own seed and confirm it still reproduces.

    Its caption asserts a provenance ("seed 1, temp 0.8") — that is a factual claim about
    the shipped checkpoint, so it gets checked rather than trusted.
    """
    import mlx.core as mx
    sys.path.insert(0, str(NOTEBOOKS))
    import tiny_gpt

    src = (WALK / "content.py").read_text()
    model, tok, cfg = tiny_gpt.load(str(CKPT))
    bad = []

    def reproduces(seed, temp, n_new, committed):
        mx.random.seed(seed)
        regen = PROMPT + "".join(tiny_gpt.stream(model, tok, cfg, PROMPT,
                                                 n_new=n_new, temperature=temp))
        return committed.strip() == regen.strip()

    print("\ncurated excerpts (each records the seed that produced it):")

    # 1. the single story whose CAPTION carries the seed. Anchor on the caption and walk back
    #    to the block it belongs to, so adding other rawoutput blocks can't mis-target this.
    cap = re.search(STORY_CAPTION, src)
    if not cap:
        print("  ?  chat.py story: seed caption not found")
        bad.append("chat.py story")
    else:
        head = src.rindex('("rawoutput", """', 0, cap.start()) + len('("rawoutput", """')
        committed = src[head:src.rindex('""",', head, cap.start())].replace('\\"', '"')
        seed, temp = int(cap.group(1)), float(cap.group(2))
        ok = reproduces(seed, temp, STORY_MAX_NEW, committed)
        print(f"  {'OK ' if ok else 'DRIFT'} chat.py story (seed {seed}, temp {temp})")
        if not ok:
            bad.append("chat.py story")

    # 2. multi-sample blocks that state seed + temperature inline, one per sample
    for temp, seed, sample in INLINE_SAMPLE.findall(src):
        ok = reproduces(int(seed), float(temp), INLINE_MAX_NEW, sample.replace('\\"', '"'))
        print(f"  {'OK ' if ok else 'DRIFT'} §14 demo sample (seed {seed}, temp {temp})")
        if not ok:
            bad.append(f"§14 sample seed {seed}")
    return bad


def check_prose_citations():
    """Do the numbers quoted in prose still match the figures they describe?"""
    print("\nmeasured numbers quoted in prose:")
    drifted = []
    for prose_mod, prose_re, fig, fig_mod, fig_re, label in PROSE_CITATIONS:
        prose = (WALK / prose_mod).read_text()
        # the figure literal also contains the value, so search prose with the SVG blanked out
        prose = re.sub(r"_SVG = r'''.*?'''", "«SVG»", prose, flags=re.S)
        pm = re.search(prose_re, prose)
        fm = re.search(fig_re, read_svg(fig_mod, fig))
        if not pm or not fm:
            print(f"  ?  {label}: pattern not found (prose={bool(pm)}, figure={bool(fm)})")
            drifted.append(label)
            continue
        ok = float(pm.group(1)) == float(fm.group(1))
        print(f"  {'OK ' if ok else 'DRIFT'} {label}: prose says {pm.group(1)}, "
              f"figure says {fm.group(1)}")
        if not ok:
            drifted.append(label)
    return drifted


def derived(man):
    state = checkpoint_state()
    if state is None:
        sys.exit(f"No checkpoint at {CKPT.relative_to(REPO)}.")
    if not state["has_eos"]:
        sys.exit("Checkpoint has no end-of-story token — notebook 02 wrote it last.\n"
                 "Run `uv run python notebooks/train_v2_checkpoint.py` first (or use --all).")

    print("\n[3/3] derived artifacts")
    for name, gen, module in SVG_ARTIFACTS:
        svg = run(["uv", "run", "python", str(WALK / gen)], capture=True)
        splice(module, name, svg)
        man["artifacts"][name] = {"generator": f"docs/walkthrough/{gen}",
                                  "target": f"docs/walkthrough/{module}",
                                  "from_checkpoint": state["weights_sha256"]}
    for name, gen in FILE_ARTIFACTS:
        run(["uv", "run", "python", str(WALK / gen)])
        man["artifacts"][name] = {"generator": f"docs/walkthrough/{gen}",
                                  "from_checkpoint": state["weights_sha256"]}
    run(["uv", "run", "python", str(Path(__file__).parent / "execute_notebook.py"),
         str(NOTEBOOKS / "03_tiny_gpt_chat.ipynb"), "7"])
    man["artifacts"]["notebooks/03_tiny_gpt_chat.ipynb"] = {
        "generator": "scripts/execute_notebook.py (cells 0-6; cell 7 is an interactive REPL)",
        "from_checkpoint": state["weights_sha256"]}
    record_notebook_02(man)
    return state


def record_notebook_02(man):
    """Record notebook 02's outputs — which do NOT come from the shipped checkpoint.

    Notebook 02 trains its own model (no <|endstory|> token) and its committed outputs are
    that model's, not the producer's. Stamping them with the shipped checkpoint's hash would
    claim a provenance they do not have, so they are recorded by their OWN final val loss.
    """
    nb_path = NOTEBOOKS / "02_tiny_gpt_tuned.ipynb"
    if not nb_path.exists():
        return
    nb = json.loads(nb_path.read_text())
    final, ids = None, None
    for cell in nb["cells"]:
        for out in cell.get("outputs", []):
            text = out.get("text", "")
            text = "".join(text) if isinstance(text, list) else text
            for line in text.splitlines():
                if line.startswith(f"step {3000}/") or re.match(r"^step +\d+/\d+ ", line):
                    final = line.strip()
            m = re.search(r"example tokens for '.*?': \[([\d, ]+)\]", text)
            if m:
                ids = [int(x) for x in m.group(1).split(",")]
    note = ("notebook 02 trains its OWN model (no <|endstory|>) and overwrites the checkpoint; "
            "the producer must run after it. These outputs are that model's, not the shipped one's.")
    for key, gen in (("notebooks/02_tiny_gpt_tuned.ipynb", "scripts/execute_notebook.py (all cells)"),
                     ("notebooks/loss_curve_tuned.png", "notebook 02 plotting cell")):
        man["artifacts"][key] = {"generator": gen, "from_checkpoint": "notebook-02 self-trained",
                                 "note": note, "final_train_line": final}
    if ids:
        man["artifacts"]["notebooks/02_tiny_gpt_tuned.ipynb"]["token_ids_shown"] = ids


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="report staleness; write nothing")
    g.add_argument("--derived", action="store_true", help="rebuild from the current checkpoint")
    g.add_argument("--all", action="store_true", help="retrain in order, then rebuild (~65 min)")
    args = ap.parse_args()

    if args.check:
        sys.exit(check())

    man = {"artifacts": {}}
    if MANIFEST.exists():
        man = json.loads(MANIFEST.read_text())
        man.setdefault("artifacts", {})

    if args.all:
        print("[1/3] notebook 02 — trains its own model, overwrites the checkpoint without EOS")
        run(["uv", "run", "python", str(Path(__file__).parent / "execute_notebook.py"),
             str(NOTEBOOKS / "02_tiny_gpt_tuned.ipynb")])
        man["artifacts"]["notebooks/02_tiny_gpt_tuned.ipynb"] = {
            "generator": "scripts/execute_notebook.py (all cells)"}
        man["artifacts"]["notebooks/loss_curve_tuned.png"] = {
            "generator": "notebook 02 plotting cell"}
        print("\n[2/3] producer — restores the shipped checkpoint WITH the end-of-story token")
        run(["uv", "run", "python", str(NOTEBOOKS / "train_v2_checkpoint.py")])

    state = derived(man)          # records notebook-02's artifacts with their own provenance
    man["checkpoint"] = state
    man["generated_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    man["settings"] = settings_snapshot()
    man["manual_surfaces"] = {n: why for n, why in MANUAL}
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    print(f"\nwrote {MANIFEST.relative_to(REPO)}")
    print("\nSTILL MANUAL — these need a human:")
    for name, why in MANUAL:
        print(f"  - {name}")


SETTINGS_SOURCES = ["docs/walkthrough/gen_domain_limit_probe.py",
                    "docs/walkthrough/gen_generation_trace.py",
                    "docs/walkthrough/gen_probs_figure.py",
                    "docs/walkthrough/gen_temp_figure.py",
                    "docs/walkthrough/gen_attention_figure.py",
                    "docs/walkthrough/gen_embedding_matrix.py",
                    "notebooks/train_v2_checkpoint.py"]
# names that are layout/style rather than experimental settings — noise in a manifest
SETTINGS_SKIP = re.compile(r"^(W|H|INK|SOFT|FAINT|LINE|GOLD|ROSE|MONO|SERIF|SAT|DIMS|"
                           r"BAR_.*|REST_FILL|ARC_.*|STROKE_.*|TEXT_.*|LABEL_.*|BOX_.*|BASE_Y|"
                           r"ROW_.*|PCT_GAP|MAX_BAR|OPACITY|BOXES|N_END|CONFIG_FIELDS|"
                           r"TOP_COLOUR)$")   # PANELS is NOT skipped — it carries the temperatures


def settings_snapshot():
    """Record the load-bearing constants each generator was run with.

    Parsed from the AST rather than executed (importing would run model code) and rather
    than regex-matched (which silently misses tuple assignments like `LAYER, HEAD = 1, 3`
    — the attention figure's entire provenance).
    """
    import ast
    out = {}
    for rel in SETTINGS_SOURCES:
        path = REPO / rel
        if not path.exists():
            continue
        found = {}
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, ast.Assign):
                continue
            targets, value = node.targets[0], node.value
            names = ([t.id for t in targets.elts if isinstance(t, ast.Name)]
                     if isinstance(targets, ast.Tuple) else
                     [targets.id] if isinstance(targets, ast.Name) else [])
            values = (value.elts if isinstance(value, ast.Tuple) and len(names) > 1
                      else [value] * len(names))
            for n, v in zip(names, values):
                if not n.isupper() or SETTINGS_SKIP.match(n):
                    continue
                try:
                    found[n] = ast.literal_eval(v)
                except (ValueError, SyntaxError):
                    pass                       # computed at runtime — not a fixed setting
        out[Path(rel).name] = found
    return out


if __name__ == "__main__":
    main()
