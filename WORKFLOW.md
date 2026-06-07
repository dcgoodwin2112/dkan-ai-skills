# Rapid Development Workflow

A disciplined-but-fast loop for AI-assisted development: the agent does the work,
you steer at a few decision gates, and quality gates compound so each step is
cheap to verify. Written framework-neutral; the running example throughout is the
DKAN MCP module work (`dkan_mcp_server`), built and hardened with this process.
Drupal/DKAN-specific bits are marked **Example** — swap them for your stack.

## Principles

- **The agent executes; the human decides.** Automate the typing; reserve human
  attention for scope, sequencing, and risk calls.
- **Gates compound.** Order work so each phase runs on top of the previous one's
  guarantees (lint-clean before CI gates on lint; security before CI runs the
  suite; correctness before performance).
- **Everything portable.** Domain knowledge, procedures, and norms live in
  versioned, auto-loading tooling — not in one session's memory — so any project
  or agent starts from the same baseline.
- **Cheap verification beats trust.** Local lint/test gates, an independent plan
  review, an independent diff review, and an adversarial pass when confidence is
  low — each catches a different class of error before it ships.

## The loop at a glance

1. **Baseline** — measure the current state empirically; date it.
2. **Plan** — write a phased plan doc (goal, scope fence, sequencing, per-phase
   "Done when", open decisions).
3. **Review the plan** — independent reviewer (codex `review_plan`); fold findings
   back in *before* writing code.
4. **Per phase** — branch → scaffold/implement → local gates → independent diff
   review → adversarial review if low-confidence → PR → merge → cleanup.
5. **Refine docs** — drive doc reconciliation to a measurable end-state with
   `/goal`.
6. **Maintain** — currency checks + CI drift detection keep the toolkit and the
   dependency pins honest.

Steps 2–4 pause for you between phases; nothing commits until you ask.

---

## 1. The reusable toolkit layer

Capture domain knowledge and repeatable procedures once, as versioned tooling that
auto-loads every session — so the agent never re-derives the same context and every
project starts equal.

**Example — the `dkan-ai-skills` Claude Code plugin:**

- **Skills** (`plugins/drupal-dkan-ai/skills/*/SKILL.md`): auto-load by
  `description` when a task matches (editing a `*.services.yml`, working in
  `Drupal\dkan_*`). Each is decision support + curated `reference/` docs, not a
  tutorial dump.
- **Slash commands** (`commands/*.md`): two kinds — *scaffolding*
  (`/scaffold-dkan-module`, `/mcp-scaffold-tool`, `/ai-scaffold-*`) that emit
  correct skeletons, and *validation* (`/validate-module`) that runs the gates.
- **Cross-tool adapters**: `bin/build-adapters` regenerates `AGENTS.md` +
  `.github/` (Copilot/Codex/Cursor) from the canonical skills; `bin/test` fails if
  they drift. Knowledge is single-sourced; every agent reads the same facts.
- **Currency maintenance**: `skills-currency.yml` pins every version-specific claim
  to an authoritative source with a cadence; `/check-skill-currency` verifies them
  and reports drift (report-only by default).

**Generic principle:** for any stack the equivalent is a small repo of (a)
decision-support docs keyed to file globs/namespaces, (b) scaffolding procedures,
(c) an adapter-regeneration step if you target multiple agents, (d) a currency
manifest for fast-moving facts.

## 2. The per-repo operational contract

Each repo carries a short agent-facing contract so the process is identical no
matter who — or which agent — picks it up.

- **`AGENTS.md` / `CLAUDE.md`**: what the thing is, the exact build/test/lint
  commands, code style, gotchas, and working norms (commit only when asked, branch
  off `main`, decline accepted-style nits). Points to the doc spine, doesn't
  restate it.
- **Tracked doc spine**: `README` (what / how to use), `ARCHITECTURE` (design +
  full inventory), `ROADMAP` (deferred / blocked / upstream). Three docs, distinct
  jobs, no overlap.
- **Untracked-scratch allowlist**: planning/scratch docs stay local. **Example:**
  `docs/.gitignore` tracks only `ARCHITECTURE.md`, `ROADMAP.md`, `.gitignore`;
  every plan doc is untracked history. Deferred work graduates from a plan into the
  tracked `ROADMAP`.

## 3. Plan from an empirical baseline

Never plan from assumptions. First measure: what passes, what fails, what exists,
counts, versions — and **date it** ("verified 2026-06-04"). The plan cites measured
facts, not guesses.

