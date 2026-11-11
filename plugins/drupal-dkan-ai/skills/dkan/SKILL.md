---
name: dkan
description: DKAN 4.x concepts and gotchas that are not obvious from the source. Loads when writing custom modules that extend DKAN (metastore, datastore, harvest, events), contributing to DKAN core (drupal/dkan, GitHub GetDKAN/dkan), working with Drupal\dkan_* namespaces or DKAN's REST API, authoring or validating dataset/distribution metadata (data.json, schema/collections/*.json, DCAT-US / Project Open Data), or wiring the decoupled React frontend (dkan_js_frontend).
---

# DKAN

Only what a grep of the installed code will not tell you quickly. Everything else
(signatures, service tables, drush commands, versions) comes from the source — it is
never stale and this file would be.

`<dkan>` is the package root: `<webroot>/modules/contrib/dkan` in a built site
(`docroot/` or `web/`), or a standalone checkout.

## Look it up, don't recall it

| Need | Source |
|---|---|
| Installed versions | `composer show drupal/dkan`, `drush status` |
| Service IDs and classes | `grep -rn "^  dkan\." <dkan>/modules/*/*.services.yml`, then read the class |
| Drush commands | `drush list --filter=dkan` |
| REST API | OpenAPI spec served at `/api/1`; routes in `<dkan>/modules/*/*.routing.yml` |
| Event constants | `grep -rn "const EVENT_" <dkan>/modules/*/src` |
| Metadata schema | `<dkan>/schema/collections/*.json` |
| Queue workers | `<dkan>/modules/*/src/Plugin/QueueWorker/` |
| CI matrix and test groups | `<dkan>/.circleci/config.yml` |
| Test/build commands | `ls .ddev/commands/*` |

Pre-4.x namespaces (`Drupal\metastore\…`, `Drupal\datastore\…`) are gone; 4.x is
`Drupal\dkan_metastore`, `Drupal\dkan_datastore`, `Drupal\dkan_harvest`,
`Drupal\dkan_common`. Service IDs (`dkan.metastore.service`, …) did not change.
Internal PHP APIs are not stable across minors; the REST API is.

End-to-end flows (dataset CRUD, CSV import, harvest, datastore query, reference
resolution, event chains): [reference/dkan-workflows.md](reference/dkan-workflows.md).

## Building against DKAN

1. **Metastore and datastore return `RootedJsonData`, not arrays.**
   `MetastoreService::get()` and `Query::runQuery()` both do. Decode first:
   `json_decode((string) $rooted, TRUE)`.
2. **Resource IDs are `{identifier}__{version}`** (double underscore); the full unique
   identifier adds `__{perspective}`. `DataResource::getIdentifierAndVersion()` accepts
   a 2-part ID, a 3-part ID, or a distribution UUID. `parseUniqueIdentifier()` throws
   unless given exactly three parts. Datastore tables are
   `datastore_` + `md5(<3-part unique identifier>)` — get the name from
   `DatabaseTable::getTableName()`, never build it by hand.
3. **A resource exists under several perspectives:** `source` (original URL),
   `local_file`, `local_url`. `ResourceMapper::get($identifier, $perspective)` defaults
   to `source` and returns `NULL` when that perspective is not registered.
4. **Never compute `md5($downloadURL)` to find a resource.** On a dereferenced dataset,
   `distribution[n].downloadURL` is the URL string; the resource identity is at
   `distribution[n]['%Ref:downloadURL'][0]['data']` (`identifier`, `version`,
   `perspective`).
5. **Publisher, distribution, keyword, theme are separate `data` nodes referenced by
   UUID.** The Referencer hashes and dedupes on write; the Dereferencer expands on read.
6. **Visibility follows the `dkan_publishing` workflow.** `post()`/`put()` save with
   the workflow's `default_moderation_state` (`published` as shipped). If a site sets
   it to `draft`, anonymous API calls 404 until `MetastoreService::publish()`.
7. **Datastore queries take a `DatastoreQuery` DTO, not SQL:**
   `new DatastoreQuery(json_encode(['resources' => [['id' => $id, 'alias' => 't']], 'limit' => 10]))`
   → `Query::runQuery()`. The payload is validated against
   `<dkan>/modules/dkan_datastore/docs/query.json`.
8. **Events are constants on many classes** (`LifeCycle`, `ResourceMapper`,
   `ResourceLocalizer`, …), not one namespace. A subscriber that never fires is usually
   subscribed to the wrong constant.
9. **Harvest plan ≠ run.** A plan is configuration; a run is one execution, and results
   live on runs (`runHarvest()`, `getRunIdsForHarvest()`).
