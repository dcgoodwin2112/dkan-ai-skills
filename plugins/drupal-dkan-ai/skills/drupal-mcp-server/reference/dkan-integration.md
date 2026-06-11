# DKAN Integration

How DKAN exposes itself over MCP, and how that maps onto `mcp_server`. Pair this
with the **`dkan-module-author`** skill for DKAN service/API specifics.

> **⏱ Time-sensitive (as of 2026-06-11).** The migration **executed**: `dkan-site`
> runs **`dkan_mcp_server`** — now a drupal.org contrib project (`1.0.x`, alpha
> releases) built ON contrib `mcp_server` `dev-2.x` / `mcp/sdk ^0.6`; the legacy
> hand-rolled `dkan_mcp` is **retired** (source removed from the site). HTTP auth
> went **OAuth-only on 2026-06-10**. Check the live state:
> ```bash
> drush pml --filter=mcp      # dkan_mcp_server Enabled (legacy dkan_mcp retired)
> composer show mcp/sdk       # v0.6.x
> ```
> Source of truth: the project's `docs/`
> (https://www.drupal.org/project/dkan_mcp_server). This repo's `bin/eval live`
> gate verifies the counts and auth claims below against the running site.

## Architecture

**Built ON `mcp_server`.** One `#[Tool]` plugin per
tool under `src/Plugin/Tool/`, each a thin adapter over an MCP-agnostic service:

- **38 tools: 25 read-only + 13 write**, in groups metastore / datastore / search /
  harvest / resource / status / write. Groups can be disabled site-wide at
  `/admin/config/services/dkan-mcp-server` (`disabled_groups` — operational gating,
  not authorization).
- **stdio:** `drush dkan-mcp-server:serve` (alias `dkan-mcps`); `--user=NAME`
  serves as that account; omit for anonymous (read-only under the permission
  model). The upstream `drush mcp:server` command runs anonymous-only and crashes
  at the pinned release — the custom command owns transport + account switching.
- **HTTP:** the contrib route re-pathed to **`/mcp`** via the
  `mcp_server.base_path` container parameter. **OAuth 2.1 Bearer only** (Basic
  removed 2026-06-10): anonymous → 401 challenge; RFC 9728 metadata at
  `/.well-known/oauth-protected-resource` advertises the `dkan_mcp:read` /
  `dkan_mcp:write` scopes. The OAuth wiring is `dkan_mcp_server`'s own
  (`DkanMcpScopes`, `OAuthRouteSubscriber` on `simple_oauth_21`) — the contrib
  `mcp_server_oauth` companion project is not installed.
- **Per-tool access enforced** by a shipped `ToolAccessSubscriber` — it gates
  `tools/call` AND filters `tools/list`, so a read-only account never sees the
  13 write tools ([auth-and-access.md](auth-and-access.md)).

**History.** `dkan_mcp_server` replaced the hand-rolled `dkan_mcp` (its own
server on `mcp/sdk ^0.4`; never released, retired and removed from the site
2026-06-11). The MCP-agnostic tool logic carried over verbatim; everything
transport-, session-, CORS-, and auth-shaped was replaced by contrib
`mcp_server` equivalents.

The tool logic classes (`HarvestTools`, `WriteTools`, `ResourceTools`,
`StatusTools`, plus the `dkan_query_tools` services) are MCP-agnostic plain
classes returning arrays — the plugins inject and call them unchanged. **Keep
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
  inputSchema: [ /* explicit JSON schema */ ],
  outputSchema: [ /* explicit JSON schema */ ],
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

Write tools add a `checkAccess()` permission gate; the shipped
`ToolAccessSubscriber` enforces it ([auth-and-access.md](auth-and-access.md)).

## Permission model

| Permission | Gates |
|---|---|
| `access mcp server` (contrib) | The endpoint + the 25 read tools |
| `edit datasets via mcp`, `publish datasets via mcp`, `delete datasets via mcp`, `manage metastore items via mcp`, `import datastore via mcp`, `drop datastore via mcp`, `manage harvests via mcp` | The 13 write tools, per verb |
| `administer dkan mcp server` | The settings form (tool-group gating) |

The fine-grained per-verb split shipped (superseding the earlier plan's single
coarse write permission). On HTTP, the OAuth `dkan_mcp:read` / `dkan_mcp:write`
scopes feed the same Drupal-permission model — permissions stay the single
source of truth on every transport.

## Client configuration

`.mcp.json` — stdio, account-switched (run with the site checkout as cwd, or
wrap with `sh -c "cd <site> && exec ddev drush …"`):

```json
{ "mcpServers": {
  "dkan-ro": { "type": "stdio", "command": "ddev",
               "args": ["drush", "dkan-mcp-server:serve", "--user=mcp_reader"] }
} }
```

HTTP — OAuth Bearer only (Basic credentials no longer authenticate):

```json
{ "mcpServers": {
  "dkan": { "type": "streamable-http", "url": "https://dkan-site.ddev.site/mcp" }
} }
```

The `ddev` wrapper runs Drush inside the container with full bootstrap.