**Example baseline lines:** "`src/` is phpcs-clean except 1 error + 3 line-length
warnings"; "38 tools (25 read / 13 write)"; "`require` pins `drupal/dkan:4.x-dev`,
`mcp/sdk:dev-main#<sha>`". Those numbers drive the plan and later become test
assertions.

## 4. Write a phased plan doc

One markdown doc, untracked, with a fixed shape:

- **Goal + scope fence** — one sentence of intent, then an explicit non-goal
  ("**No new features.**").
- **Baseline** (§3).
- **Sequencing rationale** — why this order; which phases are in your control vs.
  blocked on upstream/decisions.
- **Phases** — each tagged `[category, size, risk]`, numbered steps, and an
  explicit **"Done when:"** acceptance line. A phase with no crisp done-condition
  isn't ready to start.
- **Cross-cutting** — branch/PR/commit norms that apply to every phase.
- **Decisions for the user** — open questions you can't resolve in code, each with
  a recommendation.

Draft and present it in **plan mode**. **Pause after approval** — don't start
editing; let the human review context, adjust effort, or redirect first.

## 5. Review the plan independently

Before any code, run the plan through an independent reviewer — the codex-reviewer
MCP, `review_plan`. It catches sequencing errors, missing risks, and scope creep
while they're still free to fix. Fold validated findings back into the plan doc
(track that as its own step).

This is the highest-leverage review in the loop: a flaw caught here costs one doc
edit; the same flaw caught after implementation costs a whole phase.

## 6. Break work into scoped phases

- **One phase = one focused branch = one PR.** Small enough to review in one
  sitting.
- **Sequenced so gates compound** (see Principles).
- **Risk-tagged**, so high-risk phases (security, destructive ops, auth) are known
  up front to warrant the adversarial pass (§9).
- **ROADMAP absorbs anything cut** — scope creep goes to the backlog with
  rationale, not into the current PR.
- **Pause between phases.** The human chooses when the next one starts.

**Example sequence:** 0 lint-clean → 1 security hardening → 2 CI + drift detection
→ 3 performance → 4 packaging polish → 5 release/migration (decision-gated). Each
shipped as its own branch + PR.

## 7. Execute a phase

- Scaffold with the toolkit commands; follow the repo's code style (from the
  contract, §2).
- **Run the local gates before any review.** **Example (no PHP on host → via
  DDEV):** phpcs `Drupal,DrupalPractice`; the unit suite; the kernel suite against
  the test DB. `/validate-module` bundles lint + tests + permission audit + cache
  rebuild.
- **Make the must-run gates deterministic with a hook.** Advisory instructions
  get skipped; a hook does not (Anthropic's verification ladder — *CLAUDE.md is
  advisory, hooks are deterministic*). A `PreToolUse` hook on `git commit` that
  runs the fast gates (lint + unit) and blocks on failure turns "should run" into
  "always runs." Keep slow/integration checks (kernel, full matrix) in CI — the
  hook is fast local feedback; **CI stays authoritative.** This plugin ships such a
  gate (`hooks/commit-gate.sh`): it self-scopes to DDEV-backed modules and
  warns-but-allows when DDEV is down.
- Keep the change focused. When you spot an out-of-scope issue, **capture it** (a
  background-task chip, or a ROADMAP line) instead of widening the PR.
- At a genuine fork, **ask** (AskUserQuestion) rather than guessing. **Example:**
  "soften the hard `basic_auth` dependency, or keep it?" — a one-question fork that
  changed the phase's design.

## 8. Review the diff independently

Run the codex-reviewer `review_diff` before each PR — `general` profile always,
`security` profile for anything touching auth, access, or destructive ops.

- **Verify the diff against the plan, not just for bugs.** Confirm *every* plan
  requirement landed and nothing out of scope crept in — codex `plan_vs_diff`,
  and/or the bundled `plan-diff-reviewer` subagent (a fresh-context Claude reviewer
  handed only the diff + the plan, reporting requirement gaps, not style). The
  built-in `/code-review` is a separate, optional in-session correctness + cleanup
  pass.
- **Gotcha:** new/untracked files aren't in the `working` diff. `git add` them and
  review in `staged` mode, or they're silently skipped.
- **Integrate validated findings; decline noise with a recorded rationale.**
  **Example:** em-dash "fixes" are declined (accepted project style); a render-array
  nit was declined because the string form matches Drupal core's own convention.
- Re-review until `approve` / `approve_with_nits`.

## 9. Adversarial review in Claude when confidence is low

