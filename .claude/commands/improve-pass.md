---
description: Run one improvement iteration against the docs/ROADMAP.md backlog — verify, fix, gate, PR
argument-hint: "[item-number | next]"
---

Run **one** iteration of the repo's improvement loop. This is a repo-maintenance
command; it does not ship with the plugin. One invocation = one backlog item = one
branch + PR, then stop for the human merge. Repeatable via `/loop /improve-pass`
when the user is present to merge between iterations.

## Input

`$ARGUMENTS` (optional): a backlog item number from `docs/ROADMAP.md` to work, or
`next` (default) for the top unchecked item in priority order (P1 → P5).

## Steps

1. **Pick.** Read `docs/ROADMAP.md`. Take the requested item, or the first
   unchecked backlog item. If the backlog is empty, evaluate the **Ratchet
   targets** instead: check off any now satisfied, propose the next concrete step
   for any unmet, and stop (report only).

2. **Verify the finding first — it is a claim, not a fact** (WORKFLOW.md §3).
   Check it against the primary source: read the cited file/lines (they may have
   drifted since seeding), the upstream code, or the live site; use codex
   `verify_claim` when refutation needs an independent check. If the finding is
   wrong or already fixed, move it to **Declined** with rationale (or check it
   off with a "resolved by …" note), commit that as the pass's PR, and stop.

3. **Fix at one-PR scope.** Branch off `main`. While editing, two standing rules:
   - **Single-source any version-pinned fact you touch**: one file owns it,
     others link (see the mcp-overview.md "version facts live in SKILL.md"
     pattern). Update `skills-currency.yml` if a claim's wording or home moved.
   - **A real wrong answer becomes an eval**: if the item shows a skill giving a
     wrong answer (not just weak prose), add the failure-driven task or assertion
     per docs/EVALS.md — the wrong answer is the `assert_neg`.
   Scope creep goes to ROADMAP as a new line, not into the PR.

4. **Gate.**
   - `bin/test` (always).
   - `bin/eval scaffolds` if commands/checks changed; `bin/eval task` regrade if
     tasks.json changed; `bin/eval live` (with `EVAL_DKAN_SITE_DIR`) if the
     MCP/DKAN/DCAT reference docs changed — update the dated summary line in
     `evals/live/REPORT.md` if the outcome changed.
   - `bin/build-adapters` + re-run `bin/test` if any SKILL.md or command changed.
   - Bump the plugin patch version + `claude plugin validate` if anything under
     `plugins/` changed.
   - MCP `review_diff` (staged) to `approve` / `approve_with_nits`. Agent-facing
     content always gets the full review (WORKFLOW.md, Right-size).

5. **Record + PR.** In the same branch: check the item off in `docs/ROADMAP.md`
   (append `— done <date>, PR #<n>` once known), add any newly discovered
   follow-ups as new backlog lines, and re-evaluate the Ratchet targets. Commit,
   push, open the PR (repo conventions: concise message, trailer, generated-with
   line). **Stop — the human merges.**

## Guardrails

- One item per invocation; never batch backlog items into one PR unless they are
  the same edit (e.g. one fact sprayed across files counts as one item).
- Don't grow docs to fix docs: additions must displace or consolidate (the
  contract-bloat rule, WORKFLOW.md §12). Net-negative or net-neutral lines is the
  default expectation for P3/P4 items.
- Speculative eval assertions are the rot vector — only add negatives/tasks for
  observed failure modes (docs/EVALS.md policy).
- If verification refutes a finding, that outcome is a valid pass — recording a
  decline prevents the next session from re-deriving it.
