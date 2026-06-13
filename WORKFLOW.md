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
  or agent starts from the same baseline. New lessons flow *back* into that layer
  after each phase (§12), so the loop compounds instead of relearning.
- **Cheap verification beats trust.** Local lint/test gates, an independent plan
  review, an independent diff review, and an adversarial pass when confidence is
  low — each catches a different class of error before it ships. The review is the
  gate, not the reviewer: if the external reviewer is unavailable, warn and fall
  back to the in-Claude review (§8/§9), never skip.

## The loop at a glance

The sequence end to end. **Pause points for the human are called out; nothing
commits until you ask.** Calibrate depth to the change (see Right-size below).

1. **Baseline** — measure the current state empirically; date it.
2. **Plan** — write a phased plan doc (goal, scope fence, sequencing, per-phase
   "Done when", open decisions); present in plan mode, **pause after approval**.
3. **Review the plan** — independent reviewer (codex `review_plan`, or the in-Claude
   fallback if codex is down); fold findings back in *before* code.
4. **Per phase**, in order: `/clear` & re-seed from the plan → branch →
   scaffold/implement → **local gates** (lint + unit; eval if an AI surface) →
   independent diff review → adversarial pass if low-confidence/high-risk → commit
   (gate hook) → PR → merge → clean up → write learnings back. **Pause between
   phases.**
5. **Refine docs** — reconcile docs to a measurable end-state with `/goal`.
6. **Maintain** — currency checks, CI drift detection, MCP/AI-surface contract
   tests, and writing each phase's learnings back keep the toolkit compounding.

**Right-size the loop.** The full ladder has overhead; match gate depth to change
size. A typo or one-line fix skips the plan doc and phases (edit → local gates →
commit); a substantive or risky change earns the whole sequence. The pieces scale
independently — §9 already escalates the adversarial pass by risk; apply the same
judgment to planning and phasing. Prose-only doc changes take a lighter diff
review; **agent-facing content (skills, commands, reference docs) never does** —
there the facts are the product, and a wrong fact ships to every future session.
When unsure on something risky, over-gate.

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
  tracked `ROADMAP`. (Deliberate exception: a long-running effort can promote its
  plan to a tracked living `docs/PLAN.md` — see §4.)

## 3. Plan from an empirical baseline

Never plan from assumptions. First measure: what passes, what fails, what exists,
counts, versions — and **date it** ("verified 2026-06-04"). The plan cites measured
facts, not guesses.

**Example baseline lines:** "`src/` is phpcs-clean except 1 error + 3 line-length
warnings"; "38 tools (25 read / 13 write)"; "`require` pins `drupal/dkan:4.x-dev`,
`mcp/sdk:dev-main#<sha>`". Those numbers drive the plan and later become test
assertions.

Subagent and audit **findings are claims, not facts.** Before a finding drives a
deletion or rewrite, spot-check it against the primary source — a "high-confidence
duplication" finding that turns out to be correct progressive disclosure is one
verification away from being damage.

## 4. Write a phased plan doc

One markdown doc with a fixed shape. Two modes — pick by lifespan:

- **Untracked scratch plan** (the default; §2): single-session or short multi-phase
  work. Local history, never committed.
- **Tracked living plan** (`docs/PLAN.md`): work spanning many sessions and phases,
  cold-start handoffs, or an external maintainer in the merge loop. Structure and
  cadence below.

The fixed shape (both modes):

- **Goal + scope fence** — one sentence of intent, then an explicit non-goal
  ("**No new features.**").
- **Baseline** (§3).
- **Sequencing rationale** — why this order; which phases are in your control vs.
  blocked on upstream/decisions.
- **Phases** — each tagged `[category, size, risk]`, numbered steps, and an
  explicit **"Done when:"** acceptance line that **names its proof** — the tests
  and live checks that verify the phase (a `*Verify:*` list). A phase with no
  crisp done-condition isn't ready to start.
- **Cross-cutting** — branch/PR/commit norms that apply to every phase.
- **Decisions for the user** — open questions you can't resolve in code, each with
  a recommendation.

**Writing conventions** (both modes): durable identifiers over prose
("squash-merged as `b95d987` via MR !8", dataset UUIDs, pipeline numbers);
absolute dates; record *why* a deviation happened, not just what; deferred items
get a "Deferred / not scheduled" entry naming the action to take when picked up.
**Changing anything pinned by a test (check IDs, weights) requires updating doc
and test together — and the doc says so.**

