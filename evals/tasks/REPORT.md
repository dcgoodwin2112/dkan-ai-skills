# Task-outcome eval

The headline, **non-circular** eval: does having the skill produce better answers on real
DKAN/Drupal tasks than no skill? The skill must actually *change the output*.

## Method

- **7 self-contained tasks** (`tasks.json`), one per skill, each with a known-correct answer
  present in that skill's docs. Tasks target version- and DKAN-specific facts (the kind that
  drift) plus two short code-gen tasks.
- **Paired runs, same session model both arms** — so the only variable is skill access:
  - **with-skill**: subagent reads the named skill's docs, then answers.
  - **baseline**: subagent answers from parametric knowledge only (no file/doc access).
- **3 runs per arm** (`runs/raw_runs.json`).
- **Deterministic grading** (`grade_tasks.py`): `pass` ⇔ every `assert_pos` regex matches AND
  no `assert_neg` matches. No LLM judge → no judge bias, fully reproducible. (This is how the
  plan's grader-calibration concern is met: by construction, not by trusting a judge.)
- **`php -l` axis** (opt-in per task via `check_php_lint`; currently T6 only — the one task
  whose answers reliably contain PHP): each ```php block containing `<?php` must lint clean.
  Fragments without the opening tag are skipped — guess-wrapping false-fails valid bare-method
  snippets (observed during 2026-07-27 calibration). No host `php` → axis skipped with a
  console warning, never a silent lint-clean. All 6 complete-file blocks in the current corpus
  verified clean (via `ddev php -l`); the axis exists to catch *future* regressions.
- **Results are model-generation-pinned.** Both arms use the collecting session's model, so
  every number below is a property of *that model + the skills*, not of the skills alone —
  a stronger base model raises the baseline and shrinks the delta. `raw_runs.json` `_meta`
  records the collection date and model (the 2026-06-08 corpus predates stamping; its model
  is unrecorded, pre-Claude-5). Tasks that tie on a newer baseline are trim candidates, not
  regressions — see the accepted-tie notes on T1/T5.

## Result — 2026-07-27, `claude-fable-5` (current)

| | passed | rate |
|---|---|---|
| **with skill** | 21/21 | **100%** |
| **baseline (no skill)** | 6/21 | **29%** |
| **delta** | | **+71 pts** |

| metric | with skill | baseline |
|---|---|---|
| pass^3 — tasks passing on **all 3** runs | **7/7** | 2/7 |
| pass@3 — tasks passing on **any** run | 7/7 | 2/7 |
| per-run pass rate (mean ± stddev) | 100% ± 0% | 29% ± 0% |

**Normalized gain g = 1.00** — the skill closes the entire achievable gap; both arms
are perfectly consistent across runs. **5 of 7 tasks discriminate** (T2, T3, T4, T6,
T7): on that drift-prone subset the contrast is **15/15 vs 0/15 (+100pp)**. Baseline
again produced confident, **plausible-but-wrong** answers:

| task | correct (with skill) | claude-fable-5 baseline hallucinated |
|---|---|---|
| 2 drupal/ai core floor | `^10.5 \|\| ^11.2` | `^10.3 \|\| ^11` (all 3 runs) |
| 3 metastore class | `Drupal\dkan_metastore\MetastoreService` | led with the pre-4.x `Drupal\metastore\` namespace (all 3 runs) |
| 4 DKAN CI groups | `functional1/2/3` | recommended the bare `@group functional` (all 3 runs; caught by the neg added 2026-07-27) |
| 6 MCP write tool | `#[Tool]` + `ClientGateway` + `checkAccess` | invented `Mcp\Schema\…` result types, `execute()` without `ClientGateway`, no enforcement gate |
| 7 frontend config key | `datastore_query_api` | `datastore_endpoint`, `useSqlEndpoint`, `useDatastoreQuery` |

**Cross-generation finding (the point of the re-baseline):** upgrading the base
model did **not** make the skills redundant. The discriminating set is unchanged
from the pre-Claude-5 corpus — the ties are still exactly T1 and T5, the accepted
harm canaries — so the 2026-07-27 sweep produced **zero new eval-backed trim
candidates** (ROADMAP item 34's evidence). The baseline is *more fluent* but wrong
about the same version-pinned, post-cutoff facts; one hedged run even slipped the
positive-only T4 regex while recommending the wrong group, which is why T4 gained
its failure-driven neg. The 2 ties (T1, T5) remain harm canaries per their
`tasks.json` notes: a future skill-doc error there would surface as the with-skill
arm dropping below baseline.

## Result — 2026-06-08 corpus (archived; model unrecorded, pre-Claude-5)

Graded under that date's assertions: **with skill 20/21 (95%) vs baseline 7/21
(33%), +62pp; pass^3 6/7 vs 2/7; g = 0.93**; same 5 discriminating tasks (14/15 vs
1/15, +87pp on the subset). With-skill's single miss was T3 run 1, a hedged answer
giving both namespaces — graded a fail, honestly. Corpus archived at
`runs/raw_runs-2026-06-08.json`; numbers are that era's published record and are
not regraded under later assertion changes.

## Honest caveats

- **packaged-skill-vs-nothing.** The delta measures the packaged skill end-to-end (its curated
  docs, available to read) vs no skill — not SKILL.md prose in isolation. That's what a user
  actually gets.
- **In-session, not production triggering.** with-skill here *reads* the docs; whether the skill
  auto-loads in the first place is not measured by this eval.
- **3 binary runs/arm is coarse** — this is a reported evidence/demo artifact, not a pass/fail
  gate. (The cheap, stable gates are the scaffold and live-currency checks.)
- **Grader calibration done by design:** deterministic regex grading (no judge); during a
  verification pass I dropped a brittle `functional0` negative (correct answers mention it to
  dismiss it) and tightened the `#[Tool]` pattern. On 2026-07-08 T3 was recalibrated: its
  alternation passed on either of two tokens and never discriminated; it now requires the 4.x
  `dkan_metastore` namespace and rejects the pre-4.x FQN observed in the recorded runs — which
  also (correctly) fails one hedged with-skill run. On 2026-07-27 T4 gained a failure-driven
  neg (`@group functional` bare, excluding the `functionalN` placeholder) after all three
  claude-fable-5 baseline runs recommended it and one slipped the positive-only regex. See
  `tasks.json` notes.
- **Subagent environment context** includes the repo's git summary (recent commit subjects);
  one baseline run's prose referenced it. None of the graded assertion tokens appear in commit
  subjects, so grading is unaffected — recorded in `raw_runs.json` `_meta.caveat`.

## Reproduce

```bash
python3 evals/lib/grade_tasks.py        # re-grade runs/raw_runs.json -> benchmark.json
```
To collect fresh runs, re-run the paired subagents over `tasks.json` (in-session; the grading
step is deterministic).

## Files

- `tasks.json` — corpus + deterministic assertions (source of truth)
- `runs/raw_runs.json` — recorded paired runs (3/arm, current: 2026-07-27 `claude-fable-5`)
- `runs/raw_runs-2026-06-08.json` — archived pre-Claude-5 corpus
- `benchmark.json` — graded results (per-task + overall + embedded answers)
- `../lib/grade_tasks.py` — grader (also `--edit-ab` compare mode)
- `EDIT-AB.md` — edit-level A/B protocol for contested skill trims/rewrites
