# dkan-ai-skills

A Claude Code **plugin** of skills, slash commands, a review subagent, and reference docs for general Drupal 10.2+ / 11 module development and for writing custom Drupal modules that extend [DKAN](https://github.com/GetDKAN/dkan) 4.x, the [Drupal AI module](https://www.drupal.org/project/ai) (`drupal/ai`, `ai_agents`), and the [MCP Server module](https://www.drupal.org/project/mcp_server) (`drupal/mcp_server`) — for contributing to DKAN core itself, for the open-data metadata specs (DCAT-US / Project Open Data) DKAN implements, and for DKAN's decoupled JavaScript frontend.

Ships **no runtime PHP code** — it packages auto-loading skills, slash commands, a review subagent, and commit-gate + dependency-gate hooks for Claude Code. The reference docs are verified against DKAN `4.x`, `drupal/ai 1.3.x`, and `mcp_server` v2.x-dev (pre-release; `mcp/sdk` 0.6 API).

Claude Code is the primary target, but the same content is also published as tool-neutral adapters (`AGENTS.md`, `.github/` for Copilot) so it works with other coding agents — see [Use with other agents](#use-with-other-agents-copilot-codex-cursor-).

## Development workflow

These skills, commands, and the bundled reviewer agent plug into a repeatable, phased development loop — empirical baseline, plan doc + independent plan review, scoped branch-per-phase PRs with independent diff review (the `plan-diff-reviewer` subagent, plus an adversarial pass when confidence is low), then `/goal`-driven doc cleanup. See **[WORKFLOW.md](WORKFLOW.md)** for the full process, written generically enough to lift to other projects.

## Layout

```
.claude-plugin/marketplace.json   # local marketplace listing the plugin
plugins/drupal-dkan-ai/            # CANONICAL SOURCE
  .claude-plugin/plugin.json       # plugin manifest
  skills/                          # auto-loading skills (SKILL.md + reference/)
  commands/                        # slash commands
  agents/                          # review subagents (plan-diff-reviewer)
  hooks/                           # commit-gate + dependency-gate hooks (PreToolUse)
AGENTS.md                          # generated: broad cross-tool guidance
.github/                           # generated: Copilot instructions + prompts
bin/build-adapters                 # regenerates AGENTS.md + .github/ from the source
bin/install, bin/test              # symlink installer (non-plugin setups) + test suite
skills-currency.yml                # version facts each skill pins + sources to verify
.claude/commands/                  # repo-maintenance commands (not shipped in the plugin)
```

The skills/commands under `plugins/drupal-dkan-ai/` are the single source of truth. `AGENTS.md` and `.github/` are **generated** by `bin/build-adapters` and committed; don't edit them by hand (`bin/test` fails if they drift from the source).

## Install (recommended: plugin marketplace)

Set up once, available across every project on the machine:

```bash
git clone https://github.com/dcgoodwin2112/dkan-ai-skills.git ~/src/dkan-ai-skills
claude plugin marketplace add ~/src/dkan-ai-skills
claude plugin install drupal-dkan-ai@dkan-ai-skills
```

The clone is a standalone tooling checkout — keep it anywhere outside your Drupal projects (the example uses `~/src/dkan-ai-skills`; substitute your own path). The marketplace registers it by absolute path and installs machine-wide, so it adds **nothing** to your Drupal site and is available in every project you open.

Validate changes with `claude plugin validate ~/src/dkan-ai-skills/plugins/drupal-dkan-ai`.

**Updating:** Claude Code caches an installed plugin by version. After `git pull` (or local edits), bump `version` in `plugins/drupal-dkan-ai/.claude-plugin/plugin.json`, then refresh the marketplace and update by the **marketplace-qualified** name:

```bash
claude plugin marketplace update dkan-ai-skills      # re-read the local marketplace
claude plugin update drupal-dkan-ai@dkan-ai-skills   # the @dkan-ai-skills suffix is required (bare name errors "not found")
claude plugin list                                   # verify the new version is installed
```

Restart Claude Code to apply, or run `/reload-plugins` in the CLI to reload without restarting (not available in Desktop — see below). For quick local iteration without a version bump, force-refresh the cache:

```bash
claude plugin uninstall drupal-dkan-ai@dkan-ai-skills
claude plugin marketplace remove dkan-ai-skills && claude plugin marketplace add ~/src/dkan-ai-skills
claude plugin install drupal-dkan-ai@dkan-ai-skills
```

**Refreshing in Claude Desktop:** the `/plugin` and `/reload-plugins` commands are not available in the desktop app, and `/reload-skills` reloads only skills (not agents or hooks). Run the CLI update above, then **fully quit and reopen Desktop** to load new agents and hooks — a new conversation alone may not pick them up ([claude-code#52967](https://github.com/anthropics/claude-code/issues/52967)).

When installed as a plugin, skills auto-load by their `description`, commands are namespaced — e.g. `/drupal-dkan-ai:scaffold-dkan-module` — and agents are invoked as `@agent-drupal-dkan-ai:plan-diff-reviewer`.

## Install (fallback: symlinks)

For setups that don't use the plugin system, `bin/install` symlinks the skills/commands into a `.claude/` directory (using absolute paths back to the checkout, so the checkout can live anywhere):

```bash
~/src/dkan-ai-skills/bin/install              # into $PWD/.claude (per-project)
~/src/dkan-ai-skills/bin/install ~/.claude    # into ~/.claude (all projects)
```

For a Drupal site, run the per-project form from the site's **Composer root** — the directory containing `composer.json`, above `docroot/`/`web/` — so `.claude/` lands at the project root where Claude Code looks for it, not inside the web root.

Re-running is safe: matching symlinks are left alone, stale ones repointed, non-symlink files skipped. `bin/test` exercises the installer. Commands installed this way are invoked without the plugin namespace (e.g. `/scaffold-dkan-module`).

## Use with other agents (Copilot, Codex, Cursor, …)

The same skills, reference docs, and scaffolding procedures are published as tool-neutral adapters, generated from the canonical source and committed at the repo root:

- **`AGENTS.md`** — read by Codex, Cursor, Gemini CLI, Aider, Zed, and other agents that honor the [AGENTS.md](https://agents.md) convention.
- **`.github/copilot-instructions.md`** — repo-wide GitHub Copilot instructions.
- **`.github/instructions/*.instructions.md`** — path-scoped Copilot instructions (`applyTo` globs) that auto-attach when editing DKAN/Drupal-AI module code.
- **`.github/prompts/*.prompt.md`** — the scaffolding commands as Copilot prompt files, invoked `/scaffold-dkan-module` etc.

The skill adapters are thin: they point at the canonical `reference/*.md` docs so those stay single-sourced.

**Working in this repo:** the adapters resolve as-is; any agent picks them up.

**Vendoring into your own Drupal project:** run the installer with `--adapters` from your Drupal project's **Composer root** (the directory with `composer.json`, not `docroot/`/`web/`):

```bash
cd /path/to/your-drupal-site        # the Composer root
~/src/dkan-ai-skills/bin/install --adapters
```

This symlinks the skills+commands under `.ai/dkan-ai-skills/` and writes `AGENTS.md` + `.github/` into the current directory, with pointers rewritten to that vendored location. Run it from the Composer root so those files sit at the project root where agents look for them. Existing non-generated files are never overwritten.

**Regenerating:** after editing any `SKILL.md` or command, run `bin/build-adapters` and commit the result (`bin/test` enforces this).

## Skills

Seven auto-loading skills under `plugins/drupal-dkan-ai/skills/`:

- **`drupal-module-dev`** — loads when writing or modifying any custom/contrib Drupal module: `.module`/`.install`/`*.info.yml`/`*.services.yml`/`*.routing.yml`, plugins, forms, controllers, hooks (`src/Hook/`), events, entities, config schema, or module tests, or asking about Drupal 10/11 APIs/conventions/deprecations. The general Drupal foundation layer (DI, `#[Hook]`, plugin attributes vs annotations, config validation, `hook_update_N` vs `post_update`, PHPUnit base classes) the DKAN/AI/MCP skills build on. Targets Drupal `^10.2 || ^11`.
- **`drupal-ai-module`** — loads when working with `drupal/ai`, `ai_agents`, or `ai_assistant_api`. Plugin-type decision tree, always-true rules, pitfalls, testing, and RAG. Note `drupal/ai 1.3.x` requires Drupal `^10.5 || ^11.2`.
- **`dkan-module-author`** — loads when editing files under `web/modules/custom/` or `docroot/modules/custom/`, or working with `Drupal\dkan_metastore\*`, `Drupal\dkan_datastore\*`, `Drupal\dkan_harvest\*`, or `Drupal\dkan_common\*` namespaces. Targets DKAN 4.x on Drupal `^10.2 || ^11`.
- **`dkan-core-contributor`** — loads when working *inside* DKAN core: editing the `drupal/dkan` package source (`modules/contrib/dkan/` or a `dkan/` checkout), changing `Drupal\dkan_*` core classes, or touching DKAN's tests/CI. Internals at modification depth (storage factories, schema validation, reference lifecycle, queues), the in-repo PHPUnit harness, and the contribution/CI workflow. For *using* DKAN from a custom module, use `dkan-module-author` instead. Targets DKAN 4.x (GitHub `GetDKAN/dkan`).
- **`open-data-dcat`** — loads when working with dataset/distribution metadata, `schema/collections/*.json`, or a `data.json` catalog, or asking what a metadata field means or its allowed values. The DCAT-US / Project Open Data v1.1 spec DKAN implements: required fields, vocabularies (`accessLevel`, `accrualPeriodicity`), `downloadURL` vs `accessURL`, the `data.json` catalog and harvest sources. The domain layer beneath the DKAN code skills; pairs with `/validate-dcat-metadata`.
- **`drupal-mcp-server`** — loads when authoring `#[Tool]`/`#[ResourceProvider]`/prompt/notification plugins for the contrib `mcp_server` module, working with `Drupal\mcp_server\*` or `mcp/sdk`, or editing `dkan_mcp`. Extension-point decision table, the unenforced-`checkAccess` gotcha, and the DKAN MCP migration. Targets `mcp_server` v2.x-dev on the `mcp/sdk` 0.6 API — **pre-release and volatile**.
- **`dkan-frontend`** — loads when working with DKAN's decoupled JavaScript frontend: the `dkan_js_frontend` Drupal module or its `dkan_js_frontend.config`, the React app served from the docroot `/frontend` (`data-catalog-app`), a DKAN React component library (`cmsds-open-data-components` / `data-catalog-components`), or the ddev frontend install/build commands. The integration/architecture layer — how Drupal serves the SPA, the config-driven routes, the `datastore_query_api` switch, the two library lineages — cross-referencing the component library's own `agent-docs/` for component detail.

Example paths in the docs use `<webroot>/modules/...`; substitute your Drupal web root (`docroot/` in DKAN's recommended-project, `web/` elsewhere).

## Slash commands

### Scaffolding
| Command | Generates |
|---|---|
| `/scaffold-dkan-module <name>` | Complete DKAN 4.x module skeleton — info.yml (correct `dkan:dkan_*` deps), services.yml, composer.json, optional standalone test harness |
| `/dkan-core-test <module> <ClassName> [--type unit\|kernel\|functional]` | In-repo PHPUnit test for DKAN **core** — correct suite + base class (`Api1TestBase`/kernel/unit), DKAN traits (`QueueRunnerTrait`), and `@group dkan`/`functionalN` so it runs in CI |
| `/ai-scaffold-provider <module> <ProviderName>` | AI Provider plugin (LLM backend) — class, settings form, route, `api_defaults.yml`, deps, schema, test stub |
| `/ai-scaffold-tool <module> <ToolName>` | FunctionCall plugin (AI tool) — class with attribute and `execute()`/`setOutput()` stubs, test stub |
| `/ai-scaffold-agent <module> <AgentName>` | AiAgent plugin — `parent::create()` pattern, lifecycle stubs, YAML prompt dir, test stub |
| `/ai-scaffold-action <module> <ActionName>` | AiAssistantAction plugin extending `AiAssistantActionBase` |
| `/mcp-scaffold-tool <module> <ToolName> [--write]` | MCP Server `#[Tool]` plugin — attribute (schema + annotations), `create()` DI, `execute(array, ClientGateway)` + `defaultConfiguration()` stubs, optional `checkAccess()` gate, test stub |
| `/scaffold-drupal-service <module> <ServiceName>` | Drupal service with DI, `services.yml` entry, unit test |
| `/add-event-subscriber <module> [event]` | EventSubscriber for a DKAN/Drupal event, tagged in `services.yml` |
| `/add-drupal-route <module> <path> [perm]` | Route + controller + permission entry |

The AI scaffold commands target Drupal AI `^1.3` and refuse `2.0.x` (breaking provider lifecycle changes). `/mcp-scaffold-tool` targets `mcp_server` v2.x-dev on the `mcp/sdk` 0.6 API and version-gates before scaffolding.

### Validation
| Command | Runs |
|---|---|
| `/validate-module <module>` | phpcs, phpunit, permission audit, cache rebuild |
| `/validate-dcat-metadata <path-or-uuid>` | Checks dataset/distribution JSON against DCAT-US / POD v1.1 — required fields, `accessLevel`/`accrualPeriodicity` enums, URI/date formats, `contactPoint`/`publisher` shape; reports violations + fixes |

## Hooks

The plugin ships `PreToolUse` hooks (`plugins/drupal-dkan-ai/hooks/`) that make the local quality gates **deterministic** (Anthropic's verification ladder — *CLAUDE.md is advisory, hooks are deterministic*). They are fast local feedback; CI stays the authoritative gate. Both activate after `claude plugin update drupal-dkan-ai` and a **new session** (hooks load at session start), and ship via the plugin install path only, not the `bin/install` symlink fallback. Inspect/disable with `/hooks` or override in a project's `.claude/settings.local.json`; trace either with `CLAUDE_GATE_DEBUG=1`.

### commit-gate

Before any `git commit`, runs the committing module's phpcs + unit suite via DDEV and **blocks the commit if they fail**. Because plugin hooks fire in every project, the script is **self-scoping**: it no-ops unless the commit targets a DDEV-backed module carrying `phpcs.xml.dist` and/or `phpunit.xml`. Kernel/integration tests are left to CI.

- **DDEV not running →** warns and allows the commit (infra never hard-blocks).
- **Bypass** an intentional WIP commit with `CLAUDE_SKIP_COMMIT_GATE=1`.

### dependency-gate

Before a command that **adds a named package** — `composer require`, `npm install <pkg>` / `npm add`, `yarn add`, `pnpm add`, `bun add`, `pip install <pkg>`, `uv add` / `uv pip install <pkg>`, `poetry add`, `pipx install`, and the common `cargo`/`go`/`gem`/`deno` equivalents — **blocks** so a human vets the package first. This guards against **slopsquatting**: LLMs hallucinate plausible-but-nonexistent package names (~1 in 5 suggested packages) and attackers pre-register them. Supply-chain risk is universal, so this gate is **not** project-scoped.

- Lockfile-driven installs (`composer install`, bare `npm install`, `npm ci`, `yarn install`, `pip install -r …`, `pip install -e .`) are **not** gated — they add nothing unreviewed.
- **Bypass** with `CLAUDE_SKIP_DEP_GATE=1`; preview a command's verdict with `CLAUDE_GATE_DRYRUN=1`.

## Reviewer subagent

The plugin ships a read-only review subagent, **`plan-diff-reviewer`**, that checks a code change against the plan it implements: every planned requirement present, nothing out of scope, plus correctness gaps. It reports **gaps, not style** (phpcs and the external reviewer own lint) and respects a repo's declined-style norms (e.g. accepted em dashes).

Hand it the **diff** and the **plan** (inline or as paths) and invoke it by name — `@agent-drupal-dkan-ai:plan-diff-reviewer` — or let it auto-delegate from its description. It has `Read`/`Grep`/`Glob` only (no shell, no edits), so it is read-only at the tool boundary and treats the diff and plan as untrusted data — it never acts on instructions embedded in what it reviews. Output is fixed: Implemented / Missing-or-partial / Out-of-scope / Correctness concerns / Verdict.

This is the fresh-context reviewer in [WORKFLOW.md](WORKFLOW.md) §8–§9 — complementary to the external codex `review_diff` / `plan_vs_diff`, and usable as one model-diverse lens in the §9 adversarial panel. Shipped via the plugin install path only (not the `bin/install` symlink fallback); available after `claude plugin update drupal-dkan-ai` and a new session.

## Reference docs

### Drupal module development (`plugins/drupal-dkan-ai/skills/drupal-module-dev/reference/`)
- `services-and-di.md` — dependency injection, `services.yml`, autowiring, logging, string translation, Drush commands
- `hooks-events-plugins.md` — OOP `#[Hook]` + `#[LegacyHook]`, event subscribers, plugin attribute discovery and the annotation deprecation timeline
- `routing-forms-rendering.md` — routes + access, Form API, render arrays/cacheability, theming/libraries
- `config-and-entities.md` — Config API, config schema + `FullyValidatable`, content vs config entity definitions
- `module-lifecycle.md` — `*.info.yml`, `hook_update_N` vs `hook_post_update_NAME`, the requirements split, recipes/config actions
- `testing-and-standards.md` — PHPUnit base classes, kernel test setup, strict config schema, deprecation testing, phpcs/phpstan

### DKAN authoring (`plugins/drupal-dkan-ai/skills/dkan-module-author/reference/`)
- `dkan-overview.md` — architecture, data model, distributions/references/perspectives, data dictionaries
- `dkan-services.md` — service IDs, classes, method signatures for DI
- `dkan-api.md` — REST API endpoints and query DTO
- `dkan-workflows.md` — CSV import pipeline, event system, harvest ETL, publish flow
- `dkan-harvest.md` — authoring custom harvest extractors/transformers/loaders (ETL class-strings)
- `dkan-drush.md` — every DKAN drush command (datastore, harvest, metastore, sample content)
- `dkan-diagnostics.md` — operational diagnostics: watchdog logs, stuck queues, permission misconfig, the `dkan_mcp` status tools
- `dkan-testing.md` — unit/kernel/functional patterns, mock-chain, standalone stubs

### DKAN core contribution (`plugins/drupal-dkan-ai/skills/dkan-core-contributor/reference/`)
- `core-overview.md` — contributor orientation: package vs. built site, module tree, branches, the `getdkan/*` dependency surface
- `core-internals.md` — storage/factory indirection, schema validation, the reference lifecycle, queues/jobs
- `extending-core.md` — adding a built-in plugin (DatasetInfo, DkanApiDocs, ResourceProcessor), harvest ETL class, queue worker, or metastore schema
- `testing-core.md` — the in-repo PHPUnit harness (vs. the standalone one), base classes, DKAN traits, `@group`, Cypress, update-path fixtures
- `contributing-and-ci.md` — DDEV setup, phpcs/Qlty standards, update hooks, the CircleCI matrix, PR requirements

### Open data / DCAT-US (`plugins/drupal-dkan-ai/skills/open-data-dcat/reference/`)
- `dcat-us-overview.md` — the DCAT-US / POD v1.1 spec, the catalog→dataset→distribution model, how it maps to DKAN
- `dataset-fields.md` — every dataset field (required/recommended/optional), vocabularies, the POD fields DKAN omits
- `distributions-and-resources.md` — the distribution object, `downloadURL` vs `accessURL`, datastore resources, data dictionaries
- `catalog-harvest-interop.md` — the `data.json` catalog, DKAN's `/data.json` export, harvest sources, federal compliance

### Drupal AI (`plugins/drupal-dkan-ai/skills/drupal-ai-module/reference/`)
- `plugin-types.md` — base classes, attributes, required methods, paths per plugin type
- `services.md` — service IDs, classes, key methods
- `pitfalls.md` — failure modes with symptoms, causes, fixes
- `testing-ai-plugins.md` — unit-testing tools, asserting tool dispatch, golden-case eval, mocking `ai.provider`
- `ai-search-rag.md` — RAG, embeddings, VdbProvider authoring, ai_search Search API backend
- Upstream docs: https://project.pages.drupalcode.org/ai/

### MCP Server (`plugins/drupal-dkan-ai/skills/drupal-mcp-server/reference/`)
- `mcp-overview.md` — architecture (SDK bridge + Drupal plugins/config entities), extension-point map, transports, submodules, version landscape
- `tool-plugins.md` — `#[Tool]` attribute, `ToolPluginBase`, `execute(array, ClientGateway)`, `ToolDefinition`, derivers, schemas, enablement
- `resources-prompts-notifications.md` — resource providers/templates, `McpPromptConfig` + completion providers, notification stub
- `auth-and-access.md` — `RequestEvent` gating, `McpAuthorizationDeniedException`, the unenforced-`checkAccess` gotcha, OAuth submodule, CORS, sessions
- `dkan-integration.md` — `dkan_mcp` today vs. the `mcp_server`-based target, tool mapping, permission model, client config
- `testing.md` — what to test (and not), unit + kernel patterns, standalone stubs
- Upstream: https://www.drupal.org/project/mcp_server (GitLab issues/MRs — use `glab`)

### DKAN frontend (`plugins/drupal-dkan-ai/skills/dkan-frontend/reference/`)
- `architecture.md` — the three pieces (Drupal module, React app, component library), the data path, the two library lineages
- `dkan-js-frontend-module.md` — the Drupal serving contract: `dkan_js_frontend.config`, config-driven routing, the Page controller, the SPA-as-frontend setup
- `build-deploy-customize.md` — ddev install/build, the `extra.dkan-frontend` override, the `datastore_query_api` switch, local-dev version drift, customizing

## Maintaining the skills (currency)

The skills pin version-specific facts about fast-moving upstreams (Drupal core 10.2→11.x, `drupal/ai`, `mcp_server`/`mcp/sdk`, DKAN 4.x, the frontend libraries, DCAT-US). To keep them from drifting:

- **`skills-currency.yml`** — the manifest of every pinned claim, the authoritative source to verify it against, and a `cadence`/`volatility`/`last_verified` per claim. Centralizes facts otherwise scattered across each `SKILL.md` "Version notes". Update it when you add or change a skill.
- **`/check-skill-currency`** (`.claude/commands/`) — run in this repo to verify the manifest against upstream sources and get a drift-triage report. Report-only by default; `--write` bumps `last_verified` and applies confident, mechanical fixes. Scope by skill and `--cadence` (e.g. `monthly`).

The command is report-first by design — doc judgment calls stay with a human reviewer. It can be wired to a monthly scheduled run (Claude Code's `/schedule`, or a GitHub Actions cron) that runs the check and opens an issue/PR with findings, but that trigger is intentionally not committed here.
