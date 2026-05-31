# dkan-ai-skills

A Claude Code **plugin** of skills, slash commands, and reference docs for writing custom Drupal modules that extend [DKAN](https://github.com/GetDKAN/dkan) 4.x, the [Drupal AI module](https://www.drupal.org/project/ai) (`drupal/ai`, `ai_agents`), and the [MCP Server module](https://www.drupal.org/project/mcp_server) (`drupal/mcp_server`) — and for contributing to DKAN core itself.

Ships **no runtime PHP code** — it packages auto-loading skills and slash commands for Claude Code. The reference docs are verified against DKAN `4.x`, `drupal/ai 1.3.x`, and `mcp_server` v2.x-dev (pre-release; `mcp/sdk` 0.6 API).

Claude Code is the primary target, but the same content is also published as tool-neutral adapters (`AGENTS.md`, `.github/` for Copilot) so it works with other coding agents — see [Use with other agents](#use-with-other-agents-copilot-codex-cursor-).

## Layout

```
.claude-plugin/marketplace.json   # local marketplace listing the plugin
plugins/drupal-dkan-ai/            # CANONICAL SOURCE
  .claude-plugin/plugin.json       # plugin manifest
  skills/                          # auto-loading skills (SKILL.md + reference/)
  commands/                        # slash commands
AGENTS.md                          # generated: broad cross-tool guidance
.github/                           # generated: Copilot instructions + prompts
bin/build-adapters                 # regenerates AGENTS.md + .github/ from the source
bin/install, bin/test              # symlink installer (non-plugin setups) + test suite
```

The skills/commands under `plugins/drupal-dkan-ai/` are the single source of truth. `AGENTS.md` and `.github/` are **generated** by `bin/build-adapters` and committed; don't edit them by hand (`bin/test` fails if they drift from the source).

## Install (recommended: plugin marketplace)

Set up once, available across every project on the machine:

```bash
git clone https://github.com/dcgoodwin2112/dkan-ai-skills.git ~/src/dkan-ai-skills
claude plugin marketplace add ~/src/dkan-ai-skills
claude plugin install drupal-dkan-ai@dkan-ai-skills
```

Validate changes with `claude plugin validate ~/src/dkan-ai-skills/plugins/drupal-dkan-ai`.

**Updating:** Claude Code caches an installed plugin by version. After `git pull` (or local edits), bump `version` in `plugins/drupal-dkan-ai/.claude-plugin/plugin.json`, then `claude plugin update drupal-dkan-ai`. For quick local iteration without a version bump, force-refresh the cache:

```bash
claude plugin uninstall drupal-dkan-ai@dkan-ai-skills
claude plugin marketplace remove dkan-ai-skills && claude plugin marketplace add ~/src/dkan-ai-skills
claude plugin install drupal-dkan-ai@dkan-ai-skills
```

When installed as a plugin, skills auto-load by their `description` and commands are namespaced — e.g. `/drupal-dkan-ai:scaffold-dkan-module`.

## Install (fallback: symlinks)

For setups that don't use the plugin system, `bin/install` symlinks the skills/commands into a `.claude/` directory:

```bash
~/src/dkan-ai-skills/bin/install              # into $PWD/.claude (per-project)
~/src/dkan-ai-skills/bin/install ~/.claude    # into ~/.claude (all projects)
```

Re-running is safe: matching symlinks are left alone, stale ones repointed, non-symlink files skipped. `bin/test` exercises the installer. Commands installed this way are invoked without the plugin namespace (e.g. `/scaffold-dkan-module`).

## Use with other agents (Copilot, Codex, Cursor, …)

The same skills, reference docs, and scaffolding procedures are published as tool-neutral adapters, generated from the canonical source and committed at the repo root:

- **`AGENTS.md`** — read by Codex, Cursor, Gemini CLI, Aider, Zed, and other agents that honor the [AGENTS.md](https://agents.md) convention.
- **`.github/copilot-instructions.md`** — repo-wide GitHub Copilot instructions.
- **`.github/instructions/*.instructions.md`** — path-scoped Copilot instructions (`applyTo` globs) that auto-attach when editing DKAN/Drupal-AI module code.
- **`.github/prompts/*.prompt.md`** — the scaffolding commands as Copilot prompt files, invoked `/scaffold-dkan-module` etc.

The skill adapters are thin: they point at the canonical `reference/*.md` docs so those stay single-sourced.

**Working in this repo:** the adapters resolve as-is; any agent picks them up.

**Vendoring into your own Drupal project:** run the installer with `--adapters` from your project root:

```bash
~/src/dkan-ai-skills/bin/install --adapters
```

This symlinks the skills+commands under `.ai/dkan-ai-skills/` and writes `AGENTS.md` + `.github/` into the project with pointers rewritten to that vendored location. Existing non-generated files are never overwritten.

**Regenerating:** after editing any `SKILL.md` or command, run `bin/build-adapters` and commit the result (`bin/test` enforces this).

## Skills

Four auto-loading skills under `plugins/drupal-dkan-ai/skills/`:

- **`drupal-ai-module`** — loads when working with `drupal/ai`, `ai_agents`, or `ai_assistant_api`. Plugin-type decision tree, always-true rules, pitfalls, testing, and RAG. Note `drupal/ai 1.3.x` requires Drupal `^10.5 || ^11.2`.
- **`dkan-module-author`** — loads when editing files under `web/modules/custom/` or `docroot/modules/custom/`, or working with `Drupal\dkan_metastore\*`, `Drupal\dkan_datastore\*`, `Drupal\dkan_harvest\*`, or `Drupal\dkan_common\*` namespaces. Targets DKAN 4.x on Drupal `^10.2 || ^11`.
- **`dkan-core-contributor`** — loads when working *inside* DKAN core: editing the `drupal/dkan` package source (`modules/contrib/dkan/` or a `dkan/` checkout), changing `Drupal\dkan_*` core classes, or touching DKAN's tests/CI. Internals at modification depth (storage factories, schema validation, reference lifecycle, queues), the in-repo PHPUnit harness, and the contribution/CI workflow. For *using* DKAN from a custom module, use `dkan-module-author` instead. Targets DKAN 4.x (GitHub `GetDKAN/dkan`).
- **`drupal-mcp-server`** — loads when authoring `#[Tool]`/`#[ResourceProvider]`/prompt/notification plugins for the contrib `mcp_server` module, working with `Drupal\mcp_server\*` or `mcp/sdk`, or editing `dkan_mcp`. Extension-point decision table, the unenforced-`checkAccess` gotcha, and the DKAN MCP migration. Targets `mcp_server` v2.x-dev on the `mcp/sdk` 0.6 API — **pre-release and volatile**.

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

## Reference docs

### DKAN authoring (`plugins/drupal-dkan-ai/skills/dkan-module-author/reference/`)
- `dkan-overview.md` — architecture, data model, distributions/references/perspectives, data dictionaries
- `dkan-services.md` — service IDs, classes, method signatures for DI
- `dkan-api.md` — REST API endpoints and query DTO
- `dkan-workflows.md` — CSV import pipeline, event system, harvest ETL, publish flow
- `dkan-harvest.md` — authoring custom harvest extractors/transformers/loaders (ETL class-strings)
- `dkan-drush.md` — every DKAN drush command (datastore, harvest, metastore, sample content)
- `dkan-testing.md` — unit/kernel/functional patterns, mock-chain, standalone stubs
- `drupal-patterns.md` — Drupal 10/11 conventions (DI, render arrays, routing, custom entities)

### DKAN core contribution (`plugins/drupal-dkan-ai/skills/dkan-core-contributor/reference/`)
- `core-overview.md` — contributor orientation: package vs. built site, module tree, branches, the `getdkan/*` dependency surface
- `core-internals.md` — storage/factory indirection, schema validation, the reference lifecycle, queues/jobs
- `extending-core.md` — adding a built-in plugin (DatasetInfo, DkanApiDocs, ResourceProcessor), harvest ETL class, queue worker, or metastore schema
- `testing-core.md` — the in-repo PHPUnit harness (vs. the standalone one), base classes, DKAN traits, `@group`, Cypress, update-path fixtures
- `contributing-and-ci.md` — DDEV setup, phpcs/Qlty standards, update hooks, the CircleCI matrix, PR requirements

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
