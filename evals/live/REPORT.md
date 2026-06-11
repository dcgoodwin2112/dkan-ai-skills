# Live-currency gate — skill docs vs a running DKAN site

The third enforced gate (env-gated): deterministic checks that the skill docs' factual claims
about the DKAN/MCP surface match a **running** DKAN dev site. `/check-skill-currency` verifies
pinned claims against upstream *docs*; this gate verifies them against the *system*. No LLM, no
tokens, no `claude -p` — it runs fine inside a Claude Code session and finishes in ~6s.

## Method

- **27 checks** (`checks.json`) in 4 groups, evaluated by `../lib/check_live.py` over probes
  that each run at most once per gate run:

| group | probes | checks |
|---|---|---|
| mcp_surface | `tools/list` as reader and writer (stdio) | tool counts, exact rosters, read-only annotations, ro/rw split, wire-safe names |
| metastore_schema | `list_schemas`, `get_schema(dataset)` | required fields, accessLevel enum, omitted POD fields, ISO-8601 accrualPeriodicity |
| site_posture | `get_site_status` + 3 curl probes | DKAN 4.x / Drupal 11, modules enabled, anon 401, RFC 9728 PRM + scopes, Basic rejected (403 / JSON-RPC -32002) |
| doc_tripwire | repo files (no site connection) | regexes guarding the claim text itself |

- **Strictly read-only.** The stdio transport is `ddev drush dkan-mcp-server:serve --user=…`;
  the writer session exists for `tools/list` only — the runner has no rw `tools/call` code path
  (grep-verifiable). HTTP probes: one anonymous POST, one optional Basic POST, one GET.
- **Ops vocabulary:** equals / count / contains / absent / subset / matches, plus three named
  checks in Python for cross-probe comparisons. An extraction path that stops resolving is an
  **error that fails the gate** — a check can never pass vacuously; `absent`/`subset`/`matches`
  additionally reject empty extractions. Doc negatives carry `neg_example`s with the scaffold
  gate's liveness rule (a regex that can't match its own example fails the gate as VACUOUS).
- **Skip/exit semantics:** `EVAL_DKAN_SITE_DIR` unset → clean SKIP, exit 0, nothing written.
  Configured but unreachable → exit 2 with the server's stderr tail and a ddev hint. Any check
  fail/error → exit 1. Provenance records a site fingerprint from `get_site_status`.

## Result (day one, 2026-06-11)

**22/27 pass — the 5 failures are the demonstration.** Every live check against the running
site passes; every failure is a doc tripwire catching real drift created on 2026-06-10, when
the site's MCP module (`dkan_mcp_server` 1.0.x) moved under the docs:

| failing tripwire | stale text | live truth (proven by) |
|---|---|---|
| doc_no_old_serve_cmd | `drush dkan-mcp:serve` (×3) | `dkan-mcp-server:serve` (the gate's own transport) |
| doc_no_35_tools | "~35 tools" | 38 (rw_tool_count) |
| doc_no_22_read | "22 read" (×2) | 25 (ro_tool_count) |
| doc_skill_no_35 | "~35 …tools" in SKILL.md | 38 (rw_tool_count) |
| doc_names_current_serve_cmd | current command unnamed | dkan-mcp-server:serve |

Each tripwire's expected value is justified by a sibling live check in the same run — the
pairing is the gate's core idea. The fix is a follow-up docs PR (which must also run
`bin/build-adapters`); this report's red snapshot stays committed as the discrimination
evidence, mirroring how the scaffold gate documents catching a deliberate break — except this
break is real.

## Discrimination (verified end-to-end)

- Setting `ro_tool_count` expected to 24 → exit 1 naming the check with expected-vs-actual.
- Corrupting a `neg_example` → the check fails as VACUOUS and negatives-live drops to 3/4.
- Fixing one stale doc line → `doc_names_current_serve_cmd` flips green while
  `doc_no_old_serve_cmd` correctly keeps failing on the two remaining occurrences.
- SKIP and unreachable paths leave `results.json` untouched (checksummed).

## Honest caveats

- **Snapshot of one pinned dev site** (`dkan_mcp_server` 1.0.x on the dkan-site DDEV project),
  not upstream truth. Counts like 25/38 will legitimately drift as the module evolves — that
  drift is the signal, but expect maintenance.
- **Auth checks are scoped to the MCP endpoint only** — deliberately silent on `/api/1/*`
  (whose basic_auth story is separate and still doc-accurate). Three shallow HTTP probes, not
  a security audit.
- **Deterministic ≠ frozen:** no LLM and stable given fixed site state, but the site is
  mutable, so results are dated snapshots, not byte-reproducible forever.
- The Basic-rejected pair needs `EVAL_DKAN_BASIC_PROBE` credentials and skips without them.

## Reproduce

```bash
export EVAL_DKAN_SITE_DIR=~/Sites/dkan-site          # DDEV checkout, ddev running
export EVAL_DKAN_BASIC_PROBE='user:pass'             # optional: Basic-rejected probes
bin/eval live                                        # or: python3 evals/lib/check_live.py
```

Unset `EVAL_DKAN_SITE_DIR` → SKIP (exit 0). Stopped ddev → exit 2 with a hint. Non-DDEV or
renamed setups: `EVAL_DKAN_MCP_CMD_RO/_RW`, `EVAL_DKAN_SITE_URL`, `EVAL_DKAN_MCP_HTTP_PATH`.

## Files

- `checks.json` — probe/op/expected check inventory (source of truth)
- `results.json` — committed day-one run (red by design; see Result)
- `../lib/check_live.py` — gate runner · `../lib/mcp_stdio.py` — stdio JSON-RPC client
- `../../bin/eval` — `live` subcommand
