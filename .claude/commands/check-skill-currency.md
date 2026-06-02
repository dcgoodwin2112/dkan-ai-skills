---
description: Check the skills' pinned version facts against upstream sources and report drift
argument-hint: "[skill-name | all] [--cadence monthly|quarterly|all] [--write]"
---

Audit the version-pinned facts in the skills against their upstream sources, using
`skills-currency.yml` as the checklist. This is a repo-maintenance command for keeping
the `drupal-dkan-ai` skills current; it does not ship with the plugin.

## Input

`$ARGUMENTS` (all optional):

- **scope** — a skill name (e.g. `drupal-module-dev`) to check just that skill, or `all`
  (default) for every skill in the manifest.
- **`--cadence monthly|quarterly|all`** — only check claims at this cadence. Default
  `all`. Use `monthly` for the routine pass, `all` for a full reconciliation.
- **`--write`** — after verification, update `last_verified` dates in
  `skills-currency.yml` for claims confirmed still-current, and (only when you are
  confident) draft doc edits for confirmed drift. Without it, report only — make no edits.

## Steps

1. **Load the manifest.** Read `skills-currency.yml`. Parse `sources` (where to check)
   and `skills[*].claims` (what to verify). Filter by the scope and `--cadence` args.

2. **Coverage check.** List `plugins/drupal-dkan-ai/skills/*/`. If any skill directory
   has **no** entry in the manifest, flag it as a gap ("skill X not tracked") — currency
   checking silently misses untracked skills.

3. **Verify each claim.** For each in-scope claim, fetch its `source` (WebFetch /
   WebSearch the release notes, change records, project page, repo tags, or npm page) and
   compare against the `claim` text. Classify:
   - **current** — source confirms the claim still holds.
   - **drift** — source contradicts or supersedes it (new version, changed API, removed
     feature, moved deprecation milestone). Capture the specific delta.
   - **unverifiable** — source unreachable or ambiguous. Say so; do not guess.

   Be conservative: only call something **drift** when the source clearly shows it.
   Prefer authoritative sources (drupal.org change records / release notes, official
   repos, npm/packagist) over blog posts. For DKAN internal-API claims, note that the
   installed copy is the real source of truth.

4. **Report.** Output a triage table grouped by skill:

   | Skill | Subject | Status | Detail / delta | Source |
   |---|---|---|---|---|

   Then a short prioritized list of recommended doc edits (which SKILL.md / reference doc,
   what to change, and why), highest-impact first. Note any coverage gaps and
   unverifiable entries separately.

5. **(`--write` only) Apply.**
   - For **current** claims: bump their `last_verified` to today's date in
     `skills-currency.yml`.
   - For **drift** you are confident about: make the corresponding edit in the skill doc
     **and** update the manifest `claim` text + `last_verified`. Keep the docs' existing
     style (cite the Drupal version, hedge leading-edge items with "verify against your
     core version"). Leave anything uncertain for human review — list it instead of
     editing.
   - If any SKILL.md or command under `plugins/drupal-dkan-ai/` changed, run
     `bin/build-adapters` and confirm `bin/test` passes (Test 7 = no adapter drift).

## Notes

- Default to **report-only**. `--write` exists for confident, mechanical updates; doc
  judgment calls (what to hedge, what to omit) stay with a human reviewer.
- Today's date is available in the session context — use it for `last_verified`.
- This command pairs with an optional monthly scheduled run (see the repo README's
  maintenance section) that invokes it and opens an issue/PR with the findings.
