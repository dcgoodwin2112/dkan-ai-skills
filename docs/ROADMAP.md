# ROADMAP

The tracked deferral log and improvement backlog (WORKFLOW.md §2/§6/§12). Worked
one item at a time by `/improve-pass` — each pass verifies the finding, fixes it
at one-PR scope, and checks it off here in the same PR. Items are **claims from
review passes, not facts** — verify against the primary source before acting;
refuted items move to Declined with rationale.

Backlog seeded 2026-07-08 from a three-agent deep review (skills content, eval
coverage, commands/infra). Evidence pointers are file:line at seeding time.

## Ratchet targets

The measurable definition of "the skills and evals are getting better." Check off
when reached; an `/improve-pass` that can't pick a backlog item checks these.

- [x] Every task-eval assertion fails the baseline on ≥1 run or is an explicitly
      accepted tie — met 2026-07-08 (PR #52 made T3 discriminate; PR #53 accepted
      T1/T5 as documented harm canaries)
- [ ] Every high-volatility `skills-currency.yml` claim has a mechanical tripwire
      (live check, scaffold/doc assertion, or staleness warning) or an explicit
      accepted-gap note in the manifest
- [ ] Every version-pinned fact lives in exactly one skill file; other files link
      (the fact-spray ratchet — see items 12–17)
