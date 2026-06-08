# Vendored eval harness — provenance

`run_eval.py` and `utils.py` are vendored (copied) from Anthropic's **skill-creator**
skill, which ships the canonical skill-effectiveness eval harness.

## Why vendored (not shelled-out)

The plan (EVAL-HARNESS-PLAN.md, decision D-new-1) preferred shelling out to the installed
skill-creator scripts. We vendor instead because:

1. **Python compatibility.** Upstream uses PEP 604 `X | None` type syntax (Python 3.10+);
   this machine has only system Python **3.9**. Vendoring lets us add
   `from __future__ import annotations` (makes annotations lazy) — a one-line fix — without
   editing an installed plugin.
2. **Reproducibility.** skill-creator is an installed plugin that can update under us
   (a reviewer concern). A pinned in-repo copy makes eval runs reproducible across machines
   and contributors.

## Source

- Skill: `skill-creator` (Anthropic, claude-plugins-official marketplace)
- Marketplace checkout commit: `ed3ff7a`
- Upstream path: `skills/skill-creator/scripts/{run_eval.py,utils.py}`
- Captured: 2026-06-08
- `claude` CLI at capture time: `2.1.168`

## Changes from upstream

- `utils.py`: added module docstring note + `from __future__ import annotations`. Logic unchanged.
- `run_eval.py`: added `from __future__ import annotations`; changed the `parse_skill_md`
  import to this package's layout (`from .utils import …` with a direct-exec fallback);
  added `--strict-mcp-config` to the `claude -p` invocation so nested calls don't start the
  user's MCP servers (irrelevant to triggering, and a large speedup across hundreds of calls).
  Logic otherwise identical.

## What it does / does not measure

`run_eval.py` writes the skill's **description** into a temporary *command* file under an
isolated project root's `.claude/commands/`, runs `claude -p <query>`, and detects whether
Claude fires a `Skill`/`Read` tool call naming that command. This is a **description-attraction
proxy** — it measures whether a description attracts the model in isolation. It is **not** real
SKILL.md auto-load, and it tests one description at a time (no cross-skill arbitration).

## Updating

To re-sync with upstream: re-copy the two files, re-apply the two changes above, and bump the
commit/date here.