**The living plan** splits labor with the §2 contract — state the rule in the plan
itself ("**Mechanics stay in AGENTS.md**") and never duplicate: `PLAN.md` records
context, decisions with rationale, architecture, phases, risks, and deferrals (the
things later phases must respect); `AGENTS.md` keeps day-to-day build mechanics
(commands, test ground rules, gotchas) plus a phase checklist and one
"Architecture (phase N slice)" section per phase. Below the phase list, append
chronological `## Phase N notes (date)` sections (decisions made while building,
then the live-verification record) and — when a fresh session will pick up the
work — a `## Phase N handoff (date)` (repo state, dev-site state, what to consume,
known gaps). Keep exactly one `## Current state (date, post-phase-N)` section that
is **rewritten, not appended**: stale claims are replaced ("MR !9 pending merge"
becomes "phase 8 squash-merged as `577e4bf` via MR !9"). Plan-only commits go
straight to the default branch and are pushed — no branch or MR for docs-only
planning changes.

Draft and present it in **plan mode**. **Pause after approval** — don't start
editing; let the human review context, adjust effort, or redirect first.

## 5. Review the plan independently

Before any code, run the plan through an independent reviewer — the codex-reviewer
MCP, `review_plan`. **Ask the zeroth question first:** have the reviewer weigh the
goal against the null alternatives — do nothing, delete the thing, reduce scope —
before critiquing the phases. The gates below verify a plan is *internally* sound;
only this question (and the human at the §4 pause) checks it's the *right* plan. A
fully-reviewed redesign plan once gave way to a one-PR demolition the moment
someone asked whether the thing should exist at all.

The review catches sequencing errors, missing risks, and scope creep while they're
still free to fix. Fold validated findings back into the plan doc (track that as
its own step). **If codex is unavailable**, say so and stand in the bundled
**`plan-reviewer`** subagent (`@agent-drupal-dkan-ai:plan-reviewer`) — a
fresh-context Claude reviewer handed the plan doc, reporting the same classes;
note the substitution in the plan doc rather than skip the gate. The fallback is
fresh-context but **same-model** — it shares the planner's blind spots, so treat
its approval as weaker than codex's and lean harder on the pause. (`/code-review`
reviews diffs, not plans, so it is not the stand-in here.)

**Scope the review to what's about to be built.** For a living plan, review the
*unbuilt phase*, not the whole document: codex `focus` on that phase's section,
`context_globs` pointing at the real code it touches. Fold accepted findings into
the phase entry and stamp it — `(Amended <date> after a codex review_plan pass:
<one-line list of changes>)` — so the gate is auditable later.

This is the highest-leverage review in the loop: a flaw caught here costs one doc
edit; the same flaw caught after implementation costs a whole phase.

## 6. Break work into scoped phases

- **One phase = one focused branch = one PR.** Small enough to review in one
  sitting.
- **Sequenced so gates compound** (see Principles).
- **Risk-tagged**, so high-risk phases (security, destructive ops, auth) are known
  up front to warrant the adversarial pass (§9).
- **Decision-gate phases that hinge on an open call.** When the plan carries a
  "Decisions for the user" item, align it with a phase boundary so the pause *is*
  the decision point — the phase doesn't start until the human answers.
- **ROADMAP absorbs anything cut** — scope creep goes to the backlog with
  rationale, not into the current PR.
- **Pause between phases.** The human chooses when the next one starts.
- **Re-seed context between phases when it helps** — judgment, not ceremony.
  `/clear` and re-seed from the plan doc when switching domains or when the prior
  phase's residue stops being load-bearing; a continuous session through closely
  related phases is fine with modern context management.

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
- **AI surfaces add an eval gate.** If a change touches a prompt, agent, or tool
  schema, its **eval suite is a required gate** alongside lint and tests — behavior
  is what regresses there, and only evals catch it. **Calibrate before you trust it
  as a gate:** an LLM-judged eval gates honestly only once its scores track human
  ratings on a sample — an uncalibrated judge carries biases (length, position,
  self-preference) that wave bad output through. **Example:** `dkan-aiq:eval` after a
  system-prompt or agent-routing change.
- **Make the must-run gates deterministic with a hook.** Advisory instructions
  get skipped; a hook does not (Anthropic's verification ladder — *CLAUDE.md is
  advisory, hooks are deterministic*). A `PreToolUse` hook on `git commit` that
  runs the fast gates (lint + unit) and blocks on failure turns "should run" into
  "always runs." Keep slow/integration checks (kernel, full matrix) in CI — the
  hook is fast local feedback; **CI stays authoritative.** This plugin ships such a
  gate (`hooks/commit-gate.sh`): it self-scopes to DDEV-backed modules and
  warns-but-allows when DDEV is down. A companion `hooks/dependency-gate.sh` applies
  the same principle to supply-chain risk — it blocks agent-initiated package installs
  (`composer require`, `npm install <pkg>`, `uv add`, …) until a human vets them (§9).
- Keep the change focused. When you spot an out-of-scope issue, **capture it** (a
  background-task chip, or a ROADMAP line) instead of widening the PR.
