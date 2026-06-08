# Phase 1 — Triggering eval

Measures whether each skill's `description` (the only thing the auto-loader sees) attracts
the right queries and resists sibling-domain near-misses — the highest-leverage risk for 7
skills with deliberately overlapping Drupal/DKAN domains.

## Two complementary methods

| Method | Tests | Runs where | Status |
|---|---|---|---|
| `run_eval.py` (vendored) via `bin/eval trigger` | Real `claude -p` triggering: does a description make Claude invoke the skill? (per-skill, in isolation) | Authenticated terminal / CI | Harness built. **Not runnable inside a sandboxed Claude Code agent session — nested `claude -p` gets HTTP 401** (host-managed OAuth isn't visible to child processes). Run it yourself. |
| In-session judge routing | Description *discriminability*: given all 7 name+descriptions, route each query to one skill or `none` | In-session subagents (have auth) | **Done — results below** |

## The eval set — `routing.json` (100 queries)

- 65 should-trigger (8–17 per skill), 35 hard near-misses (exactly 5 targeting each skill —
  shared vocabulary, true intent elsewhere), 6 `none`.
- Authored by 7 per-skill drafting agents (each given all 7 descriptions to craft tricky
  near-misses against its own skill), then consolidated and verified (ids sequential, all
  labels valid, queries unique).
- `lib/build_trigger_sets.py` derives the per-skill `run_eval` input sets (`sets/<skill>.json`)
  from it, so the master file stays the single source of truth.

## Results — in-session judge routing

Blind, forced single-choice routing over name+description only, two models for a robustness
gradient:

| Judge | Overall | Near-misses (35) |
|---|---|---|
| strong (session model) | **100/100** | 35/35 |
| weak (haiku) | **100/100** | 35/35 |
| inter-model agreement | **100/100** | — |

Both models — including a weak one — routed every query, including all 35 adversarial
near-misses, to the intended skill, with perfect agreement. The 7 descriptions carry enough
disambiguating signal (cross-references, namespace/path cues, explicit "for X see Y" pointers)
to be **text-separable**; no cross-skill description overlap was found. Artifact:
`results/judge_routing.json`.

## Honest interpretation — what this does and does NOT prove

- **Proves:** the descriptions are internally consistent and mutually distinct. A real failure
  mode for sibling skills — ambiguous/overlapping descriptions — was tested across 100 queries
  (35 adversarial) and not found, even under a weak router.
- **Partially circular:** the query labels were authored from the same descriptions the judge
  reads, so a high score chiefly confirms separability-*from-text*, not field behavior.
- **Cannot show:** real-world *under*-triggering (a user phrasing that matches no description),
  the documented "too-simple-to-trigger" effect, or actual `Skill`-tool invocation rates.
- **So:** read 100% as "descriptions are clean / non-overlapping," not "triggering is solved."
  The decisive *triggering* number is `bin/eval trigger` in an authed env; the decisive
  *effectiveness* number is Phase 2 (task outcomes, which is non-circular).

## Run the real triggering eval yourself

In a normal, authenticated `claude login` terminal (NOT inside an agent session):

```bash
bin/eval trigger                 # all 7 skills
bin/eval trigger open-data-dcat  # one skill
# knobs: EVAL_RUNS=3 EVAL_WORKERS=6 EVAL_TIMEOUT=45 EVAL_MODEL=<id>
```

Each skill runs hermetically (throwaway temp project root) and lean (`--strict-mcp-config`,
no MCP startup). Output: `results/<skill>.run_eval.json` (gitignored — run-specific).

## Files

- `routing.json` — master labeled set (source of truth)
- `lib/{run_eval.py,utils.py}` — vendored harness (see `lib/PROVENANCE.md`)
- `lib/build_trigger_sets.py` — derives per-skill sets
- `results/judge_routing.json` — committed in-session judge artifact (predictions + provenance + caveats)
- `sets/`, `_judge_input.json`, `results/*.run_eval.json` — derived/per-run (gitignored)
