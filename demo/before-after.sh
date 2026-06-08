#!/usr/bin/env bash
# Live before/after demo for dkan-ai-skills.
#
# Asks ONE gnarly DKAN/Drupal question two ways and prints the answers labeled,
# side by side:
#   BEFORE — a stock model with no skill (parametric knowledge only)
#   AFTER  — the same model with the dkan-ai-skills plugin installed
#
# Non-interactive, single command. This is a PRESENTATION AID, separate from the
# measurement path (that is bin/eval + evals/). It shows live, on one question,
# the same effect the Phase 2 task-outcome eval measures across many
# (evals/tasks/REPORT.md): the base model answers confidently but with stale or
# invented specifics (wrong version constraints, fabricated service/method names,
# nonexistent config keys); the skill arm answers from the packaged reference docs.
#
# Usage:
#   demo/before-after.sh ["your question"]
#
# Requires an AUTHENTICATED claude (claude login, or ANTHROPIC_API_KEY). Like
# `bin/eval trigger`, it spawns `claude -p`, so it will NOT work inside a
# sandboxed Claude Code agent session (nested claude -p returns HTTP 401). Run it
# from a normal terminal.
#
# Env:
#   DEMO_MODEL    pin both arms to one model id (default: your configured model)
#   DEMO_CLAUDE   path to the claude binary (default: claude) — override for tests
#
# Talking points (good questions to try — each DISCRIMINATES in the benchmark):
#   - "What exact Drupal core version constraint does drupal/ai 1.4.x require?"
#       base: stale "^10.3 || ^11"  ·  skill: "^10.5 || ^11.2"
#   - "Write a minimal write-capable #[Tool] plugin for drupal/mcp_server on the
#      mcp/sdk 0.6 API: attribute, base class, execute() signature, access gate."
#       base: invented ToolBase/CallToolResult  ·  skill: #[Tool]+ClientGateway+checkAccess
#   - "What @group identifiers does DKAN core use to split functional tests in CI?"
#       base: "@group functional"  ·  skill: functional1 / functional2 / functional3
#   - "Which config key controls the datastore query API the DKAN React frontend calls?"
#       base: guesses / "not sure"  ·  skill: datastore_query_api

set -uo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
claude_bin="${DEMO_CLAUDE:-claude}"
model_args=()
[[ -n "${DEMO_MODEL:-}" ]] && model_args=(--model "$DEMO_MODEL")

default_q="What exact Drupal core version constraint does drupal/ai 1.4.x require? Give the precise constraint string."
question="${1:-$default_q}"

command -v "$claude_bin" >/dev/null 2>&1 || {
  echo "error: '$claude_bin' not found — need an authenticated claude CLI (claude login or ANTHROPIC_API_KEY)" >&2
  exit 1
}

tmp_base="$(mktemp -d)"
tmp_skill="$(mktemp -d)"
cleanup() { rm -rf "$tmp_base" "$tmp_skill"; }
trap cleanup EXIT

# AFTER arm: install the plugin's skills+commands into an isolated project root,
# so the demo is self-contained and doesn't depend on your global install state.
"$repo_root/bin/install" "$tmp_skill/.claude" >/dev/null 2>&1 || {
  echo "error: bin/install failed" >&2
  exit 1
}

ask() { # <cwd> <prompt>  -> answer on stdout
  ( cd "$1" && "$claude_bin" -p "$2" --strict-mcp-config "${model_args[@]+"${model_args[@]}"}" 2>/dev/null )
}

echo "Running both arms (same model — one with the skill, one without)…" >&2

base_ans="$(ask "$tmp_base" "$question")"

skill_prompt="$question

You have DKAN / Drupal-AI / MCP Server skills installed in this project. Consult the relevant skill's reference docs and answer precisely — exact version constraints, class names, and identifiers."
skill_ans="$(ask "$tmp_skill" "$skill_prompt")"

rule() { printf '============================================================\n'; }

echo
echo "QUESTION:"
echo "  $question"
echo
rule; echo "BEFORE — no skill (stock model, parametric knowledge only)"; rule
printf '%s\n' "${base_ans:-(no output — check auth / model)}"
echo
rule; echo "AFTER — with dkan-ai-skills installed"; rule
printf '%s\n' "${skill_ans:-(no output — check auth / model)}"
echo
echo "(Presentation aid. Measured results across many tasks: evals/tasks/REPORT.md and bin/eval.)"
