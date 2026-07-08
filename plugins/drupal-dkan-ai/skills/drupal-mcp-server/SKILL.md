---
name: drupal-mcp-server
description: Reference and decision support for writing custom modules that extend the contrib MCP Server module (drupal/mcp_server) — the bridge that exposes Drupal/DKAN capabilities to AI assistants over the Model Context Protocol (mcp/sdk). Loads when authoring #[Tool], #[ResourceProvider], #[ResourceTemplateProvider], #[PromptArgumentCompletionProvider], or #[Notification] plugins; working with Drupal\mcp_server\* namespaces, the mcp/sdk, or RequestEvent authorization; or editing under modules/contrib/mcp_server or a module that depends on mcp_server:mcp_server (including DKAN's dkan_mcp_server). Targets mcp_server v2.x-dev on the mcp/sdk 0.6 API (0.6.0 tagged 2026-06-02) — pre-release and volatile.
---

# MCP Server Module — Plugin Author's Reference

This skill loads when you're extending the contrib `mcp_server` module — turning
Drupal/DKAN capabilities into MCP tools, resources, and prompts that AI clients
call. It covers the extension points, when to reach for each, the always-true
rules, and the pitfalls that bite. Detail lives in
[reference/mcp-overview.md](reference/mcp-overview.md),
[reference/tool-plugins.md](reference/tool-plugins.md),
[reference/resources-prompts-notifications.md](reference/resources-prompts-notifications.md),
[reference/auth-and-access.md](reference/auth-and-access.md),
[reference/dkan-integration.md](reference/dkan-integration.md), and
[reference/testing.md](reference/testing.md).

For scaffolding a tool plugin, use `/mcp-scaffold-tool`.

> **Path convention**: example paths use `<webroot>/modules/...`, relative to the
> Drupal web root (`docroot/` in DKAN's recommended-project, `web/` elsewhere).
> Substitute your project's actual root; confirm with `ls` if unsure.

## ⚠️ Version volatility — verify before you trust any API

`mcp_server` is **pre-release** and rides a **pre-1.0, BC-breaking SDK**. This is
the single biggest hazard; treat every API below as version-contingent.

- The module's `v2.x-dev` branch requires **`mcp/sdk: ^0.6`** (the 0.6 API):
  `Mcp\Server\Handler\ToolHandlerInterface`, `Mcp\Server\ClientGateway`,
  `Builder::add()`. `mcp/sdk` broke BC twice across 0.4 → 0.5 → 0.6, but **`0.6.0`
  was tagged 2026-06-02**, so the module now pins a released SDK (`^0.6`) rather
  than `dev-main`. `mcp/sdk` is the official MCP PHP SDK
  (`modelcontextprotocol/php-sdk`, a PHP Foundation + Symfony collaboration).
- The earlier `0.4`/`0.5` API (`Builder::addTool()`, no `ClientGateway`) is
  **incompatible** — code written against it will not load against `0.6`.
- **The module's own bundled `references/` can lag its code** (e.g.
  `references/sdk/index.md` still says "`mcp/sdk ^0.4.0`" while the source imports
  0.6-only classes). Trust the **source + `composer.json`** over prose.
- **`mcp_server` core has no Drupal module dependencies** — only `php` + `mcp/sdk`
  + `psr/simple-cache` at the Composer level. OAuth, admin UI, and the `drupal/tool`
  bridge are separate companion projects (extracted from in-tree submodules
  2026-06-09; see below).
- First tag: `2.0.0-alpha1` (2026-06-11) — still pre-stable. Per its maintainer:
  *add no backwards-compatibility layers or migrations in your solutions.*

Always confirm the installed reality before relying on a signature:

```bash
composer show drupal/mcp_server mcp/sdk            # installed branch/version
ls <webroot>/modules/contrib/mcp_server/src/Plugin # confirm the plugin classes exist
```

If `mcp/sdk` resolves to `0.4`/`0.5` but `mcp_server` is on `2.x`, the module
references SDK classes that **are not installed** and will fatal — bump the SDK
or pin the module to a matching branch first. (This was `dkan-site`'s state
before its 2026-06 migration; see
[dkan-integration.md](reference/dkan-integration.md).)

## When to use which extension point

