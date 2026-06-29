import type { Config } from "knowhub";

const LOCAL_PROTOCOLS_BASE = "/Users/johnemilad/Projects/ai-knowledge/protocols";

// slm-lab is the reference implementation for these patterns — sync local copies so the
// playbook is visible in-repo. Edit protocols in ai-knowledge (canonical), then run `knowhub`.
const config: Config = {
  resources: [
    // SLM build pattern (distill → eval → improve; the two ceilings + verifier path)
    {
      plugin: "local",
      pluginConfig: { path: `${LOCAL_PROTOCOLS_BASE}/SLM_DISTILLATION_AND_IMPROVEMENT.md` },
      overwrite: true,
      outputs: ["docs/protocols/SLM_DISTILLATION_AND_IMPROVEMENT.md"],
    },
    // Serve pattern (local model → callable MCP stdio expert)
    {
      plugin: "local",
      pluginConfig: { path: `${LOCAL_PROTOCOLS_BASE}/LOCAL_MODEL_MCP_EXPERT.md` },
      overwrite: true,
      outputs: ["docs/protocols/LOCAL_MODEL_MCP_EXPERT.md"],
    },
    // Data source (ClinicalTrials.gov v2 — TrialScout's input)
    {
      plugin: "local",
      pluginConfig: { path: `${LOCAL_PROTOCOLS_BASE}/CLINICALTRIALS_GOV_API.md` },
      overwrite: true,
      outputs: ["docs/protocols/CLINICALTRIALS_GOV_API.md"],
    },
  ],
};

export default config;
