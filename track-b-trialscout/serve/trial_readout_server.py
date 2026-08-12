#!/usr/bin/env python3
"""TrialScout MCP server — the fine-tuned Qwen3-4B "expert", exposed as a callable tool.

This is Phase 5 (B7): package the winner of the Track-B A/B (Qwen3-4B + LoRA adapter,
which scores 0.932 on a 1,444-trial natural held-out set under schema v3) as an MCP server so any MCP client (Claude Code,
Claude Desktop, …) can call it. It runs the model **locally and free** via MLX — no API spend.

Two tools, one shared inference core:
  • trial_readout(nct_id)            — fetch the trial from ClinicalTrials.gov v2, then read it out.
  • trial_readout_from_record(record) — read out a trial record you already have (offline / custom).

The contract is kept identical to training by importing the *exact* prompt builder
(`build_prompt` from format_for_mlx.py) and the *exact* record shape (`compact` from
fetch_trials.py). Output is validated against schema/trial_readout.schema.json — no black box.

Run:
  # Wire into an MCP client (stdio) — see serve/README.md and the project .mcp.json:
  uv run python track-b-trialscout/serve/trial_readout_server.py

  # Smoke-test end-to-end without an MCP client (validate-tiny-before-the-long-run):
  uv run python track-b-trialscout/serve/trial_readout_server.py --selftest NCT02942290
"""
from __future__ import annotations

import argparse
import json
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

import anyio
import requests
from jsonschema import Draft7Validator
from mcp.server.fastmcp import FastMCP
from pydantic import Field

# --- reuse the training contract verbatim (no drift between train and serve) ---
ROOT = Path(__file__).resolve().parents[1]  # track-b-trialscout/
sys.path.insert(0, str(ROOT / "train"))
sys.path.insert(0, str(ROOT / "data"))
sys.path.insert(0, str(ROOT / "schema"))
from format_for_mlx import build_prompt  # noqa: E402  exact prompt the model was trained on
from fetch_trials import compact  # noqa: E402         CT.gov study object -> compact record
from normalize import snap_to_enum  # noqa: E402        snap near-miss enum values to schema vocab
from derive import merge_risk_flags  # noqa: E402      compute the arithmetic risk flags, don't ask
from fingerprint import check as check_schema  # noqa: E402  refuse a v1 adapter on a v2 schema

# --- config (no magic numbers: every knob named + commented) ---
BASE_MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"  # ADR-0002/0009: Qwen won the A/B
ADAPTER = ROOT / "train" / "adapters" / "qwen_v3_it400"  # the 28 MB LoRA we trained (gitignored)
# NOTE: must track the schema. Pointing this at a v1 adapter while schema/ is v2 produces
# output that still VALIDATES (the normalizer snaps unknown values to "other") but is wrong.
# Caught by --selftest on 2026-08-10; that silent-validity failure mode is why the selftest exists.
SCHEMA_PATH = ROOT / "schema" / "trial_readout.schema.json"
CTGOV = "https://clinicaltrials.gov/api/v2/studies"      # public API v2, no key
MAX_TOKENS = 400                                         # readout JSON fits well under this

SCHEMA = json.loads(SCHEMA_PATH.read_text())
_VALIDATOR = Draft7Validator(SCHEMA)

mcp = FastMCP("trialscout_mcp")


class ResponseFormat(str, Enum):
    """Output format for the readout."""
    MARKDOWN = "markdown"  # human-readable summary
    JSON = "json"          # the structured object + validation metadata


# --- model: lazy singleton so server startup is instant; first call pays the load (~10s) ---
_MODEL: tuple[Any, Any] | None = None  # (model, tokenizer)


def _load_model() -> tuple[Any, Any]:
    """Load base Qwen + LoRA adapter once, cache for the server's lifetime.

    Logs to stderr only — stdio servers must never write to stdout (it's the MCP channel).
    """
    global _MODEL
    if _MODEL is None:
        from mlx_lm import load
        # A wrong adapter still produces schema-VALID output (the normalizer snaps unknown
        # values to "other"), so validation cannot catch this. Check the contract instead.
        ok, msg = check_schema(ADAPTER)
        if not ok:
            raise RuntimeError(msg)
        print(f"[trialscout] {msg}", file=sys.stderr, flush=True)
        print(f"[trialscout] loading {BASE_MODEL} + adapter {ADAPTER} ...", file=sys.stderr, flush=True)
        _MODEL = load(BASE_MODEL, adapter_path=str(ADAPTER))
        print("[trialscout] model ready", file=sys.stderr, flush=True)
    return _MODEL


