---
name: dkan-module-author
description: Reference and decision support for writing custom Drupal modules that extend DKAN — metastore, datastore, harvest, search, or events. Loads when editing files under web/modules/custom/, when working with Drupal\dkan\*, Drupal\metastore\*, Drupal\datastore\*, Drupal\harvest\*, or Drupal\common\* namespaces, or when consuming DKAN's REST API. Targets DKAN 2.22 on Drupal 10.6. Curates the bundled `reference/dkan-*.md` doc set; does not duplicate it.
---

# DKAN Module Author's Reference

This skill loads when you're writing custom code that integrates with DKAN. Its job is to direct you to the right detail doc and surface the half-dozen DKAN-specific concepts that are non-obvious from the code alone.

For runtime introspection (querying the catalog, inspecting harvest runs, reading logs), prefer the `dkan_mcp` MCP tools over manual code-spelunking — see [web/modules/custom/dkan_mcp/README.md](../../../dkan_mcp/README.md).

## Pick the right doc for the task

| Task | Read |
|---|---|
| Understanding what a Distribution / Reference / Perspective IS | [reference/dkan-overview.md](reference/dkan-overview.md#key-concepts) |
| Injecting a DKAN service in a custom plugin | [reference/dkan-services.md](reference/dkan-services.md) — has every service ID + class + method signature |
| Querying the datastore programmatically | [reference/dkan-services.md#datastore-module](reference/dkan-services.md#datastore-module) (services) + [reference/dkan-workflows.md#datastore-query-execution](reference/dkan-workflows.md#datastore-query-execution) (flow) |
| Hitting DKAN's REST API from a controller or external client | [reference/dkan-api.md](reference/dkan-api.md) |
| Subscribing to a DKAN event | [reference/dkan-services.md#event-constants](reference/dkan-services.md#event-constants) (constants) + [reference/dkan-workflows.md#event-system](reference/dkan-workflows.md#event-system) (timing) |
| Tracing what happens when a CSV is imported | [reference/dkan-workflows.md#csv-import-pipeline](reference/dkan-workflows.md#csv-import-pipeline) |
| Building a custom harvester or listening to harvest events | [reference/dkan-services.md#harvest-module](reference/dkan-services.md#harvest-module) + [reference/dkan-workflows.md#harvest-etl](reference/dkan-workflows.md#harvest-etl) |
| Writing a unit / kernel test that touches DKAN classes | [reference/dkan-testing.md](reference/dkan-testing.md) — mock-chain patterns, standalone-stub conventions, base classes |
| Standard Drupal 10 conventions (DI, render arrays, routing, plugins) | [reference/drupal-patterns.md](reference/drupal-patterns.md) |

If your question is "what data exists right now?" — that's a `dkan_mcp` query, not a docs lookup.

## Always-true rules (the things people get wrong on first attempt)

These are the DKAN-specific concepts that don't exist in vanilla Drupal and aren't visible from a `services.yml` grep. Read these before writing code that touches metadata or datastore resources.

1. **Metastore returns `RootedJsonData`, not arrays.** `MetastoreService::get('dataset', $uuid)` returns a `RootedJsonData` object that casts to a JSON string via `(string) $rooted`. To work with it as an array, do `json_decode((string) $rooted, TRUE)`. Calling array methods on the object directly throws.
2. **Resource IDs are `{identifier}__{version}` with a double underscore.** `identifier` is an MD5 of the file path; `version` is a Unix timestamp. The full unique-identifier form including perspective is `{identifier}__{version}__{perspective}`. Use `DataResource::parseUniqueIdentifier($uid)` to split. Datastore table names are `datastore_` + MD5 of the full `identifier_version_perspective` string — *not* of the `identifier__version` resource ID.
3. **Perspectives are real and matter.** A resource (CSV) exists at multiple URIs at once — `source` (the external URL), `local_file` (downloaded copy), `local_url` (web-accessible local). When asking ResourceMapper for a resource, pass the perspective: `$resourceMapper->get($identifier, 'source')`. Wrong perspective → null result → silent failure.
4. **Distributions on a fetched dataset live under `%Ref:downloadURL`, not the top-level `downloadURL`.** When you `json_decode` a Metastore-returned dataset, `$dataset['distribution'][n]['downloadURL']` is the original URL string, but the resolved resource info (identifier, version, perspective) is at `$dataset['distribution'][n]['%Ref:downloadURL'][0]['data']`. The `%Ref:` fields are how the Dereferencer surfaces resolution metadata. Do NOT compute `md5($downloadURL)` to look up resources — read `%Ref:downloadURL[*]['data']['identifier']` directly.
5. **References decouple nested objects.** Publisher, distribution, keyword, theme, and other configurable properties are stored as separate `data` nodes referenced by UUID. On write, the Referencer hashes and dedupes; on read, the Dereferencer expands UUIDs back to full objects. Treating these as plain inline data on POST will create orphan reference nodes.
6. **The harvest module's "plan" and "run" are separate concepts.** A plan is the configuration (source, extractor, identifier); a run is one execution of that plan. Harvest results live under runs, not plans. `HarvestService::runHarvest($plan_id)` creates a new run; `getRunIdsForHarvest($plan_id)` enumerates them.
7. **Datastore queries take a `DatastoreQuery` DTO, not raw SQL.** Build a JSON payload `['resources' => [['id' => $resource_id, 'alias' => 't']], 'limit' => N, ...]`, wrap with `new DatastoreQuery(json_encode($payload))`, pass to `Query::runQuery()`. Returns a `RootedJsonData`; decode for results.

## Top pitfalls

The five most expensive mistakes when writing against DKAN. Each has a one-line symptom and a one-line fix.

1. **Looking up a resource by `md5($downloadURL)`.** Symptom: `resourceMapper->get(md5($url), 'source')` returns null even though the dataset shows the file. Cause: the identifier is computed from the *file path* the resource was registered with, which may differ from the canonical `downloadURL` (e.g. host rewriting, internal URLs). Fix: read `%Ref:downloadURL[0]['data']['identifier']` from the dereferenced dataset JSON instead of recomputing.
2. **Forgetting to publish.** Symptom: `MetastoreService::get('dataset', $uuid)` works in tests but a public API call returns 404. Cause: `post()` creates a draft; you also need `publish()` for the dataset to be visible to anonymous users. Fix: see [reference/dkan-workflows.md#publish](reference/dkan-workflows.md#publish).
3. **Custom event subscriber never fires.** Symptom: tagged `event_subscriber` service registered, `getSubscribedEvents()` returns the right constant, but the listener never runs. Cause: most likely subscribed to the wrong event constant (DKAN events live on multiple classes — `MetastoreService::EVENT_DATASET_UPDATE`, `Search::EVENT_SEARCH`, etc., not a single namespace), or the event has been fired before the subscriber's module was enabled (cache). Fix: cross-reference the constant in [reference/dkan-services.md#event-constants](reference/dkan-services.md#event-constants), confirm tagging in `*.services.yml`, `drush cr`.
4. **Assuming an array shape from `MetastoreService::get()`.** Symptom: `Cannot use object of type RootedJsonData as array` or `Trying to access array offset on value of type object`. Fix: `$data = json_decode((string) $rooted, TRUE)` first. Same goes for `Query::runQuery()`'s return — it's `RootedJsonData`, not an array.
5. **Test with mock-chain that breaks on a DKAN refactor.** Symptom: phpunit was green; after a `composer update`, mock-chain throws `MethodCallNotInChain`. Cause: the underlying class added or renamed a method. Fix: see [reference/dkan-testing.md#mock-chain-library](reference/dkan-testing.md#mock-chain-library) for the correct invocation pattern; for behavior tests prefer kernel tests against real services.

## Service injection cheat sheet

When you need to inject a DKAN service in a custom plugin or controller, the most common ones:

| Need | Service ID |
|---|---|
| CRUD against the metastore | `dkan.metastore.service` |
| Resolve a resource UUID/URL → resource ID | `dkan.metastore.resource_mapper` |
| Run a structured datastore query | `dkan.datastore.query` |
| Run raw datastore SQL | `dkan.datastore.sql_endpoint.service` |
| Read import status / row counts | `dkan.datastore.service` (`DatastoreService`) |
| Manage harvest plans / runs | `dkan.harvest.service` |
| Search the metastore | `dkan.metastore_search.service` (requires `metastore_search` enabled) |

Full table with method signatures: [reference/dkan-services.md](reference/dkan-services.md). Add the corresponding submodule (`dkan:metastore`, `dkan:datastore`, `dkan:harvest`, `dkan:metastore_search`) to your module's `*.info.yml` dependencies.

## When to reach for `dkan_mcp` instead

The MCP server is the right surface when the task is "discover or manipulate live data," not "write code that runs in production":

- Auditing the catalog before a migration → `list_datasets`, `get_dataset_info`, `search_datasets`
- Debugging a failing import → `get_import_status`, log queries via `LogTools`
- Reproducing a query a user reported → `query_datastore`, `get_datastore_schema`
- Permission check / route check while reasoning about a controller → `check_permissions`, `get_route_info`

For the full tool list, see [web/modules/custom/dkan_mcp/docs/tools.md](../../../dkan_mcp/docs/tools.md). Skill content directs to MCP tools deliberately; do not duplicate their parameter schemas here.

## Version notes

- This site runs DKAN 2.22 on Drupal 10.6. Behavior described here is verified against that combination.
- Internal APIs (service signatures, event constants) are not guaranteed stable across DKAN minor releases. Before recommending a class or method by name, verify it exists in the installed copy: `find web/modules/contrib/dkan -name "<ClassName>.php"`.
- Public REST API endpoints are version-stable across 2.x. See [reference/dkan-api.md](reference/dkan-api.md).
