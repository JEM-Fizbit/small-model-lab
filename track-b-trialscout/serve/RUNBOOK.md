# Running TrialScout without wrecking the machine

Measured on the development box: **Apple M5, 10 CPU cores (6P/4E), 10 GPU cores, 24 GB unified
memory.** Scale the numbers if yours differs; the *shape* of the advice holds for any Apple Silicon.

## The thing that is easy to get wrong

Apple Silicon has **one memory pool shared between the system and the GPU**. There is no separate
VRAM to run out of — an over-allocated model evicts your desktop to swap, and the whole machine
crawls while the job itself still looks healthy. It is not a CPU problem, and adding cores would not
help: token generation is **memory-bandwidth-bound**, so the GPU spends most of its time waiting on
memory rather than computing.

This happened here on 2026-08-10 with `--batch-size 16`.

## Measured profile — Qwen3-4B-Instruct-2507-4bit + LoRA

| batch | s/trial | peak memory | KV cache over weights | use when |
|---|---|---|---|---|
| 1 | 5.72 | 3.25 GB | 0.96 GB | reproducing a published number; machine in active use |
| **4** | **2.41** | **3.51 GB** | 1.22 GB | **default for batch eval while you work** |
| 8 | 2.26 | 4.57 GB | 2.28 GB | machine mostly idle |
| 16 | 2.33 | ~8–9 GB (extrapolated) | ~6 GB | idle machine only — this is what caused the incident |

Model weights alone: **2.29 GB** resident.

**Batch 4 is the sweet spot and it is not close.** It captures 2.4x of the 2.5x available speedup
for 0.26 GB more than sequential. Going 4 → 16 buys ~3% throughput for roughly 2.5x the memory.

## Settings that matter

```bash
# Batch eval, machine in use — the default
uv run python track-b-trialscout/eval/infer_and_score.py \
    --model mlx-community/Qwen3-4B-Instruct-2507-4bit \
    --adapter track-b-trialscout/train/adapters/qwen_v2s_aug \
    --label myrun --batch-size 4 --memory-limit-gb 8
```

- **`--memory-limit-gb` (default 8) is the guardrail.** It calls `mx.set_memory_limit()`, so MLX
  cannot grow into the space the OS needs. Keep it. Raise it only on an idle machine.
- **`--batch-size 1` is required when the number must match a published figure.** Batching changes
  padding and therefore numerics: measured **6 of 150 predictions changed, overall 0.939 → 0.936**.
  Fine for a diagnostic where both arms get the same treatment; not fine for a cited number.
- **Runs resume.** Predictions are appended and flushed per batch, so an interrupted job restarts
  where it stopped. `--restart` discards and starts over.

## Serving (the MCP server)

Single request at a time, so memory is the model plus one KV cache: **~3.3 GB steady state**. This is
comfortable alongside normal desktop work and needs no tuning. First call pays a ~10 s model load;
afterwards the model stays resident for the life of the server.

## Training

| config | peak memory | wall clock |
|---|---|---|
| 16 layers, batch 4, max-seq **1536**, 700 iters | ~10 GB | ~55–70 min |
| 16 layers, batch 4, max-seq **2560**, 1000 iters | **14.3 GB** | ~2 h |

Activation memory scales with sequence length, so the v3 config (2560, needed so no example is
truncated) costs ~40% more than v2's. Measured on the 24 GB M5: it ran without swapping, but left
the machine at **8% free** — stable, and with no headroom for anything else.

**Do not run inference at the same time** — both want the same pool, and that combination is what
makes a 24 GB machine unusable. Training is the one job worth running while you are away. If you
must work alongside it, drop to `--batch-size 2`, which roughly halves activation memory for about
30 extra minutes.

**Check the validation curve before shipping the final weights.** `mlx_lm.lora` saves the LAST
iteration, not the best. On the v3 run val loss bottomed at iteration 400 (0.496) and rose to 0.640
by 1000 — the saved adapter was the worst checkpoint, and using `0000400_adapters.safetensors`
recovered +0.008 overall for free. The optimum is config-specific: v2 was still improving at 700.

## Quick health check while something is running

```bash
memory_pressure | tail -3
```

Watch **Pageouts** across two samples ~20 s apart, not the absolute value — the counter is cumulative
since boot and tells you nothing on its own. A few hundred pages between samples is fine; tens of
thousands means it is swapping and you should lower `--batch-size`.

## Summary

| situation | batch | memory cap |
|---|---|---|
| you are working on the machine | 4 | 8 GB |
| machine is idle | 8 | 12 GB |
| reproducing a cited number | 1 | 8 GB |
| serving via MCP | n/a | default |
| LoRA training | n/a | run nothing else |
