# serve/ — TrialScout as an MCP "expert" (Phase 5 / B7)

This packages the Track-B winner — **Qwen3-4B + our LoRA adapter** (scored 0.922 vs a 0.368
baseline, ADR-0002/0009) — as an **MCP server** so any MCP client (Claude Code, Claude Desktop)
can call it. It runs the model **locally via MLX — no API spend**.

It's the first "callable expert" in the model-of-experts / chief-of-staff vision: a small,
fine-tuned model that does one narrow job well, exposed as a tool a larger model can orchestrate.

## What it exposes

`trial_readout_server.py` is a FastMCP **stdio** server named `trialscout_mcp` with two tools:

| Tool | What it does | Network |
|---|---|---|
| `trial_readout(nct_id, response_format?)` | Fetch the trial from ClinicalTrials.gov v2 by NCT id, then read it out. | yes (CT.gov) |
| `trial_readout_from_record(record, response_format?)` | Read out a trial record you already have (offline / custom). | no |

Both return the same readout contract (`schema/trial_readout.schema.json`): `phase`, `indication`,
`modality`, `primary_endpoint_type`, `sponsor_type`, `est_readout`, `risk_flags[]`, `investor_note`.
`response_format` is `"markdown"` (default, human-readable) or `"json"` (the structured object plus
`schema_valid` / `schema_errors`). Output is validated against the schema on every call — no black box.

**Scope:** trained only on **phased interventional oncology** trials. Non-oncology or phase-less
trials are out of distribution; the tools say so rather than guessing.

## Design notes (no drift, no magic)

- The server imports the **exact** training prompt (`build_prompt` from `train/format_for_mlx.py`)
  and the **exact** record shape (`compact` from `data/fetch_trials.py`), so what the model sees at
  serve time matches what it saw at train time.
- The model trained to emit the 8 fields *without* `nct_id`; the server injects `nct_id` from the
  input and validates the assembled object.
- The base model + adapter load **once, lazily** on the first call (≈10 s); startup is instant.
- Heavy work (fetch, inference) runs in a worker thread so the async event loop stays responsive.
- Logs go to **stderr only** (stdout is the MCP channel on stdio).

## Play with it interactively (no MCP client needed)

```bash
# Interactive REPL: loads the model once, then loops. Type an NCT id, or 'random', or 'help'.
uv run python track-b-trialscout/serve/ask.py
#   trial> NCT02942290        → readout for that trial
#   trial> random             → pick a random trial from the local dataset and read it out
#   trial> json / md          → switch output format
#   trial> q                  → quit
```

This is the hands-on way to *touch* the model directly — same model the server wraps.

## Smoke-test (one-shot, no MCP client needed)

```bash
# Fetch one trial, run it end-to-end, print markdown + JSON, then exit.
uv run python track-b-trialscout/serve/trial_readout_server.py --selftest NCT02942290
# exit 0 = ok & schema-valid; 1 = not found/ineligible; 2 = parsed but off-schema.
```

## Use it from Claude Code

A project-scoped [`.mcp.json`](../../.mcp.json) at the repo root registers the server as
`trialscout`. Launch Claude Code from the project root and approve it when prompted:

```bash
cd ~/Projects/slm-lab && claude
# then, in session:  /mcp        (shows trialscout connected)
#                    "Give me a TrialScout readout on NCT02942290"
```

Prerequisites: `uv sync` has been run, and the LoRA adapter exists at
`train/adapters/qwen/` (regenerate via Phase 3 if it's missing after a fresh clone — see
[`docs/HANDOFF.md`](../../docs/HANDOFF.md) §3).

## Use it from any other MCP client

Point the client at the same stdio command:

```
command: uv
args:    ["run", "--directory", "/Users/johnemilad/Projects/slm-lab",
          "python", "track-b-trialscout/serve/trial_readout_server.py"]
```
