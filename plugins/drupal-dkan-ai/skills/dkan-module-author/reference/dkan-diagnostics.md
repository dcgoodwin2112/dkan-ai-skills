# Diagnosing a DKAN Site

Operational diagnostics for a running DKAN site: logs, stuck queues, and permission
misconfiguration. This complements [dkan-drush.md](dkan-drush.md) (the DKAN command
catalog) with the generic Drupal diagnostics that aren't DKAN-specific commands, plus
the `dkan_mcp_server` status tools (`get_site_status`, `get_queue_status`, `get_import_status`).

The earlier generic Drupal-introspection MCP tools (log/permission/service readers)
were removed; `drush` covers that ground and is available to any local agent. Run drush
via DDEV: `ddev drush <cmd>`.

## Logs (watchdog)

```bash
ddev drush watchdog:show --count=25            # recent entries
ddev drush watchdog:show --type=dkan           # filter by logger channel
ddev drush watchdog:show --severity=Error      # filter by severity
ddev drush watchdog:list                        # distinct types with counts
ddev drush watchdog:tail                        # follow live
```

DKAN logger channels: `dkan`, `datastore`, `harvest` (the `*.logger_channel` services
in [dkan-services.md](dkan-services.md)). Severity is RFC 5424:
`0 Emergency, 1 Alert, 2 Critical, 3 Error, 4 Warning, 5 Notice, 6 Info, 7 Debug`.

## Stuck queues and imports

The CSV import pipeline runs through three queues
([dkan-workflows.md#csv-import-pipeline](dkan-workflows.md#csv-import-pipeline)):
`localize_import` → `datastore_import` → `post_import`.

```bash
ddev drush queue:list                  # item counts per queue
ddev drush queue:run datastore_import  # process one queue
ddev drush cron                        # process all queues + scheduled work
```

A stuck import usually means cron isn't draining a queue. Check item counts, then
inspect the resource (import commands themselves are in [dkan-drush.md](dkan-drush.md)):

- `dkan_mcp_server` `get_queue_status` — DKAN queue item counts (same data, agent-friendly).
- `dkan_mcp_server` `get_import_status` — per-resource import state (`done` / `pending` /
  `not_imported`, row counts).
- `dkan_mcp_server` `get_site_status` — module versions, dataset/distribution counts,
  aggregate import state.

## Permission misconfiguration

Three failure modes worth checking when a route 403s unexpectedly or a role can't do
what it should:

1. **Orphaned route permission** — a route requires a permission string that no module
   defines. The route is then effectively unreachable. Compare the route's `_permission`
   against defined permissions.
2. **Orphaned role permission** — a role grants a permission that no longer exists (e.g.
   after a module update renamed it). Harmless but masks intent.
3. **Unused permission** — a DKAN permission is defined but no route references it. Often
   fine for entity-access permissions (`view/edit/... data`), which are checked in code
   rather than route requirements.

Inspect with `drush`:

```bash
ddev drush role:list                                   # roles + granted permissions
ddev drush eval "print_r(array_keys(\Drupal::service('user.permissions')->getPermissions()));"
ddev drush role:perm:add anonymous 'access content'    # grant
```

DKAN's REST permission machine-names are listed in
[dkan-api.md#permissions-summary](dkan-api.md#permissions-summary). Route definitions
live in each submodule's `*.routing.yml` under `<webroot>/modules/contrib/dkan/modules/`.