10. **Harvest ETL components are plain classes, not plugins.** The plan JSON names
    extract/transform/load classes by FQN; `ETL\Factory` does `class_exists()` then
    `new`. No attribute, no manager, no `drush cr`.
    - `Transform::run()` must return the item; returning nothing drops it.
    - `Extract::run()` throws unless it yields a non-empty array of objects.
    - `Load::run()` calls `saveItem()` only for new or changed items (hash compare).
    - The production loader and importer are outside `ETL\`:
      `Drupal\dkan_harvest\Load\Dataset`, `Drupal\dkan_harvest\Transform\ResourceImporter`.
11. **If `dkan_mcp_server` is connected, use its tools for live data** (catalog, import
    and queue status, datastore queries) instead of reading code or writing drush evals.

## Contributing to DKAN core

1. **Verify against the target branch, not the checkout:** `git show 4.x:<path>`.
   Feature branches change signatures and dependencies.
2. **Tests run in-repo against a real Drupal kernel.** Most coverage is kernel tests;
   REST tests extend `Api1TestBase` (`dkan_common/tests/src/Functional/`). Reuse the
   traits in `dkan_common/tests/src/Traits/`.
3. **Async work does not run in a test until the queue is pumped.** Import and harvest
   enqueue jobs; use `QueueRunnerTrait::runQueues(['localize_import', 'datastore_import'])`
   before asserting. This is the usual cause of empty or flaky import tests.
4. **Functional tests need a CI group.** CircleCI splits functional tests across nodes
   by `@group functional1|2|3`; an untagged one lands on the non-functional node. Copy
   the group tags of sibling tests in the module.
5. **Go through the storage factories:** `DataFactory → NodeData` (metastore),
   `DatabaseTableFactory → DatabaseTable` (datastore). Direct DB access bypasses the
   perspective and identifier mapping.
6. **Metastore items are nodes** of type `data` (`field_json_metadata`,
   `field_data_type`). The JSON schema is the source of truth; changing a shape means
   changing `schema/collections/*.json`, not just PHP.
7. **Schema, config, or stored-data changes need an update hook** in that submodule's
   `.install` (next free number in the file), plus an update-path test when data
   migrates.
8. **A mergeable PR** has a linked issue, tests, docs when behavior changes, clean
   phpcs (`Drupal,DrupalPractice` via `<dkan>/phpcs.xml`), and a green CircleCI matrix.

## Metadata (DCAT-US / Project Open Data)

1. **DKAN's dataset schema is Project Open Data v1.1** — not W3C DCAT RDF, not
   DCAT-US v3. `schema/collections/dataset.json` is authoritative for required fields
   and enums.
2. **Enums are exact:** `accessLevel` is `public` | `restricted public` | `non-public`;
   `accrualPeriodicity` is an ISO-8601 repeating interval (`R/P1Y`, `R/P3M`, …) or
   `irregular`, never a word like "annual".
3. **`downloadURL` is a direct file link and drives datastore import;** `accessURL` is
   a landing page or API. `contactPoint` and `publisher` are objects, not strings.
4. **Federal-only POD fields are not in DKAN's schema** (`bureauCode`, `programCode`,
   `landingPage`, `language`, `rights`, `dataQuality`, …). The schema does not set
   `additionalProperties: false`, so they pass through unvalidated rather than failing.
5. **`distribution.json`, `publisher.json`, etc. describe the `{identifier, data}`
   reference wrapper,** not the public field set. The real fields are in the dataset
   schema's embedded definitions.
6. **The catalog is `data.json`:** `{conformsTo, dataset: [...]}`. DKAN exports it at
   `/data.json` and harvests sources of the same shape.

## Decoupled frontend

1. **Three pieces:** the `dkan_js_frontend` Drupal module (serves the shell), a React
   app in `<webroot>/frontend`, and a component library the app consumes as a built npm
   dependency. Know which one you are editing.
2. **The module serves; it does not build.** It globs `*.js`/`*.css` from the
   configured `js_folder`/`css_folder` and attaches them. Build output in the wrong
   place gives a blank page.
3. **Routes are config.** `dkan_js_frontend.config` `routes` is a list of `name,/path`
   pairs turned into Drupal routes by `RouteProvider`. Add a config entry, not a
   `routing.yml` route.
4. **The SPA as site frontend needs `system.site` `page.front`, `page.403`, and
   `page.404` all set to `/home`** (`ddev dkan-frontend-install` does this). Otherwise
   deep links return Drupal's 404.
5. **`datastore_query_api` is the Drupal↔React coupling.** The config key is surfaced
   to `window.drupalSettings`; the library's `useDatastore` picks the route from it:
   false → `/datastore/query/{resourceId}`, true → `/datastore/query/{datasetId}/{index}`.
   A mismatch shows as an empty data table.
6. **Two incompatible library lineages:** legacy `@civicactions/data-catalog-components`
   (used by the `data-catalog-app` scaffold) and current
   `@civicactions/cmsds-open-data-components` (CMS Design System). Check the app's
   `package.json` before applying props or imports. Component-level detail lives in the
   library repo's `agent-docs/`.
7. **Local library edits not appearing** usually means npm-workspace version drift: the
   symlink only resolves when the app's `package.json` declares the version the local
   library advertises.
