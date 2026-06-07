#!/usr/bin/env bash
#
# dependency-gate.sh — deterministic gate for agent-initiated dependency installs.
#
# Shipped by the drupal-dkan-ai plugin as a PreToolUse(Bash) hook. It BLOCKS
# (exit 2) any command that ADDS a named package dependency — `composer require`,
# `npm install <pkg>` / `npm add`, `yarn add`, `pnpm add`, `bun add`, `pip install <pkg>`,
# `uv add` / `uv pip install <pkg>`, `poetry add`, `pipx install`, and the common
# `cargo`/`go`/`gem`/`deno` equivalents — so a human vets the package before it
# enters the project. This guards against SLOPSQUATTING: LLMs hallucinate
# plausible-but-nonexistent package names (~1 in 5 suggested packages don't exist)
# and attackers pre-register them. CI dependency review + lockfile/hash pinning stay
# the authoritative gate; this is the fast local stop (the verification ladder —
# CLAUDE.md is advisory, hooks are deterministic).
#
# It does NOT gate lockfile-driven installs (`composer install`, bare `npm install`,
# `npm ci`, `yarn install`, `pip install -r requirements.txt`, `pip install -e .`) —
# those add nothing not already reviewed.
#
# Plugin hooks fire for every Bash call in every project; supply-chain risk is
# universal, so this gate is intentionally NOT project-scoped. Keep it low-friction:
# vet + approve the install yourself and re-run, or bypass with CLAUDE_SKIP_DEP_GATE=1.
#
# Contract: hook payload arrives as JSON on stdin; exit 0 = allow, exit 2 = block
# (stderr is shown to the agent). Requires jq; fails open if absent.

set -uo pipefail

dbg() { [ -n "${CLAUDE_GATE_DEBUG:-}" ] && echo "dependency-gate[dbg]: $*" >&2 || true; }

input="$(cat)"
command -v jq >/dev/null 2>&1 || { dbg "jq missing; fail open"; exit 0; }

cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // empty')"
[ -n "$cmd" ] || exit 0

[ "${CLAUDE_SKIP_DEP_GATE:-}" = "1" ] && { echo "dependency-gate: bypassed (CLAUDE_SKIP_DEP_GATE=1)." >&2; exit 0; }

managers='composer npm pnpm yarn bun pip pip3 uv poetry pipx cargo go gem deno'

is_manager() {
  local t="$1" m
  for m in $managers; do [ "$t" = "$m" ] && return 0; done
  return 1
}

# First argument that is not a flag — i.e. the package name. Empty if none.
first_positional() {
  local t
  for t in "$@"; do
    case "$t" in
      -*) ;;                      # flag, skip
      *) printf '%s' "$t"; return 0 ;;
    esac
  done
}

# pip: first real package target — skip flags, `.` (local), and -r/-e/-c values.
first_pip_target() {
  local skip=0 t
  for t in "$@"; do
    if [ "$skip" = 1 ]; then skip=0; continue; fi
    case "$t" in
      -r|--requirement|-e|--editable|-c|--constraint) skip=1 ;;  # consumes next token
      .|-*) ;;                                                    # local install / flag
      *) printf '%s' "$t"; return 0 ;;
    esac
  done
}

# npm-family: first real package target — skip value-consuming flags + their values
# so a lockfile install with options (`npm install --prefix dir`) is not misread as
# installing a package called "dir". (A token consumed here as a flag value is one
# the manager itself treats as a value, not a package, so skipping it cannot hide a
# real `install <pkg>` — the parser stays aligned with the manager's own semantics.)
first_npm_target() {
  local skip=0 t
  for t in "$@"; do
    if [ "$skip" = 1 ]; then skip=0; continue; fi
    case "$t" in
      --prefix|--registry|-w|--workspace|--cache|--tag|--omit|--include|--userconfig|--globalconfig) skip=1 ;;
      -*) ;;          # valueless flag
      *) printf '%s' "$t"; return 0 ;;
    esac
  done
}

