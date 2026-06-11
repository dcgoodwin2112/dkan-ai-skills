# Evals

How `dkan-ai-skills` measures whether the skills work, and how to reproduce it. The
harness lives in `evals/`; the runner is `bin/eval`.

Four evals, two roles:

| eval | asks | role | command | needs |
|---|---|---|---|---|
| **triggering** | does a skill's `description` attract the model for the right prompts (and not sibling near-misses)? | enforced gate | `bin/eval trigger [skill]` | authenticated `claude` |
| **task outcome** | does the packaged skill beat a no-skill baseline on real DKAN/Drupal tasks? | evidence artifact | `bin/eval task` | `python3` (regrade); in-session (fresh runs) |
| **scaffold correctness** | do the scaffold commands' code templates stay spec-conformant? | enforced gate | `bin/eval scaffolds` | `python3` (+ optional phpcs) |
| **live currency** | do the docs' factual claims about the DKAN/MCP surface match a running DKAN site? | enforced gate (env-gated) | `bin/eval live` | `python3` + a running DKAN site (DDEV); SKIPs cleanly if unconfigured |

**Gate vs. artifact.** The enforced, automatable gates are **triggering**,
**scaffold-correctness**, and (where a dev site exists) **live currency** — cheap, stable,
deterministic. The **task-outcome** benchmark is a *reported evidence/demo artifact*: 3 binary
runs/arm is too coarse to gate on, so it is regenerated on demand, not enforced.

Each eval has a detailed report next to its data — read those for method and results:
`evals/triggering/REPORT.md`, `evals/tasks/REPORT.md`, `evals/scaffolds/REPORT.md`.

## Run

### `bin/eval trigger [skill]`
Spawns `claude -p` per query against an **isolated temp project root**, detecting whether the
named skill's description attracts a `Skill`/`Read` call. Per-skill sets are derived from
`evals/triggering/routing.json`. **Auth:** needs a logged-in `claude` or `ANTHROPIC_API_KEY`.
Knobs: `EVAL_RUNS`, `EVAL_WORKERS`, `EVAL_TIMEOUT`, `EVAL_MODEL`. Aggregate per-skill outputs into
a committable snapshot (`results/run_eval_summary.json`) with `evals/lib/aggregate_trigger.py`; the
in-session complement is `results/judge_routing.json`. No snapshot is committed yet — a 2026-06-08
in-session run (1 run/query) showed near-zero positive triggering, indistinguishable from a harness
artifact (when nothing fires, near-miss resistance passes for free); validate detection on obvious
positives with `EVAL_RUNS=3` from a normal terminal before committing numbers.

**Running from inside a Claude Code session** (e.g. an agent turn) needs two workarounds:
- Nested `claude -p` returns HTTP 401 because the session injects `ANTHROPIC_BASE_URL` and
  host-managed OAuth isn't visible to child processes — clear it: `env -u ANTHROPIC_BASE_URL bin/eval trigger`.
- Temporarily disable the globally-installed plugin (`claude plugin disable drupal-dkan-ai@dkan-ai-skills`,
  re-enable after) so its real skills don't out-compete run_eval's synthetic per-skill command and
  depress the measured rate.

### `bin/eval task`
Regrades the recorded paired runs (`evals/tasks/runs/raw_runs.json`) with the deterministic
grader and regenerates the static demo: `benchmark.json` + `benchmark.html`. **No auth, no
model** — fully reproducible. To collect **fresh** runs: in-session, run the paired subagents
over `evals/tasks/tasks.json` (with-skill reads the named skill's docs; baseline answers from
parametric knowledge only — same model both arms), record verbatim into `raw_runs.json`, then
`bin/eval task`.

### `bin/eval scaffolds`
Deterministic gate over each scaffold command's embedded templates (required attribute / base
class / method signatures / version-gate present; fabricated forms absent). **No deps, no
auth.** Optionally lints **real generated output** with phpcs where a Drupal/DDEV env exists:
set `EVAL_PHPCS` (e.g. `"ddev exec vendor/bin/phpcs"`) and `EVAL_SCAFFOLD_OUTPUT_DIR`; absent
either, the phpcs layer skips cleanly and the structural gate still runs.

### `bin/eval live`
Verifies skill-doc claims (tool surface, metastore schemas, auth posture) against a **running**
DKAN dev site over MCP stdio (`ddev drush dkan-mcp-server:serve`, read-only `tools/call`; the
writer connection is `tools/list` only) plus three curl probes, and greps the docs for stale
claim text. **No LLM, no tokens, no nested `claude -p`** — unlike the trigger eval it runs fine
inside a Claude Code session. Set `EVAL_DKAN_SITE_DIR` (DDEV checkout; unset → clean SKIP,
exit 0) and optionally `EVAL_DKAN_BASIC_PROBE="user:pass"` for the Basic-rejected probes;
overrides for non-DDEV setups: `EVAL_DKAN_MCP_CMD_RO/_RW`, `EVAL_DKAN_SITE_URL`,
`EVAL_DKAN_MCP_HTTP_PATH`. Exit: 0 pass/SKIP, 1 gate failure, 2 configured-but-unreachable.

## What the numbers do / don't claim

- **triggering** is a **description-attraction proxy**, not production auto-load, and is
  partially circular (the labels and the judge complement share the descriptions). Real
  auto-load arbitration across 7 siblings is approximated by sibling-domain negatives.
- **task outcome** measures the **packaged skill end-to-end vs. nothing**, in-session (the
  with-skill arm *reads* the docs) — not auto-load, and 3 binary runs/arm is coarse.
- **scaffold correctness** is a **golden/regression gate** on the shipped templates, not proof
  of world-correctness — phpcs lint and the commands' own runtime-discovery steps own that.
- **live currency** checks claims against **one pinned dev site** (dkan-site DDEV,
  `dkan_mcp_server` 1.0.x), not upstream truth — `/check-skill-currency` owns docs-vs-upstream
  drift; this gate owns docs-vs-running-system drift. Its counts legitimately move as the
  module evolves; that drift is the signal.

## Add an eval

- **triggering** — add queries to `evals/triggering/routing.json` (`expected_skill`,
  `near_miss_for`); `bin/eval trigger` rebuilds the per-skill sets.
- **task** — add a task to `evals/tasks/tasks.json` with ≥1 DKAN-specific `assert_pos` and, where
  apt, an `assert_neg` for a known hallucination; calibrate (below); collect runs; `bin/eval task`.
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

`trigger` and fresh `task` runs spend tokens + time (`claude -p` / subagents) — keep the corpus
small (≤12 tasks × 3 runs; ~100 trigger queries) and report spend. `task` regrade, the viewer,
and the `scaffolds` and `live` gates are **free** (no model).

## Provenance

Each eval records date, `claude` CLI version, model, and runs in its results JSON. The vendored
`run_eval.py` pins its skill-creator source — see `evals/lib/PROVENANCE.md`.

## CI

- **scaffold gate** — run on every change (no deps).
- **triggering gate** — run on description changes (cheap); needs `ANTHROPIC_API_KEY`.
- **task benchmark** — on demand only (coarse; not a gate).
- **live gate** — skipped in CI (needs a running DDEV site); run locally before/after touching
  the `drupal-mcp-server`, `open-data-dcat`, or `dkan-module-author` reference docs.

## Live demo

`demo/before-after.sh ["question"]` — asks one question with and without the skill and prints
the answers labeled side by side. A presentation aid, separate from the measurement path.
