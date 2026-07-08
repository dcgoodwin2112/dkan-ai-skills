# Evals

How `dkan-ai-skills` measures whether the skills work, and how to reproduce it. The
harness lives in `evals/`; the runner is `bin/eval`.

Three evals, two roles:

| eval | asks | role | command | needs |
|---|---|---|---|---|
| **task outcome** | does the packaged skill beat a no-skill baseline on real DKAN/Drupal tasks? | evidence artifact | `bin/eval task` | `python3` (regrade); in-session (fresh runs) |
| **scaffold correctness** | do the scaffold commands' code templates stay spec-conformant? | enforced gate | `bin/eval scaffolds` | `python3` (+ optional phpcs) |
| **live currency** | do the docs' factual claims about the DKAN/MCP surface match a running DKAN site? | enforced gate (env-gated) | `bin/eval live` | `python3` + a running DKAN site (DDEV); SKIPs cleanly if unconfigured |

**Gate vs. artifact.** The enforced, automatable gates are **scaffold-correctness** and
(where a dev site exists) **live currency** — cheap, stable, deterministic. The
**task-outcome** benchmark is a *reported evidence/demo artifact*: 3 binary runs/arm is
too coarse to gate on, so it is regenerated on demand, not enforced.

Each eval has a detailed report next to its data — read those for method and results:
`evals/tasks/REPORT.md`, `evals/scaffolds/REPORT.md`, `evals/live/REPORT.md`.

**Removed (2026-06-12): the triggering eval.** It tested description attraction via
synthetic per-skill command files spawned through `claude -p`, never produced a valid
committed number, and by design required disabling the installed plugin to run. If
routing measurement is ever wanted again, rebuild it on `claude -p --bare --plugin-dir`
(hermetic, no plugin disabling); the 100-query routing corpus
(`evals/triggering/routing.json`) is in git history. **Preferred path if ever rebuilt:**
don't — promptfoo's Claude Agent SDK provider ships a first-class `skill-used` assertion
for exactly this (deterministic trigger verification, actively maintained); adopting it
beats maintaining a bespoke harness for the fastest-rotting eval layer.

## Run

### `bin/eval task`
Regrades the recorded paired runs (`evals/tasks/runs/raw_runs.json`) with the deterministic
grader, producing `benchmark.json`. **No auth, no model** — fully reproducible. To collect
**fresh** runs: in-session, run the paired subagents over `evals/tasks/tasks.json`
(with-skill reads the named skill's docs; baseline answers from parametric knowledge only
— same model both arms), record verbatim into `raw_runs.json`, then `bin/eval task`.

### `bin/eval scaffolds`
Deterministic gate over each scaffold command's embedded templates (required attribute / base
class / method signatures / version-gate present; fabricated forms absent). **No deps, no
auth.** Optionally lints **real generated output** with phpcs where a Drupal/DDEV env exists:
set `EVAL_PHPCS` (e.g. `"ddev exec vendor/bin/phpcs"`) and `EVAL_SCAFFOLD_OUTPUT_DIR`; absent
either, the phpcs layer skips cleanly and the structural gate still runs.

### `bin/eval live`
Verifies skill-doc claims (tool surface, metastore schemas, auth posture) against a **running**
DKAN dev site over MCP stdio (`ddev drush dkan-mcp-server:serve`, read-only `tools/call`; the
writer connection is `tools/list` only) plus two curl probes, and greps the docs for stale
claim text. **No LLM, no tokens, no nested `claude -p`** — unlike the trigger eval it runs fine
inside a Claude Code session. Set `EVAL_DKAN_SITE_DIR` (DDEV checkout; unset → clean SKIP,
exit 0); overrides for non-DDEV setups: `EVAL_DKAN_MCP_CMD_RO/_RW`, `EVAL_DKAN_SITE_URL`,
`EVAL_DKAN_MCP_HTTP_PATH`. Exit: 0 pass/SKIP, 1 gate failure, 2 configured-but-unreachable.
`results.json` is **untracked** (volatile local snapshot); the dated summary in
`evals/live/REPORT.md` is the committed record — update it when a run changes the outcome.

## What the numbers do / don't claim

- **task outcome** measures the **packaged skill end-to-end vs. nothing**, in-session (the
  with-skill arm *reads* the docs) — not auto-load, and 3 binary runs/arm is coarse.
- **scaffold correctness** is a **golden/regression gate** on the shipped templates, not proof
  of world-correctness — phpcs lint and the commands' own runtime-discovery steps own that.
- **live currency** checks claims against **one pinned dev site** (dkan-site DDEV,
  `dkan_mcp_server` 1.0.x), not upstream truth — `/check-skill-currency` owns docs-vs-upstream
  drift; this gate owns docs-vs-running-system drift. Its counts legitimately move as the
  module evolves; that drift is the signal.

## Add an eval

- **task** — **failure-driven only:** add a task when a real session produces a wrong answer a
  skill should have prevented — that failure becomes the task, the correct answer its
  `assert_pos`, the observed wrong answer its `assert_neg`. No speculative tasks. Add to
  `evals/tasks/tasks.json` with ≥1 DKAN-specific `assert_pos`; calibrate (below); collect runs;
  `bin/eval task`.
- **scaffold** — add a command's assertions to `evals/scaffolds/checks.json`: `assert_pos`
  required forms, `assert_neg` fabricated forms (always `code`-scoped) each with a `neg_example`.
- **live** — add a check to `evals/live/checks.json`: pick a probe + extract path + op, pin
  `expected` to the verified live value, set `doc_ref`; doc `must_not_match` tripwires require
  a `neg_example`.

## Calibration & discrimination

Grading is **deterministic string/regex** (no LLM judge), so there is no judge to calibrate —
the discipline is making assertions *discriminate*:

- **task** — confirm each `assert_pos` matches a correct answer and that the assertion actually
  **fails the baseline on ≥1 run**; drop non-discriminating assertions (they inflate both arms).
- **scaffold** — every `assert_neg` carries a `neg_example`; the checker **fails the gate** if a
  negative cannot match its own example, so a typo'd negative can't pass silently.
- **live** — same `neg_example` liveness rule for doc tripwires, plus: an extraction path that
  stops resolving is an **error that fails the gate** (never a silent pass), and
  `absent`/`subset`/`matches` reject empty extractions.

## Cost

Fresh `task` runs spend tokens + time (in-session subagents) — keep the corpus small
(≤12 tasks × 3 runs) and report spend. The `task` regrade and the `scaffolds` and `live`
gates are **free** (no model).

**Refresh policy:** regenerate fresh task runs only when the session model materially
changes (new family) or a skill under test is substantially rewritten — otherwise the
committed benchmark stands as dated evidence (provenance records CLI version + model).
Not calendar-driven.

## Provenance

Each eval records date, `claude` CLI version, model, and runs in its results JSON.

## CI

`.github/workflows/ci.yml` runs the free deterministic gates on every push/PR: `bin/test`,
the scaffold gate, a task-regrade determinism check (`bin/eval task` must reproduce the
committed `evals/tasks/` artifacts byte-for-byte), and the live gate's unconfigured-SKIP path.

Not in CI:

- **task benchmark** (fresh runs) — on demand only (coarse; not a gate). CI only checks the regrade.
- **live gate** (real run) — needs a running DDEV site; run locally before/after touching
  the `drupal-mcp-server`, `open-data-dcat`, or `dkan-module-author` reference docs.

## Live demo

`demo/before-after.sh ["question"]` — asks one question with and without the skill and prints
the answers labeled side by side. A presentation aid, separate from the measurement path.