# go: first remote package target — skip flags and local paths (`.`, `./...`), so
# `go install ./...` / `go build .` (local builds) are not treated as installs.
first_go_target() {
  local t
  for t in "$@"; do
    case "$t" in
      .|./*|-*) ;;    # local path / flag
      *) printf '%s' "$t"; return 0 ;;
    esac
  done
}

MATCH=""  # "<manager> <package>" when a gating install is found.

# Decide whether one command segment adds a named package; set MATCH and return 0.
scan_segment() {
  local seg="$1"
  local -a toks
  read -ra toks <<< "$seg"
  local n=${#toks[@]} i=0
  # Skip leading wrappers (sudo, ddev/lando/exec) and VAR=val assignments to reach
  # the manager token — so `ddev composer require`, `ddev exec npm add` are seen.
  while [ "$i" -lt "$n" ]; do
    case "${toks[$i]}" in
      sudo|ddev|lando|exec|*=*) i=$((i + 1)) ;;
      *) break ;;
    esac
  done
  [ "$i" -lt "$n" ] || return 1
  # `python -m pip install ...` → treat pip as the manager.
  case "${toks[$i]}" in
    python|python2|python3|python3.*)
      if [ "$((i + 2))" -lt "$n" ] && [ "${toks[$((i + 1))]}" = "-m" ]; then
        case "${toks[$((i + 2))]}" in pip|pip3) i=$((i + 2)) ;; esac
      fi
      ;;
  esac
  is_manager "${toks[$i]}" || return 1
  local mgr="${toks[$i]}"; i=$((i + 1))
  [ "$i" -lt "$n" ] || return 1
  local sub="${toks[$i]}"; i=$((i + 1))
  local -a args=("${toks[@]:$i}")
  local p=""

  case "$mgr" in
    composer)
      [ "$sub" = "require" ] && { MATCH="composer $(first_positional ${args[@]+"${args[@]}"})"; return 0; }
      ;;
    npm|pnpm|bun)
      case "$sub" in
        add) MATCH="$mgr $(first_npm_target ${args[@]+"${args[@]}"})"; return 0 ;;
        install|i)
          p="$(first_npm_target ${args[@]+"${args[@]}"})"
          [ -n "$p" ] && { MATCH="$mgr $p"; return 0; } ;;
      esac
      ;;
    yarn)
      [ "$sub" = "add" ] && { MATCH="yarn $(first_positional ${args[@]+"${args[@]}"})"; return 0; }
      ;;
    pip|pip3)
      if [ "$sub" = "install" ]; then
        p="$(first_pip_target ${args[@]+"${args[@]}"})"
        [ -n "$p" ] && { MATCH="$mgr $p"; return 0; }
      fi
      ;;
    cargo)
      case "$sub" in
        add|install) MATCH="cargo $(first_positional ${args[@]+"${args[@]}"})"; return 0 ;;
      esac
      ;;
    go)
      case "$sub" in
        get|install)
          p="$(first_go_target ${args[@]+"${args[@]}"})"
          [ -n "$p" ] && { MATCH="go $p"; return 0; } ;;
      esac
      ;;
    gem)
      [ "$sub" = "install" ] && { MATCH="gem $(first_positional ${args[@]+"${args[@]}"})"; return 0; }
      ;;
    uv)
      # `uv add <pkg>`, `uv pip install <pkg>`, `uv tool install <pkg>` add named
      # packages; `uv pip install -r req.txt`, `uv sync/lock/run`, and bare forms do not.
      case "$sub" in
        add) MATCH="uv $(first_positional ${args[@]+"${args[@]}"})"; return 0 ;;
        pip|tool)
          if [ "${args[0]:-}" = "install" ]; then
            local -a rest=("${args[@]:1}")
            if [ "$sub" = "pip" ]; then
              p="$(first_pip_target ${rest[@]+"${rest[@]}"})"
            else
              p="$(first_positional ${rest[@]+"${rest[@]}"})"
            fi
            [ -n "$p" ] && { MATCH="uv $p"; return 0; }
          fi ;;
      esac
      ;;
    poetry)
      [ "$sub" = "add" ] && { MATCH="poetry $(first_positional ${args[@]+"${args[@]}"})"; return 0; }
      ;;
    pipx)
      [ "$sub" = "install" ] && { MATCH="pipx $(first_positional ${args[@]+"${args[@]}"})"; return 0; }
      ;;
    deno)
      # `deno add <pkg>` / `deno install <pkg>` add packages; bare `deno install`
      # (project deps) does not.
      case "$sub" in
        add|install)
          p="$(first_positional ${args[@]+"${args[@]}"})"
          [ -n "$p" ] && { MATCH="deno $p"; return 0; } ;;
      esac
      ;;
  esac
  return 1
}

# Normalize for detection only (we inspect, never execute this): strip quote chars
# so a quoted manager token (`"npm"`) is seen, and unwrap a `bash -c` / `sh -lc`
# wrapper so a nested install is seen. This gate is a speed-bump for the agent, not
# a sandbox against a determined adversary.
norm="$(printf '%s' "$cmd" | sed "s/[\"']//g")"
norm="$(printf '%s' "$norm" | sed -E 's/(^|[;&|])[[:space:]]*(sudo[[:space:]]+)?(bash|sh|zsh)[[:space:]]+-[a-z]*c[a-z]*[[:space:]]+/\1 /g')"
# Split the command on shell separators (&&, ||, ;, |, &, newline) and scan each.
segments="$(awk '{ gsub(/&&|\|\||[;|&]/, "\n"); print }' <<< "$norm")"
while IFS= read -r seg; do
  [ -n "$seg" ] || continue
  scan_segment "$seg" && break
done <<< "$segments"

if [ -n "${CLAUDE_GATE_DRYRUN:-}" ]; then
  [ -n "$MATCH" ] && echo "dependency-gate[dryrun]: WOULD GATE — $MATCH" >&2 \
                  || echo "dependency-gate[dryrun]: would allow" >&2
  exit 0
fi

if [ -n "$MATCH" ]; then
  mgr="${MATCH%% *}"; pkg="${MATCH#* }"
  {
    echo "dependency-gate: BLOCKED — agent-initiated dependency install detected."
    echo "  $mgr  →  ${pkg:-<unspecified>}"
    echo
    echo "Vet before adding (slopsquatting: ~1 in 5 LLM-suggested packages don't"
    echo "exist, and attackers pre-register the hallucinated names):"
    echo "  - confirm it exists and is the intended, canonical package;"
    echo "  - check author / downloads / source repo; then pin the version (by hash)."
    echo
    echo "Have a human approve it, or bypass with CLAUDE_SKIP_DEP_GATE=1."
  } >&2
  exit 2
fi

exit 0
