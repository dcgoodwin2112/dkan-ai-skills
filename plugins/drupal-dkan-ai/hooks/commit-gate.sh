#!/usr/bin/env bash
#
# commit-gate.sh — deterministic local quality gate for `git commit`.
#
# Shipped by the drupal-dkan-ai plugin as a PreToolUse(Bash) hook. Before a
# commit it runs phpcs + the unit suite (via DDEV) for every Drupal module the
# commit touches and BLOCKS the commit (exit 2) on failure. CI remains the
# authoritative gate; this is fast local feedback that closes the loop before
# code leaves the machine.
#
# Plugin hooks fire for every Bash call in every project, so this script is
# SELF-SCOPING: it exits 0 (no-op) unless the commit is in a DDEV-backed git repo
# and touches files under a module carrying phpcs.xml.dist and/or phpunit.xml.
# Kernel/integration tests are left to CI (slow, DB-bound).
#
# Scope is derived from the files being committed (git diff --cached, plus the
# tracked working set when -a/--all is used), each mapped to its enclosing module
# — so it works whether the module is the repo root or a subdirectory of a larger
# site/monorepo.
#
# Policy: gates `git commit` (including --amend and -a); warns-but-allows when
# DDEV is down (infra never hard-blocks); bypass an intentional WIP commit with
# CLAUDE_SKIP_COMMIT_GATE=1; preview scope with CLAUDE_GATE_DRYRUN=1; trace with
# CLAUDE_GATE_DEBUG=1.
#
# Contract: hook payload arrives as JSON on stdin; exit 0 = allow, exit 2 = block
# (stderr is shown to the agent). Requires git + jq; fails open if either is
# absent. Container paths are passed to the shell as positional args, never
# interpolated into a command string.

set -uo pipefail

dbg() { [ -n "${CLAUDE_GATE_DEBUG:-}" ] && echo "commit-gate[dbg]: $*" >&2 || true; }

input="$(cat)"
command -v jq >/dev/null 2>&1 || { dbg "jq missing; fail open"; exit 0; }
command -v git >/dev/null 2>&1 || { dbg "git missing; fail open"; exit 0; }

cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // empty')"
cwd="$(printf '%s' "$input" | jq -r '.cwd // empty')"
[ -n "$cmd" ] || exit 0

# Gate only `git [global-opts] commit ...`. Allows -C/-c/--flags before the
# subcommand; ignores `git log --grep commit`, `git status`, and `commit` as a
# message substring (those have a non-option token before `commit`).
re_detect='(^|[^[:alnum:]_])git([[:space:]]+(-C[[:space:]]+[^[:space:]]+|-c[[:space:]]+[^[:space:]]+|-{1,2}[^[:space:]]+))*[[:space:]]+commit([[:space:]]|$)'
printf '%s' "$cmd" | grep -Eq "$re_detect" || exit 0
dbg "git commit detected"

[ "${CLAUDE_SKIP_COMMIT_GATE:-}" = "1" ] && { echo "commit-gate: bypassed (CLAUDE_SKIP_COMMIT_GATE=1)." >&2; exit 0; }

# Resolve a starting directory without splitting on the literal 'commit' substring
# (a path or message may contain it): a global `git -C <dir>` (the -C immediately
# follows git, so a `commit -C <ref>` reuse-message flag is not matched), else a
# leading `cd <dir>` anchored at the command start, else the tool cwd.
start="$cwd"
re_gitc='(^|[^[:alnum:]_])git[[:space:]]+-C[[:space:]]+([^[:space:];&|]+)'
re_cd='^[[:space:]]*cd[[:space:]]+([^[:space:];&|]+)'
if [[ "$cmd" =~ $re_gitc ]]; then
  start="${BASH_REMATCH[2]}"
elif [[ "$cmd" =~ $re_cd ]]; then
  start="${BASH_REMATCH[1]}"