- **Route heavy exploration through `Explore` subagents.** Let a subagent sweep the
  codebase and hand back the conclusion; the implementing context stays focused on
  the change instead of filling with raw search output.
- At a genuine fork, **ask** (AskUserQuestion) rather than guessing. **Example:**
  "soften the hard `basic_auth` dependency, or keep it?" — a one-question fork that
  changed the phase's design.

## 8. Review the diff independently

Run the codex-reviewer `review_diff` before each PR — `general` profile always,
`security` profile for anything touching auth, access, destructive ops, or a
surface that exposes tools or data to an AI agent.

- **Fallback when codex is unavailable.** If the codex MCP is down, rate-limited,
  usage-exhausted, unconfigured, or erroring, **warn explicitly and do not skip the
  review.** Fall back to the in-Claude path: the built-in **`/code-review`**
  (correctness + cleanup), the **`plan-diff-reviewer`** subagent (diff-vs-plan), and
  the **§9 adversarial pass** for anything risky. **Record in the PR** that the
  external review was unavailable and what ran instead. The fallback is same-vendor,
  so it loses codex's cross-family diversity: for high-risk / security changes,
  escalate §9 (more lenses, `opus` + `sonnet`) and re-run codex once it is back.
- **Verify the diff against the plan, not just for bugs.** Confirm *every* plan
  requirement landed and nothing out of scope crept in — codex `plan_vs_diff`
  (mode `staged` for local work; mode `range` against the integration branch for a
  long-lived phase branch), and/or the bundled `plan-diff-reviewer` subagent (a
  fresh-context Claude reviewer handed only the diff + the plan, reporting
  requirement gaps, not style). Record the pass in the phase notes. The built-in
  `/code-review` is a separate, optional in-session correctness + cleanup pass.
- **Gotcha:** new/untracked files aren't in the `working` diff. `git add` them and
  review in `staged` mode, or they're silently skipped.
- **Integrate validated findings; decline noise with a recorded rationale.**
  **Example:** em-dash "fixes" are declined (accepted project style); a render-array
  nit was declined because the string form matches Drupal core's own convention.
- Re-review until `approve` / `approve_with_nits`.

## 9. Adversarial review in Claude when confidence is low

An independent reviewer is one opinion. When a finding is **low-confidence**, the
change is **high-risk**, or **the external reviewer is unavailable**, add a second,
adversarial pass inside Claude:

- **Independent skeptics** — subagents prompted to *refute* the change; a
  majority-refute kills it.
- **Perspective-diverse lenses** — give each reviewer a distinct angle
  (correctness / security / does-it-actually-reproduce) so redundancy doesn't blind
  them all to the same miss.
- **For an AI/agent surface, add a tool-I/O security lens.** Check the change
  against the **lethal trifecta** — private-data access + exposure to untrusted
  content + an exfiltration/write path; any two are survivable, all three is
  exploitable — and break it by *design*, not by prompt. Treat tool inputs *and*
  outputs as untrusted (injection arrives through call arguments and through
  returned data — never let returned content act as instructions); enforce least
  privilege per tool; keep read-only and read-write tools on **separate,
  separately-credentialed surfaces** (the `dkan-ro` / `dkan-rw` split) so text
  injected on the read path has no write tool in reach; keep destructive verbs
  **human-gated**, not autonomous. Vet **AI-suggested dependencies** — confirm the
  package exists and is the one you meant (slopsquatting), then pin; the
  `dependency-gate` hook (§7) makes this stop deterministic. Anchor the pass to
  the **OWASP LLM Top 10** and **OWASP Agentic AI Top 10** so the lenses track
  named threats, not intuition.
