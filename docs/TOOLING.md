# Tooling And Script Safety

<!-- Last reviewed: 2026-07-05 -->

This repo is a public, Apple-Silicon-first learning lab. It intentionally mixes notebooks, generated walk-through pages, local model artifacts, and Track B scripts that can download data/models or spend API money. Treat script choice as part of the workflow, not as a generic test step.

## Runtime And Package Manager

- **Python:** 3.12 only. `.python-version` pins `3.12`, and `pyproject.toml` requires `>=3.12,<3.13` because MLX/Torch wheels are the compatibility boundary.
- **Package manager:** `uv`, with dependency resolution locked in `uv.lock`.
- **Hardware:** Apple Silicon is required for MLX training/inference. Non-Apple machines can read the notebooks and build the static walk-through, but should not expect Track A/Track B model runs to work.
- **Notebook outputs:** committed intentionally. They are the learning trail, not disposable build noise.
- **Large artifacts:** weights, adapters, checkpoints, raw/gold data, and Hugging Face caches are gitignored and regenerable.

## Public / Private Boundary

- This public repo must not receive private status, backlog, handoff, business, credential, local path, or strategy material.
- Local MCP config stays in `.mcp.json`; commit only `.mcp.json.example`.
- Secrets stay in `.env`; commit only `.env.example`.

## Script Safety Categories

### Safe Local Checks

- `git diff --check`
- `uv lock --check`
- `python -c "import pathlib, tomllib; tomllib.loads(pathlib.Path('pyproject.toml').read_text())"` validates `pyproject.toml` syntax.

These commands are read-only and do not run model code, install dependencies, or call external services.

### Local Checks After The Environment Exists

- `uv run ruff check .`

`uv run` can synchronize the environment if it is missing or stale. Do not use it as a no-install verification command unless dependency installation is acceptable for the session.

### Local Generated Outputs

- `uv run python docs/walkthrough/build.py` rebuilds `docs/walkthrough/site/`.
- `uv run python notebooks/train_v2_checkpoint.py` writes `notebooks/checkpoints/tiny_gpt_v2/`.
- Running notebooks can update committed notebook outputs and local checkpoints.

These are local, but they mutate files or generated artifacts. Review diffs before committing.

### Regenerating Track A After A Retrain

**Use the orchestrator; do not do this by hand.** Twelve surfaces derive from the Track A
checkpoint, and the two trainers write to the *same* checkpoint path while producing
*different* models — so hand-regeneration reliably ships a stale figure or a downgraded
checkpoint.

```bash
uv run python scripts/regenerate_track_a.py --check      # what is stale? writes nothing
uv run python scripts/regenerate_track_a.py --derived    # rebuild from the current checkpoint
uv run python scripts/regenerate_track_a.py --all        # retrain in order, then rebuild (~65 min)
```

- **Order is load-bearing:** notebook 02 first (it overwrites the checkpoint *without* the
  `<|endstory|>` token), then `train_v2_checkpoint.py` to restore the shipped one, then the
  derived figures. `--all` enforces this; `--derived` refuses to run against a checkpoint
  that has no end-of-story token.
- **`--check` is the staleness gate.** It compares each artifact's recorded provenance in
  `docs/walkthrough/TRACK_A_MANIFEST.json` against the checkpoint on disk, and verifies the
  token ids rendered in `TOKENIZE_SVG`. Run it before publishing.
- **Three surfaces still need a human** and are listed by every run: `GENLOOP_SVG` (its seed
  is chosen so the figure demonstrates its own caption — re-pick with
  `gen_generation_trace.py --hunt`), `TOKENIZE_SVG`'s token ids, and the verbatim
  `rawoutput` story pasted into `content.py`.
- **Notebook 01 is not part of this.** It trains inline, saves no checkpoint, and five of the
  site's live-pulled output blocks come from it — so it stays stable across Track A retrains.
- Hashes in the manifest detect staleness; they are **not** byte-equality tests. MLX on the
  GPU is not bitwise deterministic (see `docs/DECISIONS.md` ADR-0013).

### External Data / Model Downloads

- `uv run jupyter lab` can trigger notebook-driven dataset/model work.
- `uv run python track-b-trialscout/data/fetch_trials.py --target 1500` calls ClinicalTrials.gov and writes raw data.
- Track A dataset loads can download TinyStories through Hugging Face datasets.
- Track B inference/training can download base models through Hugging Face / MLX Hub.
- `uv run python track-b-trialscout/serve/trial_readout_server.py --selftest <NCT_ID>` fetches ClinicalTrials.gov data and loads the local model/adapter.

These are appropriate for model work, but not for a quick docs/metadata verification pass.

### Provider-Cost / API-Key Commands

- `uv run python track-b-trialscout/train/make_gold.py ...` calls Anthropic for teacher labels and spends money.
- Claude-as-judge eval paths spend Anthropic credits when enabled.

These require `ANTHROPIC_API_KEY`, a clear cap, and a reason to spend the budget. The existing scripts are pilot-gated and resumable; keep that pattern.

### Long-Running Model Work

- `uv run python track-b-trialscout/train/run_phase3.py`
- `uv run python track-b-trialscout/eval/infer_and_score.py ...`
- `uv run python track-b-trialscout/serve/ask.py`

These can be slow, GPU-heavy, cache-heavy, or interactive. Do not run them as routine verification for docs-only changes.

### MCP Runtime

- `.mcp.json.example` is the public template. `.mcp.json` is local-only and gitignored.
- The TrialScout MCP server uses stdio; stdout is the protocol channel and logs must stay on stderr.
- `trial_readout_from_record` can run offline once the model/adapter are local; `trial_readout` fetches ClinicalTrials.gov by NCT id.

## CI And Deploy Notes

- GitHub Pages deploys on pushes to `main` that touch `docs/walkthrough/**`, `notebooks/**`, or the Pages workflow.
- The Pages workflow deliberately installs only `jinja2` and `pygments` with `pip`; it does not run `uv sync` or install MLX on Linux.
- Metadata/docs-only changes outside those paths should not trigger the Pages deploy.

## Verification Tiers

- **Docs/metadata only:** `git diff --check`; optionally `uv lock --check` if `uv` is available.
- **Python config changes:** parse `pyproject.toml`, then use `uv lock --check`; run `uv run ruff check .` only if installs/sync are acceptable.
- **Walk-through content/build changes:** rebuild `docs/walkthrough/site/`, inspect the generated diff, and expect Pages deploy on push.
- **Notebook/model/data changes:** use the smallest relevant notebook/script path first, then run the affected Track A or Track B verification. Report downloads, generated artifacts, cost caps, and any committed notebook output changes.
