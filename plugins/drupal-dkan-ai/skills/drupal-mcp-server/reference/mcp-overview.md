# MCP Server — Overview & Architecture

What `drupal/mcp_server` is, how it's built, and the extension points you author
against. Read this first; the other reference docs go deep on each surface.

## What it is

`mcp_server` bridges the **Model Context Protocol** PHP SDK (`mcp/sdk`) into
Drupal. It lets AI clients (Claude Desktop, IDE agents, etc.) discover and invoke
Drupal capabilities over MCP's JSON-RPC 2.0 protocol — as **tools** (actions),
**resources** (readable artifacts), and **prompts** (reusable templated messages).

The module supplies the transport, discovery, registration, session, and
authorization plumbing. **You** supply the domain behavior as Drupal plugins and
config entities. Core has **no Drupal module dependencies** — only `php` +
`mcp/sdk` at the Composer level.

## Architecture

```
AI client ──JSON-RPC──▶ transport ──▶ Mcp\Server ──▶ ReferenceHandler ──▶ your plugin
                        (stdio|HTTP)   (SDK)           (per request type)   (#[Tool], …)
                                          ▲
                                  Mcp\Event\RequestEvent  ◀── auth subscribers (deny here)
```

- **`McpServerFactory`** (`mcp_server.server.factory`) builds an `Mcp\Server` per
  request, reading the plugin managers + config entities and registering each
  capability via the SDK `Builder` (`add()` / `addResource()` /
  `addResourceTemplate()`). The `mcp_server.server` service is `shared: false` —
  rebuilt each request so it carries current-user context.
- **Discovery** is Drupal plugin discovery: PHP 8 attributes
  (`#[Tool]`, `#[ResourceProvider]`, `#[ResourceTemplateProvider]`,
  `#[PromptArgumentCompletionProvider]`, `#[Notification]`) under matching
  `src/Plugin/<Type>/` namespaces, each with its own manager
  (`plugin.manager.mcp_server.*`) extending `DefaultPluginManager`.
- **Config entities** back prompts (`McpPromptConfig`) and the enable/configure
  state of resource providers (`mcp_server.resource_providers`,
  `mcp_server.resource_template_providers`).
- **Authorization** is not in the dispatch path by default — it rides the SDK's
  `Mcp\Event\RequestEvent`, fired before any handler runs. See
  [auth-and-access.md](auth-and-access.md).

## Extension-point map

| Surface | Attribute | Namespace | Manager / store | MCP method |
|---|---|---|---|---|
| Tool (action) | `#[Tool]` | `Plugin\Tool` | `plugin.manager.mcp_server.tool` | `tools/list`, `tools/call` |
| Resource (concrete URIs) | `#[ResourceProvider]` | `Plugin\ResourceProvider` | `…resource_provider` + `mcp_server.resource_providers` | `resources/list`, `resources/read` |
| Resource template (URI patterns) | `#[ResourceTemplateProvider]` | `Plugin\ResourceTemplateProvider` | `…resource_template_provider` + `mcp_server.resource_template_providers` | `resources/templates/list` |
| Prompt | — (config entity) | — | `McpPromptConfig` | `prompts/list`, `prompts/get` |
| Prompt arg autocomplete | `#[PromptArgumentCompletionProvider]` | `Plugin\PromptArgumentCompletionProvider` | `…prompt_argument_completion_provider` | `completion/complete` |
| Notification (stub) | `#[Notification]` | `Plugin\Notification` | `…notification` | — (not yet wired) |

## Transports

Both transports build the *same* server from the *same* plugins. There is **no
transport-based tool subsetting** — every registered, enabled capability is
available on both; scope access with a `RequestEvent` subscriber instead.

- **stdio** — `drush mcp:server` (alias `mcps`). Drush bootstraps the full
  container, then `Mcp\Server::run(new StdioTransport())` reads JSON-RPC on
  stdin / writes stdout. For local clients that spawn a subprocess.
- **HTTP** — `POST /_mcp` (route `mcp_server.handle`, controller
  `McpServerController::handle`, methods GET/POST/DELETE/OPTIONS,
  `_auth: ['cookie']`, permission `access mcp server`). Sessions persist across
  requests via `SharedTempStoreSessionStore` (SharedTempStore / `keyvalue.expirable`,
  ~1-week TTL).

> **Route path caveat:** this checkout's `mcp_server.routing.yml` declares
> `/_mcp`. Upstream work makes the path configurable (some builds default to
> `/mcp`). **Verify your build's route** (`drush route | grep mcp`) before wiring
> a client.

## Submodules

| Submodule | Adds |
|---|---|
| `mcp_server_ui` | All admin forms/pages: server settings, prompt CRUD, resource-provider settings. Core ships runtime only (the `views`/`views_ui` split). |
| `mcp_server_oauth` | OAuth2 per-tool scope enforcement via a `RequestEvent` subscriber + RFC 9728 metadata discovery (needs `simple_oauth`/`simple_oauth_21`). |
| `mcp_server_tool_bridge` | Bridges `drupal/tool` plugins into MCP as `tool_api.<config_id>` tools (`ToolApi` plugin). Core has no `drupal/tool` dependency. |
| `mcp_server_examples` | Reference plugins — copy these: `EchoTool`, `ContentLookupTool`, `ContentTypeListResource`, `ContentEntityResourceTemplate`, `EntityQueryCompletionProvider`, `StaticListCompletionProvider`. |

## Version landscape

See the volatility callout in [SKILL.md](../SKILL.md). In short: `mcp_server`
`v2.x-dev` ⇒ `mcp/sdk: dev-main` (0.6 API: `RuntimeToolHandlerInterface`,
`ClientGateway`, `Builder::add()`); `0.6.0` is untagged; the `0.4`/`0.5` API is
incompatible. Confirm with `composer show drupal/mcp_server mcp/sdk` and read the
**source**, not the bundled prose, which can lag. `opis/json-schema 2.6.0` (the
SDK's validator) matches DKAN's lock — no conflict on a DKAN site.

## Build / quality commands

```bash
# from the Drupal root (paths relative to <webroot>):
vendor/bin/phpunit  <webroot>/modules/contrib/mcp_server/tests/
vendor/bin/phpcs --standard=Drupal,DrupalPractice <webroot>/modules/contrib/mcp_server/
vendor/bin/phpstan analyse <webroot>/modules/contrib/mcp_server/
drush cache:rebuild
```

Issues/MRs live on **GitLab** — use the `glab` CLI, not `drupalorg-cli`, for this
project.
