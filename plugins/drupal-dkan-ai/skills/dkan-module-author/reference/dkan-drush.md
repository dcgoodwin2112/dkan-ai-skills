# DKAN Drush Commands Reference

Canonical CLI for debugging datastore, harvest, and metastore. All commands enumerated from registered `drush.services.yml` command classes under `<webroot>/modules/contrib/dkan`.

## Running drush

On a DDEV site, prefix every command with `ddev` (as the examples below do); elsewhere, run `drush` (or `vendor/bin/drush`) directly:

```
ddev drush dkan:datastore:list
ddev drush dkan:harvest:status sample_content
```

Commands taking a confirmation (e.g. `dkan:harvest:deregister`, `dkan:harvest:cleanup`) accept `-y` / `--no-interaction` to auto-confirm.

These statuses are also introspectable live via the `dkan_mcp_server` MCP tools when that module is installed (e.g. `get_import_status`), but drush is the canonical CLI.

## Datastore

Source: `dkan_datastore/src/Drush.php`, `dkan_datastore/src/Commands/{ReimportCommands,PurgeCommands,DegradedModeCommands}.php`

| Command | Args / Options | Description |
|---|---|---|
| `dkan:datastore:import` | `<identifier>` `--deferred` | Import a datastore resource by resource ID. `--deferred` queues instead of running now. No-op if jobs already "done" (drop first to re-import). |
| `dkan:datastore:list` | `--format` `--status=<status>` `--uuid-only` | List all datastores with FileFetcher/Importer status and bytes processed. `--status` filters; `--uuid-only` returns UUIDs only. |
| `dkan:datastore:drop` | `<identifier>` `--keep-local` | Drop datastore table + localized file + post-import job status. `--keep-local` preserves the localized file. |
| `dkan:datastore:drop-all` | — | Drop ALL datastore tables (iterates every distribution). |
| `dkan:datastore:prepare-localized` | `<identifier>` | Prepare local perspective: create dir, add `local_url` to resource mapper (no checksum), print external fetch info. |
| `dkan:datastore:localize` | `<identifier>` `[version]` `--deferred` | Copy resource from source to local file system. Defaults to latest version. `--deferred` queues. |
| `dkan:datastore:reverse-dataset-lookup` (alias `dkan:datastore:rdl`) | `<table_name>` | Resolve a datastore table name (e.g. `datastore_8b7a...`) back to its dataset UUID. |
| `dkan:datastore:reimport` | `<uuid>` | Drop and re-import all distributions for a dataset UUID. |
| `dkan:datastore:purge` | `<csvUuids>` `--deferred` `--prior` | Purge unneeded resources for comma-separated dataset UUIDs. `--prior` covers all prior revisions (default: two most recent). |
| `dkan:datastore:purge-all` | `--deferred` `--prior` | Purge unneeded resources across all datasets. |
| `dkan:datastore:degraded-mode` | `[state]` (`1`/`0`) | Enable/disable degraded datastore query mode. Omit arg to show current status. |

## Harvest

Source: `dkan_harvest/src/Commands/HarvestCommands.php`

| Command | Args / Options | Description |
|---|---|---|
| `dkan:harvest:list` | — | List registered harvest plan IDs. |
| `dkan:harvest:register` | `[plan_json]` `--identifier` `--extract-type` `--extract-uri` `--transform` `--load-type` | Register a harvest plan from JSON, or build from options. If `plan_json` given, options ignored. |
| `dkan:harvest:deregister` | `<plan_id>` `--revert` | Delete a harvest plan (confirms). `--revert` removes harvested datasets first. |
| `dkan:harvest:run` | `<plan_id>` | Run a single harvest plan. |
| `dkan:harvest:run-all` | `--new` | Run all registered plans. `--new` runs only plans that never ran. |
| `dkan:harvest:info` | `<harvestId>` `[runId]` | Show plan and run info. Omit `runId` for all runs. |
| `dkan:harvest:revert` | `<harvestId>` | Remove all harvested entities for a plan. |
| `dkan:harvest:archive` | `<harvestId>` | Archive all harvested datasets for a plan. |
| `dkan:harvest:publish` | `<harvestId>` | Publish all harvested datasets for a plan. |
| `dkan:harvest:status` | `<harvestId>` `[runId]` | Show status of a run. Omit `runId` for latest run. |
| `dkan:harvest:orphan-datasets` (alias `dkan:harvest:orphan`) | `<harvestId>` | Orphan datasets from every run of a harvest. |
| `dkan:harvest:cleanup` | — | Report and (on confirm) remove leftover harvest data tables. |
| `dkan:harvest:update` | — | Migrate old-style harvest hash/run tables to the current schema; drops outdated tables. |

## Metastore

Source: `dkan_metastore/src/Commands/MetastoreCommands.php`, `dkan_metastore/modules/dkan_metastore_search/src/Commands/RebuildTrackerCommands.php`

| Command | Args / Options | Description |
|---|---|---|
| `dkan:metastore:publish` | `<uuid>` | Publish the latest version of a dataset. |
| `dkan:metastore-search:rebuild-tracker` | — | Rebuild the Search API tracker for the `dkan` index. |

## Common / Dataset

Source: `dkan_common/src/Commands/{CommonCommands,JobStoreCommands}.php`

| Command | Args / Options | Description |
|---|---|---|
| `dkan:dataset-info` | `<uuid>` | Print JSON info about a dataset and its resources/distributions/revisions. |
| `dkan:jobstore-fixer` | — | Rename deprecated jobstore tables and merge duplicates into current-named tables. |

## Sample Content

Source: `dkan_sample_content/src/Drush.php`

| Command | Args / Options | Description |
|---|---|---|
| `dkan:sample-content:create` | — | Register and run the `sample_content` harvest. Run cron a few times to finish import. |
| `dkan:sample-content:remove` | — | Revert and deregister the `sample_content` harvest plan. |