fi
start="${start%\'}"; start="${start#\'}"; start="${start%\"}"; start="${start#\"}"
case "$start" in /*) : ;; *) start="${cwd:-$PWD}/$start" ;; esac
start="$(cd "$start" 2>/dev/null && pwd -P)" || { dbg "start not a dir; fail open"; exit 0; }

repo="$(git -C "$start" rev-parse --show-toplevel 2>/dev/null)" || { dbg "not a git repo; not ours"; exit 0; }
[ -n "$repo" ] || exit 0
dbg "repo=$repo"

# Enclosing DDEV project (walk up for .ddev/config.yaml).
ddev_root=""; d="$repo"
while [ -n "$d" ] && [ "$d" != "/" ]; do
  [ -f "$d/.ddev/config.yaml" ] && { ddev_root="$d"; break; }
  d="$(dirname "$d")"
done
[ -n "$ddev_root" ] || { dbg "no DDEV project; not ours"; exit 0; }

# Files about to be committed: staged, plus tracked-modified when -a/--all is used
# (those get staged by `git commit -a` itself, so are not yet in the index here).
changed="$(git -C "$repo" diff --cached --name-only 2>/dev/null)"
if printf '%s' "$cmd" | grep -Eq '(^|[[:space:]])-[A-Za-z]*a[A-Za-z]*([[:space:]]|$)|[[:space:]]--all([[:space:]]|$)'; then
  changed="$changed
$(git -C "$repo" diff --name-only 2>/dev/null)"
fi
changed="$(printf '%s\n' "$changed" | sed '/^[[:space:]]*$/d' | sort -u)"
[ -n "$changed" ] || { dbg "no changed files; nothing to gate"; exit 0; }

# Map each changed file to its gate root: the CLOSEST (deepest) ancestor dir within
# the repo carrying phpcs.xml.dist and/or phpunit.xml. Module-is-repo-root resolves
# to the repo; a site/monorepo or nested module resolves to the owning module dir.
gate_roots=""
while IFS= read -r f; do
  [ -n "$f" ] || continue
  acc="$repo"
  found=""
  { [ -f "$acc/phpcs.xml.dist" ] || [ -f "$acc/phpunit.xml" ]; } && found="$acc"
  rest="$(dirname "$f")"
  case "$rest" in .|/) rest="" ;; esac
  if [ -n "$rest" ]; then
    IFS='/' read -ra parts <<< "$rest"
    for p in ${parts[@]+"${parts[@]}"}; do
      acc="$acc/$p"
      { [ -f "$acc/phpcs.xml.dist" ] || [ -f "$acc/phpunit.xml" ]; } && found="$acc"
    done
  fi
  [ -n "$found" ] && gate_roots="$gate_roots
$found"
done <<< "$changed"
gate_roots="$(printf '%s\n' "$gate_roots" | sed '/^[[:space:]]*$/d' | sort -u)"
[ -n "$gate_roots" ] || { dbg "no gated module touched"; exit 0; }
dbg "gate_roots: $(printf '%s' "$gate_roots" | tr '\n' ' ')"

# Preview: report scope without invoking DDEV or the gates.
if [ -n "${CLAUDE_GATE_DRYRUN:-}" ]; then
  echo "commit-gate[dryrun]: would gate (DDEV at $ddev_root):" >&2
  while IFS= read -r g; do [ -n "$g" ] && echo "  - ${g#"$ddev_root"/}" >&2; done <<< "$gate_roots"
  exit 0
fi

command -v ddev >/dev/null 2>&1 || { echo "commit-gate: ddev not on PATH; skipping local gate (CI enforces)." >&2; exit 0; }
if ! ( cd "$ddev_root" && ddev exec true </dev/null >/dev/null 2>&1 ); then
  echo "commit-gate: DDEV at $ddev_root is not running; skipping local gate (run 'ddev start'; CI enforces)." >&2
  exit 0
fi

bin="/var/www/html/vendor/bin"
# Wrap a string in single quotes, escaping embedded quotes, for safe interpolation
# into the container command (a path cannot break out of the quotes or inject).
shq() { local s=$1; s=${s//\'/\'\\\'\'}; printf "'%s'" "$s"; }
fail=0; summary=""
run_gate() {  # label, container-dir, container-command (binary + fixed args)
  local label="$1" cdir="$2" cmdline="$3" out
  if out="$( cd "$ddev_root" && ddev exec bash -c "cd $(shq "$cdir") && $cmdline" </dev/null 2>&1 )"; then
    dbg "$label passed"; return 0
  fi
  fail=1
  summary="${summary}
--- ${label} failed ---
$(printf '%s\n' "$out" | tail -n 25)"
}

while IFS= read -r g; do
  [ -n "$g" ] || continue
  if [ "$g" = "$ddev_root" ]; then
    rel="."; cdir="/var/www/html"
  else
    rel="${g#"$ddev_root"/}"; cdir="/var/www/html/$rel"
  fi
  [ -f "$g/phpcs.xml.dist" ] && run_gate "phpcs ($rel)"        "$cdir" "$bin/phpcs --standard=phpcs.xml.dist ."
  [ -f "$g/phpunit.xml" ]    && run_gate "phpunit unit ($rel)" "$cdir" "$bin/phpunit -c phpunit.xml"
done <<< "$gate_roots"

if [ "$fail" = 1 ]; then
  {
    echo "commit-gate: BLOCKED — local quality gate failed."
    echo "$summary"
    echo
    echo "Fix the issues above, or bypass an intentional WIP commit with CLAUDE_SKIP_COMMIT_GATE=1."
  } >&2
  exit 2
fi

echo "commit-gate: passed." >&2
exit 0
