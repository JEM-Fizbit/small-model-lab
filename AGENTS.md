# AGENTS.md

Guidance for AI coding assistants (Claude Code, Cursor, Copilot, Codex, etc.) working in this repo.

**Read [`CLAUDE.md`](CLAUDE.md) first** — it covers the project, conventions, and gotchas.

## Most important: this is a PUBLIC repo with a public/private split

Internal/personal material lives in a **separate private repo**
([`JEM-Fizbit/slm-lab-private`](https://github.com/JEM-Fizbit/slm-lab-private)), cloned into
`_private/` here (gitignored — local only, never pushed to this repo).

- **Do not commit personal/internal content to this repo** — no live backlog, status/handoff
  notes, business strategy, absolute home paths (`/Users/…`, `~/Projects/…`), or references to
  private repos. That belongs in `_private/`.
- **Status & the live task list are in `_private/HANDOFF.md` and `_private/BACKLOG.md`** (local,
  gitignored — not on GitHub). Read them when resuming.
- The git history was rewritten (2026-06-08) to purge such content; don't reintroduce it.
- `.mcp.json` is gitignored (per-user path); copy `.mcp.json.example`.

See `CLAUDE.md` for the full layout and rules.