def _extract_json(text: str) -> dict | None:
    """Pull the first balanced {...} object out of the model's output.

    Same logic as eval/infer_and_score.py (kept inline to avoid that module's import-time
    file reads of data/raw + data/gold, which need not exist when only serving).
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    return None
    return None


def _infer(raw_record: dict) -> dict:
    """BLOCKING: run base+adapter on one compact trial record; return readout + validation.

    Must be called inside a worker thread (anyio.to_thread) so it doesn't block the event loop.
    The model was trained to emit the 8 fields *without* nct_id, so we inject it from the input.
    """
    from mlx_lm import generate
    model, tok = _load_model()
    prompt = tok.apply_chat_template(
        [{"role": "user", "content": build_prompt(raw_record)}],
        add_generation_prompt=True, tokenize=False)
    out = generate(model, tok, prompt=prompt, max_tokens=MAX_TOKENS, verbose=False)

    obj = _extract_json(out)
    if obj is None:
        return {"_ok": False, "_error": "model did not emit parseable JSON", "_raw": out[:500]}

    nct = raw_record.get("nct_id") or "unknown"
    # nct_id first for readability; our injected value wins over any the model echoed
    readout = {"nct_id": nct, **{k: v for k, v in obj.items() if k != "nct_id"}}
    readout = snap_to_enum(readout)  # fix near-miss enum values (casing / out-of-vocab) pre-validation
    # Seven of the eleven risk flags are arithmetic on fields in the record. Compute those and
    # keep only the model's four judgement flags -- it is measurably worse at `enrollment < 50`
    # than an `if` statement, having learned the teacher's errors. See schema/derive.py.
    readout["risk_flags"] = merge_risk_flags(raw_record, readout.get("risk_flags_judgement"))
    errors = sorted(e.message for e in _VALIDATOR.iter_errors(readout))
    return {"_ok": True, "readout": readout, "_schema_valid": not errors, "_schema_errors": errors}


def _fetch_trial(nct_id: str) -> dict | None:
    """BLOCKING: fetch one trial from CT.gov v2 and reduce it to the model's record shape.

    Returns None if the trial doesn't exist, or exists but isn't a phased interventional
    trial (compact() filters those — TrialScout was only trained on that population).
    """
    r = requests.get(f"{CTGOV}/{nct_id}", params={"format": "json"}, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return compact(r.json())


# --- shared output formatting (DRY across both tools) ---
def _render_markdown(readout: dict, valid: bool, errors: list[str]) -> str:
    r = readout
    risk = r.get("risk_flags") or []
    mods = r.get("modalities")
    # An empty list is a claim ("this trial has no drug asset"), not a missing answer,
    # so it gets said out loud rather than rendered as an empty bullet.
    if mods:
        mod_line = ", ".join(mods)
    elif isinstance(mods, list):
        mod_line = "_none — this trial tests no drug or biologic_"
    else:
        mod_line = "unknown"
    lines = [
        f"# TrialScout readout — {r.get('nct_id')}",
        "",
        f"- **Phase**: {r.get('phase')}",
        f"- **Indication**: {r.get('indication')}",
        f"- **Intervention type**: {r.get('intervention_class')}",
        f"- **Modalities**: {mod_line}",
        f"- **Primary endpoint**: {r.get('primary_endpoint_type')}",
        f"- **Sponsor type**: {r.get('sponsor_type')}",
        f"- **Est. readout**: {r.get('est_readout')}",
        f"- **Risk flags**: {', '.join(risk) if risk else 'none'}",
        "",
        f"**Investor note** — {r.get('investor_note')}",
    ]
    if not valid:
        lines += ["", f"> ⚠️ Schema check failed ({len(errors)} issue(s)): " + "; ".join(errors)]
    return "\n".join(lines)


def _format_result(result: dict, fmt: ResponseFormat) -> str:
    """Turn the _infer() result dict into the tool's string response."""
    if not result["_ok"]:
        return f"Error: {result['_error']}. Raw model output (truncated): {result.get('_raw', '')}"
    if fmt == ResponseFormat.JSON:
        return json.dumps({
            "readout": result["readout"],
            "schema_valid": result["_schema_valid"],
            "schema_errors": result["_schema_errors"],
        }, indent=2, ensure_ascii=False)
    return _render_markdown(result["readout"], result["_schema_valid"], result["_schema_errors"])