- [x] Every command that embeds code templates is scaffold-gated — met 2026-07-08
      (PR #51; the two `validate-*` commands have zero code fences)

## Improvement backlog

### P1 — verified errors

- [x] 1. **Fix `revertHarvest()` contradiction + de-duplicate HarvestService API.**
      `dkan-module-author/reference/dkan-services.md:167–182` says `: mixed`,
      `dkan-harvest.md:114` says `: int`; source (`HarvestService.php:193`) is
      untyped with no return type. Keep one API list, match the source.
      — done 2026-07-08, PR #46. Verification widened it: five more methods had
      invented types in both copies; dkan-harvest.md now owns the list, matching
      4.x exactly, with a "don't re-type these" note.
- [x] 2. **Stale "three curl probes" after the Basic-probe retirement.**
      `bin/eval:23–24`, `evals/lib/check_live.py:7` and `:387` (writes wrong
      provenance). Actual count: two (`http.anon`, `http.prm`).
      — done 2026-07-08, PR #47. Verification found a fourth site
      (checks.json `_about`); all four reworded count-free so a future probe
      change can't restale them.
- [x] 3. ~~**`commands/validate-module.md:24`**: `ddev exec phpunit` →
      `ddev exec vendor/bin/phpunit`~~ — **declined 2026-07-08** (finding
      refuted): DDEV puts `vendor/bin` on the web-container PATH by default;
      verified on the live container (`which phpunit` →
      `/var/www/html/vendor/bin/phpunit`), so `ddev exec phpunit` works. The
      cited fragility doesn't exist; the explicit-path form on line 18 is a
      style preference, not a fix.
- [x] 4. **Commit-gate timeout fails open silently.** `hooks/hooks.json` sets 120s;
      multi-module phpcs+phpunit via DDEV can exceed it and the commit proceeds
      ungated. Raise it and/or document the fail-open in the script header + README
      (the only undocumented fail-open path).
      — done 2026-07-08, PR #49. Timeout 120→300s; fail-open documented in the
      script header and README's commit-gate list.
- [x] 5. **`dkan-harvest.md` namespace map incomplete.**
      `Drupal\dkan_harvest\Transform\ResourceImporter` (source-verified) lives
      outside `ETL\` like `Load\Dataset`, but the map only flags the latter;
      `dkan-api.md:180–189`'s plan example should defer to dkan-harvest.md.
      — done 2026-07-08, PR #50. Blanket ETL\* claim qualified; ResourceImporter
      documented from its verified docblock; api.md example defers for FQNs.
      **P1 complete: 4 fixed, 1 declined.**

### P2 — eval gaps

- [x] 6. **Add `dkan-core-test` to the scaffold gate.** It embeds 4 fenced PHP
      templates (`Api1TestBase`, `@group dkan`/`functional1`, `QueueRunnerTrait`,
      `namespace Drupal\Tests\…`) but has no `checks.json` entry — a fabricated
      base class would ship ungated. ~10 lines using existing machinery.
      — done 2026-07-08, PR #51. 7 pos + 2 failure-driven negs (both
      hallucinations found in T4's recorded baseline runs). Gate now 10/10
      commands / 84 assertions.
- [x] 7. **Split task T3's alternation.** `MetastoreService|dkan\.metastore\.service`
      passes on either token though the prompt demands both; baseline passes 3/3
      (non-discriminating). Split into two `assert_pos`, regrade, commit benchmark.
      — done 2026-07-08, PR #52. Verification showed the proposed split alone
      wouldn't discriminate (baseline had both tokens); the real discriminator is
      the pre-4.x `Drupal\metastore\` namespace baseline hallucinates in all runs
      — now the assert_neg, with the 4.x FQN as a positive. Headline now
      95%/33%/+62pp, 5 of 7 tasks discriminating. Grader's hardcoded ties caveat
      made dynamic.
- [x] 8. **Fix or accept non-discriminating T1 and T5** (baseline 3/3 ties).
      Either sharpen the prompts/assertions to something baselines miss, or mark
      them accepted ties in tasks.json `_about` + REPORT so they stop reading as
      coverage.
      — done 2026-07-08, PR #53. Accepted (no hidden discriminator in the
      recorded runs); retained as harm canaries with explicit notes. Codex
      caught a JSON-breaking edit my masked gate chain missed — see PR.
- [x] 9. **Add an `mcp/sdk ^0.6` doc tripwire** to the `mcp-scaffold-tool` scaffold
      entry — deliberately brittle so the gate goes red the day the SDK floor bumps.
      Nothing currently fails when docs say 0.6 after 0.7 lands.
      — done 2026-07-08, PR #54. Doc-scoped positive with a
      pinned-by-test note; gate now 85 assertions.
- [ ] 10. **Warn-only currency-staleness CI step**: ~20 lines of date math flagging
      any `skills-currency.yml` `last_verified` older than its `cadence`. Warn,
      never fail (no network in CI).
- [ ] 11. **dkan-frontend eval surface is one regex (T7).** Policy is
      failure-driven-only: add a lineage-fork task only when a real session gets
      it wrong. Recorded here so the gap is a decision, not an oversight.

### P3 — single-sourcing (fact-spray ratchet)

- [ ] 12. **drupal/ai version fact → SKILL.md only.** Currently in 4 files
      (SKILL.md:36, pitfalls.md:3, ai-search-rag.md:3, services.md:145); copy the
      mcp-overview.md:86 pattern ("version facts live in SKILL.md — deliberately
      not restated here").
- [ ] 13. **MCP tool counts → dkan-integration.md only.** Soften
      drupal-mcp-server/SKILL.md:124's hard "38 tools (25 read / 13 write)" to
      "~38 — see dkan-integration.md; verify live"; the live gate owns the number.
- [ ] 14. **justinrainbow→opis migration note → core-internals.md:66–73 only**
      (also stated in dkan-core-contributor SKILL.md:29–31, :49, and
      core-overview.md:90–91). Feature-branch state; will invalidate all four.
- [ ] 15. **De-triplicate the `create()` override snippet** in
      drupal-ai-module/reference/services.md (:41–56, :64–80, :88–104) — state
      once, reference twice (~35 lines).
- [ ] 16. **Drop dkan-frontend/SKILL.md:78–82's lineages table** (architecture.md's
      copy is fuller); collapse `datastore_query_api` explanations (4 files) to
      SKILL.md rule + build-deploy-customize.md detail.
- [ ] 17. **De-duplicate the reference-resolution algorithm** within
      dkan-module-author (dkan-overview.md:61–71 vs dkan-workflows.md:208–245,
      ~35 lines; the core-contributor inside-view copy is justified).

### P4 — content quality

- [ ] 18. **Remove checkout-specific state from distributable skills:**
      ai-search-rag.md:5 "Install status (this checkout)", dkan-module-author
      SKILL.md:85 "This site runs…", dkan-drush.md:7 DDEV assumption; flag
      `dkan_query_tools` / `dkan_ai_query` worked examples as "may not exist on
      your site" (replace state with a verify command: `composer show`, `drush pml`).
- [ ] 19. **Condense drupal-mcp-server/reference/auth-and-access.md:7–34** (generic
      lethal-trifecta/OWASP doctrine a strong model knows) to ~5 lines; the doc's
      job starts at the unenforced-`checkAccess()` content.
- [ ] 20. **Cut dead weight:** drupal-ai-module pitfalls.md #8 ("no functional
      impact" — not a pitfall); drupal-mcp-server testing.md:70–85 aspirational
      contract-test essay (or move to this ROADMAP as a real deferral).
- [ ] 21. **permissions.yml gap:** drupal-module-dev has no permissions.yml coverage
      while routing docs lead with `_permission` and `/add-drupal-route` promises
      one. Small subsection in routing-forms-rendering.md or module-lifecycle.md.
- [ ] 22. **dkan-frontend dev-server gap:** no local `npm start`-against-a-DKAN-
      backend workflow (proxy/CORS) — a first-hour task for frontend customizers.
- [ ] 23. **dkan-core-contributor SKILL.md rules↔pitfalls restatement** (4 of 6
      pitfalls re-word rules from 20 lines earlier) — merge or differentiate.

### P5 — commands & infra polish

- [ ] 24. **Broken next-steps in two scaffold commands:** ai-scaffold-tool.md:121 and
      mcp-scaffold-tool.md:165 tell the user to run a module-local phpunit harness
      that only `/scaffold-dkan-module --with-tests` creates — point at
      `/validate-module` instead (it already branches on `phpunit.xml`).
- [ ] 25. **`scaffold-drupal-service.md`**: only codegen command with no skill-doc
      pointer (→ services-and-di.md). Consider snippet negatives for the three
      snippet commands only when a real fabrication is observed (speculative
      negatives are the rot vector).
- [ ] 26. **dependency-gate wrapper gaps:** `ddev exec -s web composer require …`,
      `docker compose exec app …`, and `composer req` bypass the gate; close +
      add bin/test cases. (In-scope per its own "speed bump" framing.)
- [ ] 27. **`bin/install --adapters` overclaims vendoring** (README:100): absolute
      symlinks into the local checkout don't "travel with the project" — copy
      instead, or reword.
- [ ] 28. **Scope the commit-gate phpunit run** (`--testsuite unit` when defined) or
      soften the "kernel left to CI" claim (commit-gate.sh:14, README:148).
- [ ] 29. **`demo/before-after.sh` earn-its-keep call:** presentation aid with a
      documented nested-`claude -p` 401 workaround; keep (and note the workaround
      is upstream-bound) or delete.
- [ ] 30. **Dispose completed plan docs** once this ROADMAP absorbs their deferrals:
      `docs/plans/2026-06-12-eval-demolition.md` (fully executed),
      `docs/plans/2026-07-08-codex-integration-next-steps.md` (phases 1–2 done).

## Deferred / not scheduled

- **`.codex/skills/` adapter target** — emit canonical skills in Codex's skills
  dir (SKILL.md is cross-compatible). When adapters are next touched: extend
  `bin/build-adapters`.
- **codex-reviewer-mcp per-profile model/effort** — deferred to its own plan in
  that repo (2026-07-08 codex-integration plan, phase 3). Gate: CLI upgrade +
  upstream-flag verification.
- **Direction-inversion experiments** (Codex drafts, Claude reviews — the KDD '26
  asymmetry finding): use `/codex:rescue` ad hoc; codify only if results warrant.
- **Trigger-eval rebuild**: designated path is promptfoo's `skill-used` assertion,
  not a bespoke harness (docs/EVALS.md, Removed).

## Declined (with rationale)

- **DDEV-in-CI for the live gate** — would rot hard; the gate stays local +
  folded into the monthly currency pass.
- **Network fetches in CI** for currency checking — same rot; `/check-skill-currency`
  owns upstream verification.
- **dkan-core-contributor CI-matrix eval** — upstream CircleCI config can't be
  checked without fetching GetDKAN/dkan; consciously accepted manual-currency gap.
- **Retiring the codex-reviewer MCP** in favor of the Codex plugin — plugin lacks
  plan review, claim verification, conformance checking, and structured verdicts
  (2026-07-08 assessment).