| The user wants… | Extension point | Path / discovery | Detail |
|---|---|---|---|
| Let an AI client *do* something (run a query, mutate an entity, call a service) | **Tool plugin** | `#[Tool]` under `src/Plugin/Tool/` | [tool-plugins.md](reference/tool-plugins.md) |
| Expose a fixed set of readable artifacts at concrete URIs (`resources/list`) | **ResourceProvider** | `#[ResourceProvider]` under `src/Plugin/ResourceProvider/` | [resources-prompts-notifications.md#resource-providers](reference/resources-prompts-notifications.md#resource-providers) |
| Expose a *family* of resources via a parameterized URI template (`resources/templates/list`) | **ResourceTemplateProvider** | `#[ResourceTemplateProvider]` under `src/Plugin/ResourceTemplateProvider/` | [resources-prompts-notifications.md#resource-templates](reference/resources-prompts-notifications.md#resource-templates) |
| Ship a reusable prompt (templated messages + arguments) | **`McpPromptConfig`** config entity | `mcp_server_ui` admin UI / config | [resources-prompts-notifications.md#prompts](reference/resources-prompts-notifications.md#prompts) |
| Autocomplete a prompt argument's values | **PromptArgumentCompletionProvider** | `#[PromptArgumentCompletionProvider]` under `src/Plugin/PromptArgumentCompletionProvider/` | [resources-prompts-notifications.md#completion-providers](reference/resources-prompts-notifications.md#completion-providers) |
| Declare server-emitted notifications | **NotificationProvider** | `#[Notification]` under `src/Plugin/Notification/` | [resources-prompts-notifications.md#notifications](reference/resources-prompts-notifications.md#notifications) — **stub only, not yet wired** |
| Gate who may call a tool / read a resource | **`RequestEvent` subscriber** | `event_subscriber` service | [auth-and-access.md](reference/auth-and-access.md) |
| Expose an existing `drupal/tool` (Tool API) tool over MCP **without writing a plugin** | **`mcp_server_tool_bridge`** companion project | `McpToolConfig` entity (admin UI) | [mcp-overview.md#companion-projects](reference/mcp-overview.md#companion-projects) |
| Just *call* the MCP server from a client | client config, no plugin | — | [mcp-overview.md#transports](reference/mcp-overview.md#transports) |

Most work is **Tool plugins**. Reach for resources/prompts only when the client
should *read* artifacts or *reuse* prompt templates rather than invoke actions.

## Always-true rules

1. **Run `drush cr` after adding or changing a plugin.** `#[Tool]`/`#[ResourceProvider]`/etc. discovery is attribute-cached (e.g. cache backend `mcp_server_tool_plugins`, tag `mcp_server:tools`). New plugins are invisible until rebuild. `/mcp-scaffold-tool` runs it for you.
2. **Native plugins must opt themselves in.** `ToolPluginBase::isEnabled()` reads `configuration['enabled']`, default **FALSE**. A code-defined (native) tool must override `defaultConfiguration()` to return `['enabled' => TRUE]` or it never registers. (Config-entity-backed resources/prompts enable via their config instead.)
3. **`checkAccess()` is declared but NOT auto-enforced on `tools/call`.** Core ships **zero** auth policy; overriding `checkAccess()` alone does nothing. To enforce it you must add a subscriber on the SDK's `Mcp\Event\RequestEvent` (or enable `mcp_server_oauth`). See [auth-and-access.md](reference/auth-and-access.md) — this is the #1 gotcha.
4. **Derivative IDs use `.`, never `:`.** The MCP `NameValidator` rejects `:` in wire names; `mcp_server` swaps the core `base:derivative` separator to `base.derivative` on wire-exposed managers. `ToolPluginBase::DERIVATIVE_SEPARATOR` is already `.` — emit `.` from your deriver.
5. **The handler signature is `execute(array $arguments, ClientGateway $gateway): mixed`** (0.6 API, from the SDK's `ToolHandlerInterface`). It is **not** on `ToolPluginBase` — you implement it. The `$gateway` (`Mcp\Server\ClientGateway`) is how a tool requests client sampling.
6. **Schemas live in the `#[Tool]` attribute.** `inputSchema:` / `outputSchema:` on the attribute take precedence over the base accessors (which return empty). Write the JSON Schema in the attribute.
7. **Admin/form code lives in `mcp_server_ui`, example plugins in `mcp_server_examples`** — companion projects, not in core. Mirror the `views`/`views_ui` split.
8. **`declare(strict_types=1);` + `final` classes + constructor promotion** — house style; phpcs (`Drupal,DrupalPractice`) and phpstan are enforced.

## Top pitfalls (full list: each reference doc)

1. **SDK/module version mismatch** — symptom: fatal "class `Mcp\Server\...` not found" or tools silently absent. Cause: `mcp/sdk` at `0.4`/`0.5` while `mcp_server` is `2.x` (needs `^0.6`). Fix: align them (`composer show`); pin `mcp/sdk:^0.6` (0.6.0 tagged 2026-06-02).
2. **Tool not listed** — symptom: missing from `tools/list`. Cause: forgot `drush cr`, or native tool lacks `defaultConfiguration()['enabled' => TRUE]`. Fix: rebuild cache / add the default config.
3. **Anyone can call write tools** — symptom: unauthenticated `tools/call` mutates data. Cause: relying on `checkAccess()` which nothing calls. Fix: add a `RequestEvent` subscriber that enforces it (or enable `mcp_server_oauth`).
4. **Invalid tool/resource name** — symptom: `NameValidator` rejection at registration. Cause: a `:` in a derivative ID. Fix: use the `.` separator.
5. **stdio server dies on a denied call** — symptom: `drush mcp:server` subprocess exits after one rejected tool. Cause: the command catches `McpAuthorizationDeniedException` then rethrows, killing the run loop. Mitigation: run stdio as a privileged/trusted user; gate at the HTTP layer.

## Service IDs & plugin managers

| Service ID | Class | Use for |
|---|---|---|
| `plugin.manager.mcp_server.tool` | `ToolPluginManager` | Discover/instantiate `#[Tool]` plugins; `getDefinitions()` → `ToolDefinition[]` |
| `plugin.manager.mcp_server.resource_provider` | `ResourceProviderManager` | `#[ResourceProvider]` plugins |
| `plugin.manager.mcp_server.resource_template_provider` | `ResourceTemplateProviderManager` | `#[ResourceTemplateProvider]` plugins |
| `plugin.manager.mcp_server.prompt_argument_completion_provider` | `PromptArgumentCompletionProviderManager` | `#[PromptArgumentCompletionProvider]` plugins |
| `plugin.manager.mcp_server.notification` | `NotificationProviderManager` | `#[Notification]` plugins (stub) |
| `mcp_server.server.factory` | `McpServerFactory` | Builds the `Mcp\Server`; registers tools/resources/prompts |
| `mcp_server.server` | `Mcp\Server` | The server instance (`shared: false`; rebuilt per request) |
| `logger.channel.mcp_server` | logger channel | `->get()` not needed — inject this channel directly |
| `mcp_server.shared_tempstore_session_store` | `SharedTempStoreSessionStore` | HTTP session persistence (SharedTempStore-backed, 1-week TTL) |

**Authorization extension point:** subscribe to `Mcp\Event\RequestEvent`; throw
`Drupal\mcp_server\Exception\McpAuthorizationDeniedException($reason, $httpStatus)`
to deny. **Transports:** stdio `drush mcp:server` (alias `mcps`); HTTP `POST /_mcp`
(route `mcp_server.handle`, `_auth: ['cookie']`, perm `access mcp server`).

Full method signatures: [tool-plugins.md](reference/tool-plugins.md),
[resources-prompts-notifications.md](reference/resources-prompts-notifications.md).

## DKAN integration

DKAN MCP on `dkan-site` is **`dkan_mcp_server`** — a contrib module
(drupal.org project, `1.0.x` alpha releases) built ON
`mcp_server` (`mcp/sdk ^0.6`) exposing **~38 tools** (read/write split and exact
counts live in [dkan-integration.md](reference/dkan-integration.md), pinned to the
running site by the live-currency gate — deliberately not restated here) as
`#[Tool]` plugins, with per-tool `checkAccess()` enforced by a shipped
`ToolAccessSubscriber`; stdio via `drush dkan-mcp-server:serve --user=NAME`, HTTP
at `/mcp` with OAuth-only auth (since 2026-06-10). The legacy hand-rolled
`dkan_mcp` (a ~35-tool surface on `mcp/sdk ^0.4`) is retired. If you're touching
DKAN MCP, read [dkan-integration.md](reference/dkan-integration.md) **first** —
architecture, tool roster, permission model, client config. For DKAN service/API
specifics, the `dkan-module-author` skill is the companion.

## Reference

- [reference/mcp-overview.md](reference/mcp-overview.md) — architecture (SDK bridge + Drupal plugins/config entities), extension-point map, transports, companion projects, version landscape
- [reference/tool-plugins.md](reference/tool-plugins.md) — `#[Tool]` attribute, `ToolPluginBase`, `execute()`, `ToolDefinition`, derivers, schemas, enablement
- [reference/resources-prompts-notifications.md](reference/resources-prompts-notifications.md) — resource providers/templates, prompt config entities + completion providers, notification stub
- [reference/auth-and-access.md](reference/auth-and-access.md) — `RequestEvent` gating, `McpAuthorizationDeniedException`, the unenforced-`checkAccess` gotcha, the OAuth companion project, CORS, sessions
- [reference/dkan-integration.md](reference/dkan-integration.md) — DKAN's `dkan_mcp_server` (vs. the retired `dkan_mcp`), tool mapping, permission model, client config
- [reference/testing.md](reference/testing.md) — what to test (and not), unit + kernel patterns, standalone stubs
- Upstream: https://www.drupal.org/project/mcp_server · GitLab issues/MRs (use `glab`, not `drupalorg-cli`) · the module's bundled `references/` (verify against code)
- Canonical examples: the `mcp_server_examples` companion project — `EchoTool`, `ContentLookupTool`, `ContentTypeListResource`, `ContentEntityResourceTemplate`, `EntityQueryCompletionProvider`