An independent reviewer is one opinion. When a finding is **low-confidence**, or
the change is **high-risk**, add a second, adversarial pass inside Claude:

- **Independent skeptics** — subagents prompted to *refute* the change; a
  majority-refute kills it.
- **Perspective-diverse lenses** — give each reviewer a distinct angle
  (correctness / security / does-it-actually-reproduce) so redundancy doesn't blind
  them all to the same miss.
- **Vary the model, not just the prompt.** Run the lenses under *different* models
  (e.g. one `opus`, one `sonnet` via the Agent tool's model option) and include the
  external codex reviewer — a different model family — so no single model's blind
  spots dominate the panel (the agent-as-judge / CollabEval finding). The bundled
  `plan-diff-reviewer` (§8) is a reusable fresh-context panelist.
- **Escalate by risk:** a typo fix needs none; a destructive-write authorization
  path warrants 3–5 lenses.

**Example — the catch this surfaced:** softening the `basic_auth` dependency updated
the route subscriber, but a *second* subscriber still keyed off the old flag, so an
inert-config install would have lost OAuth discovery. A single reviewer flagged it
at low confidence; the adversarial pass confirmed it was real before it shipped.

## 10. Commit, PR, and merge hygiene

- **Commit only when asked**; if on `main`, branch first.
- **The commit-gate hook (§7) enforces the gates here:** a failing lint/unit check
  blocks the commit itself (bypass an intentional WIP with
  `CLAUDE_SKIP_COMMIT_GATE=1`); CI re-runs the full suite as the authoritative gate.
- Commit messages: concise, no hype; trailer `Co-Authored-By: ...`. PR body ends
  with the generated-with line.
- **After merge, clean up:** `git checkout main && git pull --ff-only`, delete the
  merged local branch, `git fetch --prune`. Leaves only `main`, working tree clean,
  ready for the next phase.

## 11. Refine docs and clean up with `/goal`

When the feature work lands, the docs have drifted. Use the built-in **`/goal`**
command — set a completion condition and Claude works across turns until it's met —
to drive reconciliation to a *measurable* end-state, not a vague "tidy the docs."

**Example goal:** "Every tracked doc (README / ARCHITECTURE / ROADMAP) is accurate
to the merged code, cross-referenced with no duplication, free of stale
counts/versions, and the docs allowlist is respected." `/goal` keeps iterating —
edit, re-check, repeat — until that holds.

This pairs with the doc spine (§2): the goal's success criteria *are* "each of the
three docs does its one job correctly."

## 12. Maintain

The loop doesn't end at merge — two things rot over time:

- **Toolkit currency**: run `/check-skill-currency` (optionally on a schedule) to
  verify pinned version facts against upstream and report drift before it misleads.
- **Dependency drift**: when you ride dev branches/pins, add a CI job that bumps to
  upstream HEAD and runs **contract tests** — assert the consumed upstream symbols
  still exist, instantiate every plugin. It goes red the moment upstream breaks you,
  turning silent breakage into an early signal. **Example:** the `mcp_server` /
  `mcp/sdk` pin-bump job + `UpstreamContractTest` + `ToolDiscoveryTest`.
- **ROADMAP** is the living deferral log: anything cut from a phase lives here with
  rationale until it's scheduled.

---

## Generalizing to another project

The loop is framework-neutral; only the toolkit and the gate commands change.

1. **Toolkit** — a skills/commands repo for your stack: decision-support docs keyed
   to file globs, scaffolding procedures, a currency manifest, adapter regeneration
   if you target multiple agents.
2. **Contract** — an `AGENTS.md` per repo: build/test/lint commands, style, norms,
   and a three-doc spine (README / ARCHITECTURE / ROADMAP) with an untracked-scratch
   allowlist.
3. **Baseline → plan → review-plan** — measure and date; phased plan doc with "Done
   when" gates and a decisions section; independent plan review before code.
4. **Per phase** — branch → scaffold → **local gates** → independent diff review →
   adversarial pass if low-confidence/high-risk → PR → merge → cleanup.
5. **`/goal` doc cleanup** — reconcile docs to a measurable end-state.
6. **Maintain** — currency + CI drift detection + ROADMAP.

**Universal vs. stack-specific:** the sequence, the review gates, the pause cadence,
and the doc discipline are universal. Only the gate *commands* (phpcs/phpunit via
DDEV here), the scaffolds, and the currency sources are Drupal/DKAN-specific — swap
them for your stack's linter, test runner, and scaffolds.