# --- tools (flat argument schemas — the calling model passes fields directly) ---
@mcp.tool(
    name="trial_readout",
    annotations={
        "title": "TrialScout: read out a trial by NCT ID",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,  # fetches from ClinicalTrials.gov
    },
)
async def trial_readout(
    nct_id: Annotated[str, Field(
        description="ClinicalTrials.gov identifier, e.g. 'NCT02942290' (case-insensitive).",
        pattern=r"^[Nn][Cc][Tt]\d{8}$")],
    response_format: Annotated[ResponseFormat, Field(
        description="'markdown' (human-readable) or 'json' (structured object + schema validity).",
    )] = ResponseFormat.MARKDOWN,
) -> str:
    """Produce a structured, investor-relevant readout for one oncology clinical trial.

    Fetches the trial from ClinicalTrials.gov v2 by its NCT ID, then runs the fine-tuned
    Qwen3-4B TrialScout model (locally, no API spend) to extract a normalized readout:
    phase, indication, intervention class, therapeutic modalities, primary endpoint type,
    sponsor type, estimated readout window, investor-relevant risk flags, and a
    <=2-sentence investor note. The output is validated against the TrialScout JSON schema.

    `modalities` is a LIST -- a trial combining an antibody with chemotherapy returns both.
    It is EMPTY when the trial tests no drug at all (surgery, external-beam radiotherapy,
    a device, supportive care); `intervention_class` says which of those it is.

    Scope: trained only on **phased interventional oncology** trials. Non-oncology or
    phase-less trials are out of distribution; the tool reports if a trial is ineligible.

    Args:
        nct_id (str): ClinicalTrials.gov id, e.g. 'NCT02942290' (case-insensitive).
        response_format (ResponseFormat): 'markdown' (default) or 'json'.

    Returns:
        str: Markdown summary, or a JSON object:
            {
              "readout": {nct_id, phase, indication, intervention_class, modalities[],
                          primary_endpoint_type, sponsor_type, est_readout,
                          risk_flags[], investor_note},
              "schema_valid": bool,
              "schema_errors": [str]
            }
        On failure returns "Error: <reason>" (not found / ineligible / network / unparseable).

    Examples:
        - "Give me an investor readout on NCT02942290" -> nct_id='NCT02942290'.
        - "Summarize trial NCT05012345 as JSON" -> nct_id='NCT05012345', response_format='json'.
        - Don't use for: a non-cancer trial, or a record you already have in hand
          (use trial_readout_from_record instead).
    """
    nct_id = nct_id.upper()
    try:
        raw = await anyio.to_thread.run_sync(_fetch_trial, nct_id)
    except requests.RequestException as e:
        return (f"Error: could not reach ClinicalTrials.gov for {nct_id} "
                f"({type(e).__name__}). Try again, or pass the record to trial_readout_from_record.")
    if raw is None:
        return (f"Error: {nct_id} was not found on ClinicalTrials.gov, or it is not a "
                f"phased interventional trial. TrialScout only covers interventional oncology "
                f"trials with a defined phase.")
    result = await anyio.to_thread.run_sync(_infer, raw)
    return _format_result(result, response_format)


@mcp.tool(
    name="trial_readout_from_record",
    annotations={
        "title": "TrialScout: read out a trial from a supplied record",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,  # no network; runs purely on the supplied record
    },
)
async def trial_readout_from_record(
    record: Annotated[dict[str, Any], Field(
        description=(
            "A compact trial record with ClinicalTrials.gov-style fields "
            "(brief_title, phases, overall_status, lead_sponsor, lead_sponsor_class, conditions, "
            "interventions, primary_outcomes, enrollment, allocation, masking, n_arms, brief_summary). "
            "Include 'nct_id' if known; it is echoed into the readout, not inferred."))],
    response_format: Annotated[ResponseFormat, Field(
        description="'markdown' (human-readable) or 'json' (structured object + schema validity).",
    )] = ResponseFormat.MARKDOWN,
) -> str:
    """Read out a trial from a record you already have (no ClinicalTrials.gov fetch).

    Same model and output contract as `trial_readout`, but you supply the compact trial
    record directly. Use this for trials not in CT.gov, records you fetched elsewhere, or
    hypothetical/edited records. Runs fully locally and offline.

    Args:
        record (dict): compact CT.gov-style fields (see field description); include
            'nct_id' if known (echoed into the readout, not inferred from the record).
        response_format (ResponseFormat): 'markdown' (default) or 'json'.

    Returns:
        str: Same schema as trial_readout (markdown summary or JSON with readout +
        schema_valid + schema_errors). On failure returns "Error: <reason>".

    Examples:
        - Read out a record fetched via the data pipeline.
        - Test the model on a hand-edited record to probe a field.
        - Don't use when you only have an NCT id (use trial_readout, which fetches for you).
    """
    rec = dict(record)
    rec.setdefault("nct_id", "unknown")
    result = await anyio.to_thread.run_sync(_infer, rec)
    return _format_result(result, response_format)


def _selftest(nct_id: str) -> None:
    """Run one trial end-to-end (fetch -> infer -> validate) and print both formats, then exit."""
    print(f"[selftest] fetching {nct_id} ...", file=sys.stderr, flush=True)
    raw = _fetch_trial(nct_id)
    if raw is None:
        print(f"[selftest] {nct_id} not found or not a phased interventional trial.", file=sys.stderr)
        sys.exit(1)
    result = _infer(raw)
    print(_format_result(result, ResponseFormat.MARKDOWN))
    print("\n--- JSON ---")
    print(_format_result(result, ResponseFormat.JSON))
    if result["_ok"] and not result["_schema_valid"]:
        sys.exit(2)  # parsed but off-schema — surface as a non-zero exit for CI/QA


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="TrialScout MCP server (stdio transport).")
    ap.add_argument(
        "--selftest", metavar="NCT_ID", nargs="?", const="NCT02942290",
        help="Run one trial end-to-end and exit (default NCT02942290) instead of starting the server.")
    args = ap.parse_args()
    if args.selftest:
        _selftest(args.selftest)
    else:
        mcp.run()  # stdio
