# Scaffold-correctness gate

An **enforced gate**. Each scaffold command
embeds the canonical code it instructs Claude to emit (fenced templates) plus a
**"Pitfall checks"** list. This gate turns that documented contract into deterministic
assertions — a **regression gate over the shipped command templates**.

Unlike the task-outcome eval (does the model produce good output?) this checks the
**artifact we commit**: no LLM, no PHP, no network, so it is fully reproducible and
runs anywhere.

## Method

- **10 commands that embed code templates** (the `scaffold-*`, `ai-scaffold-*`,
  `mcp-scaffold-tool`, `add-drupal-route`, `add-event-subscriber`, and — added
  2026-07-08 after a coverage review flagged its four fenced PHP templates as
  ungated — `dkan-core-test`). The 2 procedural commands (`validate-*`, zero
  code fences) are out of scope.
- For each, `check_scaffolds.py` extracts every fenced code block and runs assertions from
  `checks.json`:
  - **`assert_pos`** — required forms that MUST be present: the plugin attribute, the correct
    base class, exact method signatures, the version-gate step.
  - **`assert_neg`** — fabricated/wrong forms that must be ABSENT (the hallucinations the
    Pitfall lists warn against).
  - **scope** `code` = all fenced blocks concatenated; `doc` = the whole file. Matching is
    **case-sensitive** (`TRUE`/`FALSE` and PHP identifiers are case-significant).
- **Pass** ⇔ every `assert_pos` matches AND no `assert_neg` matches. Non-zero exit fails the gate.

> **Negatives are always `code`-scoped.** The Pitfall prose deliberately *names* the wrong
> forms ("NOT `plugin.manager.ai_assistant_action`"), so a doc-scoped negative would
> false-fail on the warning text. Prose-only facts (service IDs, dependency names) are
> asserted **positively** at `doc` scope instead.

## Result

**10/10 commands pass · 84/84 assertions (71 positive, 13 negative).**

| command | skill | kind | pos | neg |
|---|---|---|---|---|
| mcp-scaffold-tool | drupal-mcp-server | full-template | 7 | 3 |
| ai-scaffold-tool | drupal-ai-module | full-template | 7 | 2 |
| ai-scaffold-action | drupal-ai-module | full-template | 10 | 2 |
| ai-scaffold-agent | drupal-ai-module | full-template | 9 | 2 |
| ai-scaffold-provider | drupal-ai-module | full-template | 8 | 1 |
| scaffold-dkan-module | dkan-module-author | full-template | 9 | 1 |
| scaffold-drupal-service | drupal-module-dev | snippet | 4 | 0 |
| add-drupal-route | drupal-module-dev | snippet | 5 | 0 |
| add-event-subscriber | dkan-module-author | snippet | 5 | 0 |
| dkan-core-test | dkan-core-contributor | full-template | 7 | 2 |

`full-template` commands embed complete canonical files (checked thoroughly); `snippet`
commands embed illustrative patterns (checked more lightly — honestly labeled).

## The gate discriminates (it is not vacuously green)

A green gate is worthless if its assertions can't fail — and a typo'd negative passes
*silently* forever. This is the Phase-3 analog of Phase 2's discrimination pre-check, but
enforced rather than checked once:

- **13/13 negatives are live, re-verified on every run.** Each `assert_neg` carries a
  `neg_example` (the violation it exists to catch); the checker fails the gate if a negative
  cannot match its own example. A negative can never silently rot into vacuity.
- Positive signatures are **non-vacuous** — they currently match, so removing or breaking
  one fails the gate immediately.
- **End-to-end:** renaming the `triggerAction()` signature to a fabricated `triggerInstruction`
  flips `bin/eval scaffolds` to exit 1, reporting both the missing signature and the
  fabricated-name hit. Restoring returns it to green.

## What it catches

The exact class of bug this repo has fixed by hand — drifted version constraints, wrong
directory casing, and **AI-fabricated symbol names**. Examples the negatives guard against:
a fabricated `RuntimeToolHandlerInterface` (corrected in `32776d3`), the old `Builder::addTool`
0.4/0.5 SDK API leaking into the 0.6 template, `triggerInstruction`/`executeAction` (invented
method names), `JOB_NEEDS_MORE_INFO` (fictional constant), a `dkan:metastore` dependency missing
the `dkan_` prefix, and a redefined-`__construct` on a `final`-constructor base.

## phpcs layer (skip-guarded)

`bin/eval scaffolds` runs the deterministic gate above, then **optionally** lints **real
generated output** with `phpcs --standard=Drupal,DrupalPractice`:

- It activates only when a phpcs binary is reachable (`EVAL_PHPCS`, e.g.
  `"ddev exec vendor/bin/phpcs"`, or `phpcs` on PATH) **and** `EVAL_SCAFFOLD_OUTPUT_DIR`
  points at generated code. Otherwise it prints `SKIP` and the gate still passes — mirroring
  `bin/test`'s jq/git skip pattern.
- **This is a plugin repo with no PHP/DDEV, so phpcs always skips here.** It is intended for a
  DDEV/CI runner (decision D4: local skip-guard now, DDEV CI later). Linting concrete generated
  files there is more meaningful than linting placeholder templates — and each command already
  carries its own `phpcs` + runtime-discovery verification steps for the in-session generation flow.

## Honest caveats

- **Golden/regression gate, not independent world-correctness.** It encodes each command's
  *documented* contract as executable assertions. It catches edits that silently break a
  template; it does not prove the template is correct against live Drupal/DKAN APIs — that is
  what phpcs lint and the commands' own runtime-discovery steps (`drush ev … getDefinitions()`)
  provide.
- **Some shared authorship.** The same repo authors both the templates and the assertions, so
  this is a snapshot/regression test (like any unit test), not an external oracle. Its value is
  protecting against future drift, and it is anchored where possible to independently-verified
  facts (e.g. the `^10.5 || ^11.2` AI core floor also asserted in Phase 2 T2).
- **Snippet commands are checked more lightly** by design — they embed patterns, not whole files.

## Reproduce

```bash
bin/eval scaffolds                 # gate + skip-guarded phpcs; exit non-zero on failure
python3 evals/lib/check_scaffolds.py   # gate only; writes results.json
```

## Files

- `checks.json` — per-command assertion spec (source of truth)
- `results.json` — graded results (per-command pass + matched/missed assertions)
- `../lib/check_scaffolds.py` — deterministic checker
- `../../bin/eval` — `scaffolds` subcommand (gate + skip-guarded phpcs)
