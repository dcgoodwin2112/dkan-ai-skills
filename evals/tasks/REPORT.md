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

## Result

| | passed | rate |
|---|---|---|
| **with skill** | 20/21 | **95%** |
| **baseline (no skill)** | 7/21 | **33%** |
| **delta** | | **+62 pts** |

*(Regraded 2026-07-08 after recalibrating T3, whose original alternation never
discriminated — see the T3 note in `tasks.json` and "Grader calibration" below.)*

**Consistency & variance (3 runs/arm).** A pooled rate hides whether the skill helps on *every*
run or just *some*:

| metric | with skill | baseline |
|---|---|---|
| pass^3 — tasks passing on **all 3** runs | **6/7** | 2/7 |
| pass@3 — tasks passing on **any** run | 7/7 | 3/7 |
| per-run pass rate (mean ± stddev) | 95% ± 8% | 33% ± 8% |

Baseline's pass@3 (3/7) exceeds its pass^3 (2/7) because task 4 passes only 1 of 3
runs; with-skill's single miss is T3 run 1 (a hedged answer giving both the correct
and the pre-4.x class namespace — graded a fail, honestly). **Normalized gain
g = 0.93** (Hake's g = (r_skill − r_base) / (1 − r_base) — the skill closes 93% of
the achievable gap, not just +62 raw points).

| # | skill | with | base | result |
|---|---|---|---|---|
| 1 | drupal-module-dev | 3/3 | 3/3 | — tie |
| 2 | drupal-ai-module | 3/3 | 0/3 | ✅ skill wins |
| 3 | dkan-module-author | 2/3 | 0/3 | ✅ skill wins |
| 4 | dkan-core-contributor | 3/3 | 1/3 | ✅ skill wins |
| 5 | open-data-dcat | 3/3 | 3/3 | — tie |
| 6 | drupal-mcp-server | 3/3 | 0/3 | ✅ skill wins |
| 7 | dkan-frontend | 3/3 | 0/3 | ✅ skill wins |

**5 of 7 tasks discriminate** — on that drift-prone subset the contrast is **14/15 vs
1/15 (+87pp)**; the 2 ties dilute the pooled headline. On the discriminating tasks
baseline didn't just score lower — it produced confident, **plausible-but-wrong**
answers (the failure mode the skills exist to prevent):

| task | correct (with skill) | baseline hallucinated |
|---|---|---|
| 2 drupal/ai core floor | `^10.5 \|\| ^11.2` | `^10.3 \|\| ^11` (all 3 runs) |
| 3 metastore class | `Drupal\dkan_metastore\MetastoreService` | `Drupal\metastore\MetastoreService` — the pre-4.x namespace (all 3 runs) |
| 4 DKAN CI groups | `functional1/2/3` | `@group functional`, `btb` (2/3 runs) |
| 6 MCP write tool | `#[Tool]` + `ClientGateway` + `checkAccess` | `ToolBase` + `CallToolResult` (wrong/older mcp/sdk API; no access gate) |
| 7 frontend config key | `datastore_query_api` | `datastore_query_version`, `root_url`, "not sure" |

The 2 **ties** are honest: they're facts the base model already knows (the requirements
split, `R/P3M`). The skill's value concentrates exactly where parametric knowledge is
stale or absent.

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
  also (correctly) fails one hedged with-skill run. See `tasks.json` notes.

## Reproduce

```bash
python3 evals/lib/grade_tasks.py        # re-grade runs/raw_runs.json -> benchmark.json
```
To collect fresh runs, re-run the paired subagents over `tasks.json` (in-session; the grading
step is deterministic).

## Files

- `tasks.json` — corpus + deterministic assertions (source of truth)
- `runs/raw_runs.json` — recorded paired runs (3/arm)
- `benchmark.json` — graded results (per-task + overall + embedded answers)
- `../lib/grade_tasks.py` — grader