- **Vary the model, not just the prompt.** Run lenses under different models (the
  Agent tool's model option) and include the cross-family codex reviewer — a
  same-family panel can *amplify* a shared bias instead of cancelling it (the
  agent-as-judge / CollabEval finding). The bundled `plan-diff-reviewer` (§8) is a
  reusable fresh-context panelist.
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
  ready for the next phase. After a **squash merge**, ancestry detection breaks —
  `git branch -d` refuses; use `-D` for the verified-merged branch.
- **When an external maintainer owns the merge** (e.g. a drupal.org contrib
  module): never self-merge — the maintainer squash-merges via the web UI, usually
  deleting the source branch. After their merge, do the cleanup above, then a small
  plan-only commit to the default branch recording the squash sha and MR number in
  the living plan's Current state (§4).
- **Before the next phase, capture what you learned.** If this phase surfaced a
  durable, non-obvious finding that caused a correction, write it into the repo's
  procedural memory now (§12) — while the context is fresh.

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

The loop doesn't end at merge — the toolkit and its knowledge need upkeep:

- **Toolkit currency**: run `/check-skill-currency` (optionally on a schedule) to
  verify pinned version facts against upstream and report drift before it misleads.
- **Procedural memory**: after each phase, distill the durable, non-obvious
  findings — the ones that *caused a correction* — back into the working repo's
  `AGENTS.md`/`CLAUDE.md` Gotchas or the relevant skill. Those gotchas and skills
  *are* the project's procedural memory; writing them back closes the
  compounding-knowledge loop, so the next session starts from the lesson instead
  of re-deriving it. **Two tiers:** a finding can rest in the harness's file-based
  memory the moment it appears (cheap, session-spanning, not yet shared); *promote*
  it to the committed `AGENTS.md`/skill once it recurs or proves durable — the
  committed layer is shared and reviewed, so promoting (not every passing thought)
  keeps it lean. Pairs with currency: currency keeps *known* facts fresh,
  procedural memory adds the *newly-learned* ones. **Example:** the
  unenforced-`checkAccess` gotcha, captured into the `drupal-mcp-server` skill so
  no later session rediscovers it.
- **Prune the contract**: currency and procedural memory only *add* to the
  `AGENTS.md`/`CLAUDE.md` contract and skills, so periodically cut the other way or
  the layer bloats until its rules get ignored (a long contract dilutes
  instruction-following — the failure §7 routes around with hooks). On a cadence
  (pair it with `/check-skill-currency`): drop stale or duplicated guidance,
  **promote must-happen rules to hooks** instead of restating them, and **link to
  the doc spine, don't inline** (§2). Where `AGENTS.md` is generated (this repo),
  prune the *skills* it builds from, not the output.
- **Earn-its-keep review**: on the same cadence, give every gate, eval, and tool a
  keep/fix/delete decision if it hasn't produced value since the last pass. A
  documented *workaround* for broken tooling is the tell — a workaround is a
  deferred decision. **Example:** a triggering eval sat broken behind a documented
  plugin-disable dance until a demolition pass deleted it; this review forces that
  call sooner.
- **Dependency drift**: when you ride dev branches/pins, add a CI job that bumps to
  upstream HEAD and runs **contract tests** — assert the consumed upstream symbols
  still exist, instantiate every plugin. It goes red the moment upstream breaks you,
  turning silent breakage into an early signal. **Example:** the `mcp_server` /
  `mcp/sdk` pin-bump job + `UpstreamContractTest` + `ToolDiscoveryTest`.
- **MCP / AI-surface supply chain**: an MCP server you *consume* is a dependency
  too — its tool descriptions, schemas, and return values are attacker-controllable
  (tool poisoning), and a silent post-approval redefinition is a *rug pull*. Vet it
  before trusting it; pin/snapshot its tool definitions so a changed scope trips a
  diff. For a server you *build*, add a **tool-permission contract test** to the
  suite above: snapshot each tool's `id` → access gate and fail the build if a
  write/destructive tool is added without a `checkAccess` + subscriber gate, or an
  existing one loses it (the excessive-agency / OWASP LLM06 guard). **Example:** the
  DKAN MCP `ToolAccessSubscriber` + a snapshot over the read-only vs read-write
  tool split.
- **AI-surface regression**: prompts, agents, and tool schemas drift as models and
  dependencies change — keep their eval suite as a standing regression gate and
  re-run it on every change to those surfaces (§7).
- **ROADMAP** is the living deferral log: anything cut from a phase lives here with
  rationale until it's scheduled.

---

## Generalizing to another project

The loop is framework-neutral; lift §1–§12 as-is. The sequence (baseline → plan →
review-plan → per-phase gates → `/goal` cleanup → maintain), the review gates, the
pause cadence, and the doc discipline are **universal**. Only three pieces are
stack-specific — swap them:

- **Toolkit** (§1) — a skills/commands repo for your stack: decision-support docs
  keyed to file globs, scaffolding procedures, a currency manifest, adapter
  regeneration if you target multiple agents.
- **Contract** (§2) — an `AGENTS.md` per repo: build/test/lint commands, style,
  norms, and the three-doc spine.
- **Gate commands** (§7) — your linter, test runner, and eval harness in place of
  phpcs/phpunit-via-DDEV; your scaffolds; your upstreams as the currency sources.

**Scaling note:** the loop is sequential by design — the pause between phases is a
feature, not a bottleneck. Genuinely independent work can parallelize across git
worktrees — confirm it's *actually* independent first (a shared foundation others
build on is not). **File isolation isn't enough:** parallel agents that run tests
still share one DDEV instance, database, and ports, so true parallelism needs
per-agent runtime isolation, not just disjoint files. And the real ceiling is
**human review throughput** — past a few concurrent agents the bottleneck is your
attention at the gates, not agent speed.
