# Extending DKAN Core From the Inside

Adding a built-in capability to the `drupal/dkan` package — as opposed to registering
one from a custom module (that's `dkan-module-author`'s
[`dkan-harvest.md`](../../dkan-module-author/reference/dkan-harvest.md) and the AI/MCP
scaffold commands). The pattern throughout: **find the canonical in-core example, copy
its shape, add a test, add an update hook if it changes stored data or config.** Don't
invent a new mechanism when DKAN already has one.

## DatasetInfo plugins

Contribute structured facts about a dataset (gathered for admin views, drush, the
`dataset-info` surface).

- Manager: `dkan_common/src/DatasetInfoPluginManager.php`; aggregator
  `dkan_common/src/DatasetInfo.php`.
- Plugins live in `*/src/Plugin/DatasetInfo/`. Canonical example:
  `dkan_datastore` ships `DatastoreInfo` (adds import/table facts).
- **To add one:** copy `DatastoreInfo` into your module's `src/Plugin/DatasetInfo/`,
  keep the same plugin discovery (annotation/attribute — match the example exactly,
  don't guess), implement the info-gathering method, `drush cr`.

## DkanApiDocs plugins

Contribute OpenAPI/Swagger fragments so an endpoint shows up in the generated API docs.

- Manager: `dkan_common/src/Plugin/DkanApiDocsPluginManager.php`; generator
  `dkan_common/src/DkanApiDocsGenerator.php`.
- Plugins in `*/src/Plugin/DkanApiDocs/`. Canonical example: `CommonApiDocs`
  (`dkan_common`). Metastore/datastore/harvest each ship their own.
- **To add one:** when you add or change a route, add/update the matching
  `DkanApiDocs` plugin so the docs don't drift from the API. Copy a sibling plugin.

## Datastore resource processors

Post-import hooks that run over a freshly imported resource (the extension seam for
"do X to every imported table").

- Interface + dir: `dkan_datastore/src/Service/ResourceProcessor/`. Canonical example:
  `DictionaryEnforcer` (applies a data-dictionary's column types to the imported table).
- Runs via the `PostImportResourceProcessor` queue worker after import completes.
- **To add one:** implement the processor interface (copy `DictionaryEnforcer`), wire
  it as a service tagged for the processor collection, and cover it with a kernel test
  that imports a small fixture and drains the queue
  ([testing-core.md](testing-core.md#async-and-queues)).

## Harvest ETL classes

Harvest is a class-string ETL pipeline (Extract → Transform → Load), assembled per
harvest plan by `dkan_harvest/src/ETL/Factory.php`.

- `src/ETL/Extract/` — `Extract`, `DataJson`, `ExtractInterface`.
- `src/ETL/Transform/` — `Transform` (base), `AddId`, `AddRandomNumber` (built-in
  examples).
- `src/ETL/Load/` — `Load`, `Simple`.

**To add a built-in transform/extractor:** subclass the base in the right `ETL/`
subdir, following `AddId` as the template. The **contract** (constructor signatures,
how the Factory instantiates by class-string from plan JSON, the run() shape) is
documented once in the module-author
[`dkan-harvest.md`](../../dkan-module-author/reference/dkan-harvest.md) — read it there
rather than re-deriving; the difference for a core contributor is only that your class
ships *in* `dkan_harvest` and may become a default.

## Queue workers

For new async/long-running work, add a Drupal `@QueueWorker` plugin under
`*/src/Plugin/QueueWorker/` (see the existing set: `ImportQueueWorker`,
`LocalizeQueueWorker`, `ResourcePurgerWorker`, `OrphanReferenceProcessor`, …). If the
work needs resumable state, build a `JobStore` via an `AbstractJobStoreFactory`
subclass rather than holding state in the queue item. Tests must drain the queue
([testing-core.md](testing-core.md#async-and-queues)).

## Adding a schema

A new metastore collection (or a field on an existing one) starts with JSON, not PHP —
the schema is the source of truth ([core-internals.md](core-internals.md#schema-validation)).

1. Add/edit the JSON Schema in `<dkan>/schema/collections/<name>.json` (and a
   `<name>.ui.json` if it needs a form). Match the existing files' draft/version and
   `$schema` conventions.
2. Confirm `SchemaRetriever` picks it up and `ValidMetadataFactory` validates sample
   metadata against it.
3. If you changed an **existing** schema in a way that affects stored data or config,
   add an update hook (`dkan_metastore_update_NNNN()` or the relevant module) — see
   [contributing-and-ci.md](contributing-and-ci.md#update-hooks).
4. Add a kernel test that posts valid + invalid metadata and asserts accept/reject.
   There are existing schema-check tests under
   `dkan_metastore/tests/src/Kernel/Install/` — mirror them.

> Schema changes ripple to the REST API response shape and the JSON form widget. A
> breaking shape change is an API-contract change — treat it as such (versioning,
> docs, `DkanApiDocs` update), not a quiet edit.
