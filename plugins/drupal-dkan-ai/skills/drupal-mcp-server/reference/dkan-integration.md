# DKAN Integration

How DKAN exposes itself over MCP, and how that maps onto `mcp_server`. Pair this
with the **`dkan-module-author`** skill for DKAN service/API specifics.

> **⏱ Time-sensitive (as of 2026-05-31).** DKAN's MCP module is **mid-migration**.
> The plan below is validated but **not yet executed** in `dkan-site`. Always
> check the live state first:
> ```bash
> composer show drupal/mcp_server mcp/sdk
> ls docroot/modules/custom/dkan_mcp/src        # Server/ + Controller/ present → still hand-rolled
> ```
> Source of truth: `dkan_mcp/docs/contrib-mcp-server-{evaluation,migration,contributions}.md`.

## Which world am I in?

**`dkan_mcp` today — hand-rolled, NOT on `mcp_server`.** It runs its own MCP
server directly on `mcp/sdk ^0.4`:

- `src/Server/McpServerFactory.php` — declarative `TOOL_GROUPS` registry →
  `Builder::addTool()`.
- `src/Server/ToolServiceContainer.php` — PSR-11 shim so the SDK can resolve
  service-injected tool classes.
- `src/Controller/McpController.php` — HTTP at **`/mcp`** (its own route).
- `src/Drush/McpServeCommand.php` — stdio via **`drush dkan-mcp:serve`**.
- `src/EventSubscriber/McpCorsSubscriber.php`, a `FileSessionStore`.

It exposes **~35 tools** across metastore/datastore/search/harvest/resource/write/
status; **22 read-only** are surfaced over HTTP (writes are stdio-only / absent
over HTTP). None of the contrib `#[Tool]` plugin model is used.

**The target — rebuilt on `mcp_server`.** The validated plan deletes all the
plumbing above and re-exposes the same tools as `#[Tool]` plugins, with a
`ToolAccessSubscriber` for per-tool permission gating. **This is a cutover, not
side-by-side** — the old code targets SDK `0.4`, `mcp_server` needs `dev-main`
(0.6); both can't autoload at once.

### Current `dkan-site` reality

Root `composer.json` pins **`mcp/sdk: ^0.4`** (`v0.4.0` locked). The vendored
`mcp_server` is at `v2.x-dev` (0.6 API) — so it references SDK classes
(`RuntimeToolHandlerInterface`, `ClientGateway`) **not installed** and is **not
runnable here yet**. It's present for migration prep. `dkan_mcp`'s hand-rolled
server is what actually runs today, on the 0.4 SDK.

## What carries over vs. what's replaced

| `dkan_mcp` today | On `mcp_server` | Status |
|---|---|---|
| Tool **logic** classes (`src/Tools/*` + shared `dkan_query_tools` services) | **Unchanged** — `#[Tool]` plugins delegate to them verbatim | Kept (198 unit tests stay green) |
| `McpServerFactory` + `TOOL_GROUPS` + `ToolServiceContainer` | `ToolPluginManager` discovery; native `enabled` via `defaultConfiguration()` | Deleted |
| `McpServeCommand` (`dkan-mcp:serve`) | `drush mcp:server` (contrib) | Deleted |
| `McpController` (`/mcp`) + `FileSessionStore` | contrib `POST /_mcp` + `SharedTempStoreSessionStore` | Deleted |
| Transport-level read-only subsetting (22-of-35 over HTTP) | **Per-tool access** (`checkAccess()` + `RequestEvent` subscriber) on *both* transports | Replaced |
| `McpCorsSubscriber` | contrib in-core CORS | Deleted |
| `input`/`output` schemas (3 explicit; rest auto-generated from method signatures) | `#[Tool]` `inputSchema`/`outputSchema` — **explicit for all 35** | Ported (bulk of the work) |

The 4 local logic classes (`HarvestTools`, `WriteTools`, `ResourceTools`,
`StatusTools`) and the 3 `dkan_query_tools` classes are already MCP-agnostic plain
classes returning arrays — the new plugins inject and call them unchanged. **Keep
plugins thin adapters** (validate `$arguments` → call the service → shape return);
the domain logic stays in DKAN's service layer. See
[tool-plugins.md#injecting-services](tool-plugins.md).

## Tool plugin skeleton (DKAN)

One class per tool under `src/Plugin/Tool/`, delegating to an injected DKAN service:

```php
#[Tool(
  id: 'query_datastore',
  label: new TranslatableMarkup('Query datastore'),
  description: new TranslatableMarkup('Query a datastore resource table…'),
  inputSchema: [ /* ported from SCHEMA_QUERY_DATASTORE */ ],
  outputSchema: [ /* ported from OUT_QUERY_RESULT */ ],
  readOnly: TRUE, destructive: FALSE, idempotent: TRUE, openWorld: FALSE,
)]
final class QueryDatastoreTool extends ToolPluginBase {
  public static function create(ContainerInterface $c, array $cfg, $id, $def): static {
    $i = parent::create($c, $cfg, $id, $def);
    $i->datastore = $c->get('dkan_query_tools.datastore');
    return $i;
  }
  protected function defaultConfiguration(): array { return ['enabled' => TRUE]; }
  public function execute(array $a, ClientGateway $g): mixed {
    return $this->datastore->queryDatastore($a['resourceId'], /* … */);
  }
}
```

Write tools add a `checkAccess()` permission gate; a `ToolAccessSubscriber`
enforces it ([auth-and-access.md](auth-and-access.md)).

## Permission model

| Permission | Gates |
|---|---|
| `access mcp server` (core) | The endpoint + the 22 read tools |
| `administer dkan via mcp` (new in `dkan_mcp`) | The 13 write tools (dataset/metastore lifecycle, imports, datastore drop, harvest write) |

Coarse to start; finer splits (`harvest via mcp`, `delete datasets via mcp`, …)
are a config-only follow-up — split the permission, repoint the affected plugins'
`checkAccess()`. Write tools to mark `destructive: TRUE`: `delete_dataset`,
`drop_datastore`, `deregister_harvest`, `unpublish_dataset`.

## Client configuration

`.mcp.json` — **today** (hand-rolled `dkan_mcp`):

```json
{ "mcpServers": {
  "dkan": { "type": "stdio", "command": "ddev", "args": ["drush", "dkan-mcp:serve"] }
} }
```
```json
{ "mcpServers": {
  "dkan": { "type": "streamable-http", "url": "https://dkan-site.ddev.site/mcp" }
} }
```

**After migration:** stdio command becomes `drush mcp:server`; HTTP URL becomes the
contrib route (`/_mcp` in the current checkout — **verify the path**, it's being
made configurable). The `ddev` wrapper runs Drush inside the container with full
bootstrap.

## Cutover gate

Phases 1–4 (scaffold plugins, port tools, delete plumbing, docs) can proceed on a
branch now against `mcp_server:2.x-dev` / `mcp/sdk:dev-main` pinned to exact
commits. **Do not flip production** (root `composer.json`: `mcp/sdk ^0.4` →
`dev-main`, add `drupal/mcp_server`) until **`mcp/sdk 0.6.0` tags** — the one hard
external dependency. Rollback is atomic: revert the root composer change + the
branch. Acceptance checklist lives in `contrib-mcp-server-migration.md §12`.
