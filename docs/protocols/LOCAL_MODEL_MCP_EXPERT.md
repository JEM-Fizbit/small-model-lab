# Local Model as a Callable MCP Expert

> Package a locally-trained/fine-tuned model (MLX, HF) as a stdio MCP "expert" that Claude Code and the Claude desktop app can call in natural language.

**Applies to:** Python · Apple MLX / `mlx-lm` (or any local inference lib) · MCP Python SDK (FastMCP) · stdio transport
**Last Updated:** 2026-06-08
**Version:** 1.0
**Original Source:** `small-model-lab/track-b-trialscout/serve/` (TrialScout — a distilled Qwen3-4B served as an MCP tool)

---

## Overview

You have a model that runs **locally** (a LoRA-fine-tuned / distilled SLM, an MLX model, etc.) and you want a larger model — or you, conversationally — to call it as a tool. This protocol is the pattern for wrapping it as a **FastMCP stdio server**: the model becomes a "callable expert," the first node of a model-of-experts / orchestrator-over-experts architecture.

The point is **not** that any single local model is production-grade — it's that the *serving layer* is reusable. Build it once on a throwaway; reuse it for every real local model after.

### Key benefits
- One-line switch to expose any local model as a tool, callable from Code **and** Desktop.
- No drift between training and serving (you import the train-time contract).
- Glass box: every output is schema-validated before it leaves the server.

---

## When to Use

| Scenario | Use this? |
|----------|-----------|
| Local model, single user, callable from Claude Code / Desktop | **Yes** |
| Wrap a fine-tuned/distilled model as a tool an orchestrator calls | **Yes** |
| Multi-client / cloud-hosted / needs OAuth | No → [`REMOTE_MCP_SERVICE_PATTERN.md`](REMOTE_MCP_SERVICE_PATTERN.md) |
| Just run a stock model locally for chat | No → [`LOCAL_LLM_OLLAMA.md`](LOCAL_LLM_OLLAMA.md) |
| Reach it from claude.ai web/mobile | Not as stdio — needs remote hosting (see "Going remote") |

---

## Core Concepts

1. **stdio, not HTTP.** Single local user, runs as a subprocess of the client, no network surface, no auth. HTTP/OAuth is the *remote* pattern and is overkill here.
2. **Reuse the training contract — the #1 rule.** Import the *exact* prompt builder and input-record shape used at train time; do **not** re-implement them in the server. This guarantees serve-time input matches what produced your eval score. (Beware import-time side effects — see Anti-Patterns.)
3. **Flat tool schemas.** Expose tool args as top-level fields (`Annotated[str, Field(...)]`), not a single nested Pydantic-model argument. Nested models force the calling model to wrap every call in a `params` object — a real ergonomics tax.
4. **Validate every output.** Validate against your JSON schema; add a deterministic **snap-to-enum** normalizer for near-miss values (casing / out-of-vocab) so the tool is *always* schema-valid.
5. **Lazy singleton load.** Load base+adapter once on first call, not at startup → instant startup; first call pays ~10 s.
6. **Don't block the event loop.** Run blocking inference in a worker thread (`anyio.to_thread.run_sync`).
7. **stderr only.** On stdio, stdout *is* the MCP channel — never `print()` to it.
8. **Ship a `--selftest`.** A one-shot CLI path (fetch/run one example end-to-end, exit) verifies the whole chain without an MCP client (validate-tiny).

---

## Implementation (skeleton)

```python
#!/usr/bin/env python3
"""<name>_mcp — a local model served as a callable MCP expert (stdio)."""
import argparse, json, sys
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

import anyio
from jsonschema import Draft7Validator
from mcp.server.fastmcp import FastMCP
from pydantic import Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "train"))
from format_for_mlx import build_prompt   # noqa: E402  EXACT train-time prompt (reuse, don't reimplement)

BASE_MODEL = "mlx-community/..."           # the base the adapter sits on
ADAPTER = ROOT / "train" / "adapters" / "model"
SCHEMA = json.loads((ROOT / "schema" / "out.schema.json").read_text())
_VALIDATOR = Draft7Validator(SCHEMA)
mcp = FastMCP("name_mcp")

_MODEL = None
def _load():
    global _MODEL
    if _MODEL is None:
        from mlx_lm import load
        print("[name] loading model…", file=sys.stderr, flush=True)   # stderr only
        _MODEL = load(BASE_MODEL, adapter_path=str(ADAPTER))
    return _MODEL

def _infer(record: dict) -> dict:           # BLOCKING — call via to_thread
    from mlx_lm import generate
    model, tok = _load()
    prompt = tok.apply_chat_template(
        [{"role": "user", "content": build_prompt(record)}],
        add_generation_prompt=True, tokenize=False)
    out = generate(model, tok, prompt=prompt, max_tokens=400, verbose=False)
    obj = _extract_json(out)                 # robust balanced-brace parse
    obj = snap_to_enum(obj)                  # deterministic near-miss → schema vocab
    errors = sorted(e.message for e in _VALIDATOR.iter_errors(obj))
    return {"readout": obj, "schema_valid": not errors, "schema_errors": errors}

class Fmt(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"

@mcp.tool(name="domain_action", annotations={
    "title": "…", "readOnlyHint": True, "destructiveHint": False,
    "idempotentHint": True, "openWorldHint": False})
async def domain_action(
    record: Annotated[dict[str, Any], Field(description="…compact input record…")],
    response_format: Annotated[Fmt, Field(description="markdown | json")] = Fmt.MARKDOWN,
) -> str:
    """Docstring with Args/Returns/Examples — it becomes the tool description."""
    result = await anyio.to_thread.run_sync(_infer, dict(record))
    return _format(result, response_format)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", nargs="?", const="<default-id>")
    args = ap.parse_args()
    if args.selftest:
        print(_format(_infer(load_example(args.selftest)), Fmt.MARKDOWN)); sys.exit(0)
    mcp.run()   # stdio
```

