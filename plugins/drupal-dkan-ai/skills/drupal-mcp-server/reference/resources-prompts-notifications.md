# Resources, Prompts & Notifications

The non-tool extension points. Reach for these when a client should **read**
artifacts or **reuse** prompt templates, rather than invoke an action. Lower
frequency than [tool plugins](tool-plugins.md); the full upstream detail is in the
module's `references/resources/` and `references/prompts/`.

## Resource Providers

A `#[ResourceProvider]` plugin enumerates **concrete, fully-qualified resource
URIs** and serves their content. Surfaced via `resources/list` / `resources/read`,
registered with the SDK `Builder::addResource()`.

- **Discovery:** `#[ResourceProvider]` under `src/Plugin/ResourceProvider/`.
  Manager `plugin.manager.mcp_server.resource_provider`. Base
  `ResourceProviderBase`.
- **Config:** the `mcp_server.resource_providers` config object — one entry per
  plugin `{id, enabled, configuration}`. Admin form (in `mcp_server_ui`) at
  `/admin/config/services/mcp-server/resources`. Enablement is **config-driven**
  (unlike native tools).

Key `ResourceProviderInterface` methods (`src/Plugin/ResourceProviderInterface.php`):

```php
getResourceType(): string;                                     // usually the plugin ID
getResources(): array;        // each: uri (req), name (req), description?, mimeType?, size?
getResourceContent(string $uri): ?CacheableResourceContent;    // NULL if URI not handled
checkAccess(string $uri, AccountInterface $account): AccessResultInterface;
isEnabled(): bool;
```

- `getResources()` is **plural** — one plugin can enumerate many concrete URIs
  (e.g. one per vocabulary). It runs at `resources/list` time, so **keep it
  cheap**; defer content building to `getResourceContent()`.
- `getResourceContent()` returns a `CacheableResourceContent` DTO wrapping
  `{uri, mimeType, text|blob}` (`text` = UTF-8 string, `blob` = binary), aligned
  to the SDK `ResourceContents` shape.
- The factory's handler closure calls `checkAccess()` and throws
  `McpAuthorizationDeniedException` on deny / `\RuntimeException` when content is
  `NULL` — so unlike tools, **resource access IS enforced** during read.

**Caching:** content is cached automatically. `CacheableResourceContent::fromArray($content)`
with no metadata → `CACHE_PERMANENT`. Declare variance with a `CacheableMetadata`
(tags/contexts); opt out with `setCacheMaxAge(0)`. The cache key is the expanded
URI + resolved contexts, so one plugin can cache thousands of URIs independently.
`checkAccess()` cacheability is merged in automatically — don't repeat it in the DTO.

Example: `mcp_server_examples` `ContentTypeListResource` — one resource at
`drupal://content-types` listing node types; requires `access content`.

## Resource Templates

A `#[ResourceTemplateProvider]` plugin exposes a **parameterized URI template**
(e.g. `drupal://entity/node/{id}`) instead of a fixed list — for resource
*families* too large to enumerate. Surfaced via `resources/templates/list`,
registered with `Builder::addResourceTemplate()`.

- **Discovery:** `#[ResourceTemplateProvider]` under
  `src/Plugin/ResourceTemplateProvider/`. Manager
  `plugin.manager.mcp_server.resource_template_provider`. Base
  `ResourceTemplateProviderBase`.
- **Config:** `mcp_server.resource_template_providers` (separate object from
  resource providers). The plugin handles URI-template matching + expansion.

Example: `mcp_server_examples` `ContentEntityResourceTemplate`.

**Provider vs. template:** fixed, listable set → ResourceProvider; open-ended,
parameter-driven family → ResourceTemplateProvider.

## Prompts

Prompts are **config entities, not plugins.** `McpPromptConfig`
(`src/Entity/McpPromptConfig.php`) defines a reusable, templated prompt; surfaced
via `prompts/list` / `prompts/get`. CRUD is in `mcp_server_ui` at
`/admin/config/services/mcp-server/prompts` (form `McpPromptConfigForm`, permission
`administer mcp prompt configurations`). Define them in config, not PHP.

Fields: `id`, `label`, `title?`, `description?`, `arguments[]`, `messages[]`,
`status`.

- **Argument:** `{label, machine_name, description, required, completion_providers?}`
  where `completion_providers` is `[{plugin_id, configuration}]` (next section).
- **Message:** `{role: user|assistant, content: [typed items]}`. Content item
  types: `text` (`text`), `image`/`audio` (`data` base64 + `mimeType`), `resource`
  (`resource.{uri,mimeType,text}`). Discovery via `access mcp server prompts`.

## Completion Providers

A `#[PromptArgumentCompletionProvider]` plugin supplies **autocomplete values**
for a prompt argument (`completion/complete`).

- **Discovery:** `#[PromptArgumentCompletionProvider]` under
  `src/Plugin/PromptArgumentCompletionProvider/`. Manager
  `plugin.manager.mcp_server.prompt_argument_completion_provider`. Base
  `PromptArgumentCompletionProviderBase`.
- Reference it from an argument's `completion_providers` by `plugin_id` +
  per-use `configuration`.

Examples (`mcp_server_examples`): `StaticListCompletionProvider` (config-supplied
list) and `EntityQueryCompletionProvider` (entity-query-driven).

## Notifications

**Stub only — contract shipped, not yet wired.** A `#[Notification]` plugin
declares which MCP notifications the server *can* emit.

- `#[Notification]` under `src/Plugin/Notification/`. Manager
  `plugin.manager.mcp_server.notification`. Base `NotificationProviderBase`.
- Interface: `NotificationProviderInterface::getNotifications(): iterable`.

`McpServerFactory` accepts the manager but **does not iterate it** yet; no concrete
emission path exists. Don't build on it for production until upstream wires
notification emission into the server lifecycle. (Resource `list_changed`
subscriptions are likewise out of scope today.)