`snap_to_enum` (deterministic, free, never turns a correct value wrong):

```python
def _snap(field, value, enum):
    if value in enum: return value
    low = value.strip().lower()
    by_low = {e.lower(): e for e in enum}
    return by_low.get(low, "other" if "other" in enum else value)  # casing → 'other' bucket
```

---

## Wiring it into clients

**Claude Code** — project-scoped `.mcp.json` at repo root:

```json
{ "mcpServers": { "name": {
  "command": "uv",
  "args": ["run", "--directory", "/abs/path/to/project", "python", "path/to/server.py"]
}}}
```

**Claude desktop app** — `~/Library/Application Support/Claude/claude_desktop_config.json`, same `mcpServers` shape. **Two gotchas (GUI apps don't inherit your shell):**
- Use an **absolute path** to the launcher (`/opt/homebrew/bin/uv`), not bare `uv`.
- Add `--directory /abs/path` so it resolves the project regardless of launch cwd.
- The app rewrites this file on preference changes — edit surgically (preserve other servers) and validate the JSON after.

**MCP reach classes** (see [`CLAUDE_SURFACE_PROBE.md`](CLAUDE_SURFACE_PROBE.md)): **A** = Claude Code (`.mcp.json`), **B** = Desktop (`claude_desktop_config.json`), **C** = claude.ai web/mobile (server-side — **cannot** reach a local stdio process).

---

## Going remote (when local isn't enough)

The model runs where the inference lib runs. **MLX is Apple-Silicon-only** — Cloudflare Workers (no GPU, WASM runtime) **cannot host the compute**, only act as a front door.

- **Same machine, remote *access*:** switch `mcp.run()` → `mcp.run(transport="streamable_http")` and put **Cloudflare Tunnel** in front. Compute stays local; you get a public URL + Access auth. This is the only role Cloudflare plays for an MLX model.
- **Truly off-machine:** re-host on real GPU infra (fuse the LoRA, convert off MLX to GGUF/CUDA) — and you lose the local/free/private properties that motivated the local model. Do this only when there's a consumer that needs always-on.
- **Apple-Silicon home server (e.g. Mac mini):** the *same* stdio server runs unchanged — no conversion. Best "always-on" path for a local MLX expert.

---

## Anti-Patterns

```python
# ❌ Nested model arg → calling model must wrap every call in {"params": {...}}
async def tool(params: MyInputModel) -> str: ...
# ✅ Flat args → tool(field_a=…, field_b=…)
async def tool(field_a: Annotated[str, Field(...)], ...) -> str: ...

# ❌ Importing a module that reads data files at import time (fails when only serving)
from infer_and_score import extract_json   # triggers RAW/GOLD file reads on import
# ✅ Import only side-effect-free helpers; inline the small util if needed

# ❌ print() to stdout on a stdio server → corrupts the MCP channel
print("loading model")
# ✅ print(..., file=sys.stderr)

# ❌ Eager model load at module top → slow startup, fails before any tool call
MODEL = load(...)
# ✅ Lazy singleton inside the first call

# ❌ Reimplementing the prompt in the server → silent train/serve drift
prompt = f"You are…\n{json.dumps(record)}"
# ✅ from format_for_mlx import build_prompt  (the exact training builder)
```

---

## Troubleshooting

**Tool not visible after editing config.** Clients read MCP config at launch only — fully quit and reopen (Desktop) or restart the session (Code).

**Works in Code, fails in Desktop.** Almost always PATH: the desktop app can't find bare `uv`/`python`. Use absolute paths + `--directory`.

**Output occasionally fails schema validation.** The model emitted a near-miss enum (casing/synonym) — that's what `snap_to_enum` is for; confirm it's applied *before* validation, both in the server and your eval (so eval == deployed).

---

## Resources

- Reference implementation: `small-model-lab/track-b-trialscout/serve/trial_readout_server.py` (+ `serve/README.md`, `ask.py` REPL).
- [`REMOTE_MCP_SERVICE_PATTERN.md`](REMOTE_MCP_SERVICE_PATTERN.md) — the cloud/OAuth counterpart.
- [`LOCAL_LLM_OLLAMA.md`](LOCAL_LLM_OLLAMA.md) — stock local serving.
- [`CLAUDE_SURFACE_PROBE.md`](CLAUDE_SURFACE_PROBE.md) — the A/B/C MCP-reach classes.
- [`SLM_DISTILLATION_AND_IMPROVEMENT.md`](SLM_DISTILLATION_AND_IMPROVEMENT.md) — how to *build* the model this serves.
- Anthropic MCP Python SDK (FastMCP): `https://github.com/modelcontextprotocol/python-sdk`.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-06-08 | Initial release. Extracted from small-model-lab/TrialScout (Phase 5 MCP packaging). |

---

**Protocol Version**: 1.0
**Last Updated**: 2026-06-08
**Original Source**: small-model-lab (track-b-trialscout/serve)
