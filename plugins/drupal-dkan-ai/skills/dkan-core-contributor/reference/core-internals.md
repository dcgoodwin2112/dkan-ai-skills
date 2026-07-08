# DKAN Core Internals (at modification depth)

The indirection that makes DKAN testable and pluggable — and that trips up
contributors who try to take shortcuts through it. This is the consumer model from
[`dkan-overview.md`](../../dkan-module-author/reference/dkan-overview.md) viewed from
the inside: not "which service do I call" but "what will I break if I change this."

## Storage

DKAN business logic **never touches the database directly**. Every persistent read or
write goes through a factory that returns a storage object implementing a shared
contract. This is the single most important internal convention.

The contract lives in `dkan_common`:

- `src/Storage/StorageFactoryInterface.php` — `getInstance($identifier, $config)`.
- `src/Storage/AbstractDatabaseTable.php` — base for DB-backed storage (CRUD + query);
  implements `DatabaseTableInterface`.
- `src/Storage/JobStore.php` + `AbstractJobStoreFactory.php` — durable job state (see
  [queues](#queues-and-jobs)).
- `src/Storage/{Query,SelectFactory}.php` — query abstraction over Drupal's DB layer.

Two concrete factory→object pairs sit on top:

| Subsystem | Factory | Storage object | Backs |
|---|---|---|---|
| Metastore | `dkan_metastore/src/Storage/DataFactory.php` | `NodeData` (`src/Storage/NodeData.php`) | a Drupal `data` node, per schema |
| Datastore | `dkan_datastore/src/Storage/DatabaseTableFactory.php` | `DatabaseTable` (`src/Storage/DatabaseTable.php`, `SqliteDatabaseTable` variant) | one DB table per imported resource |

**Why it matters for a change:**
- `DataFactory::getInstance('dataset')` returns `NodeData` — a wrapper over a node, not
  the node. Bypassing it (loading nodes directly, querying `node__field_json_metadata`)
  skips validation, the reference lifecycle, and cache handling, and breaks the
  abstraction tests assume.
- Datastore table names are derived (`datastore_` + a hash of the resource unique
  identifier), not the resource ID — resolve them through the factory /
  `DatastoreService`, never by string-building. The resource-ID/perspective rules are
  in [`dkan-overview.md`](../../dkan-module-author/reference/dkan-overview.md#key-concepts)
  and the always-true rules of the module-author skill; they apply unchanged here.
- Adding a backend (e.g. another DB engine) means a new storage class against the
  existing interface + a factory tweak — not new call sites.

Service IDs for these are in
[`dkan-services.md`](../../dkan-module-author/reference/dkan-services.md); don't
re-list them — look there.

## Schema validation

Metastore content is **JSON validated against a schema**, stored on **Drupal nodes**.
There is no per-schema entity type: every metastore item is a node of type `data` with
two load-bearing fields — `field_json_metadata` (the JSON blob) and `field_data_type`
(the schema id, e.g. `dataset`, `distribution`, `publisher`, `theme`, `keyword`,
`data-dictionary`).

The flow:

1. **Schemas** are JSON files in `<dkan>/schema/collections/*.json` (DCAT-US +
   DKAN-specific). These are the **source of truth** — a shape change is a schema
   change, not just a PHP change.
2. `dkan_metastore/src/SchemaRetriever.php` loads them at runtime.
3. `dkan_metastore/src/ValidMetadataFactory.php` wraps a JSON string + its schema into
   a `RootedData\RootedJsonData` (`getdkan/rooted-json-data`) — JSON-path-addressable
   and schema-validated. Invalid metadata throws here.

> **Validator-library caveat (verify your branch).** The justinrainbow → opis
> migration **landed on `4.x`** (verified 2026-07-08: PR #4706 "Migrate to
> opis/json-schema v2" + #4730, which adds the Opis-based
> `dkan.metastore.schema_validator` service, `Drupal\dkan_metastore\SchemaValidator`).
> `4.x` now requires **both** libraries — `opis/json-schema ^2.4` (metastore schema
> validation) and `justinrainbow/json-schema ^5.2 || ^6.6.1` (still used on some
> paths, e.g. the datastore query controller) — with `getdkan/rooted-json-data ^1.0`;
> the `m1x0n` error presenter was dropped. Checkouts from either side of that merge
> disagree with mainline: confirm with `git show 4.x:composer.json` before writing
> schema/validation code or tests — error shapes and edge cases differ between the
> two libraries. **This callout is the single home for this fact; other docs link
> here.**

Adding or changing a schema affects validation, the API, and the JSON form widget — and
usually needs an update hook. See [extending-core.md](extending-core.md#adding-a-schema).

## The reference lifecycle

Nested, reusable objects (publisher, distribution, keyword, theme, data dictionary)
are **not** stored inline. They're decoupled into their own `data` nodes referenced by
UUID, then re-expanded on read. This is DKAN's most surprising internal behavior; the
machinery is in `dkan_metastore`:

- `src/LifeCycle/LifeCycle.php` — the orchestrator, driven by entity hooks
  (`hook_entity_presave/update/load/predelete` in `dkan_metastore.module`). Each hook
  routes to a `LifeCycle` stage.
- `src/Reference/Referencer.php` — **on write**: extracts referenceable properties,
  hashes + dedupes them, replaces inline objects with UUID references, creating/reusing
  child `data` nodes.
- `src/Reference/Dereferencer.php` — **on read**: expands UUID references back into full
  objects, surfacing resolution metadata under `%Ref:` keys (the
  `%Ref:downloadURL[*]['data']` shape the module-author skill warns about).
- `src/Reference/ReferenceLookup.php` — finds which items reference a given UUID
  (so you know what breaks if you delete it).
- `src/Reference/OrphanChecker.php` — on delete/update, queues now-unreferenced children
  for cleanup (a queue worker removes them — see below).

**What this means for a change:** edit metadata write logic and you're almost certainly
inside `Referencer`/`LifeCycle`; touching either risks orphaning child nodes or
double-creating references. The consumer-facing consequence ("references decouple nested
objects," "publish vs. draft") is an always-true rule in the
[module-author SKILL.md](../../dkan-module-author/SKILL.md) — same
behavior, here you own its correctness.

## Queues and jobs

Long-running work — datastore import, resource localization (download), post-import
processing, orphan cleanup — runs as **Procrastinator** jobs (`getdkan/procrastinator`),
not inline. Jobs carry **resumable state** in a `JobStore` table, so a partial import
can continue after a timeout/interruption rather than restarting.

- Queue workers (Drupal `@QueueWorker` plugins) live in `*/src/Plugin/QueueWorker/`:
  `ImportQueueWorker`, `LocalizeQueueWorker`, `PostImportResourceProcessor`,
  `ResourcePurgerWorker`, `OrphanReferenceProcessor`, `OrphanResourceRemover`, and the
  Procrastinator `ImportJob`.
- State is keyed in `JobStore` (built via `dkan_datastore/src/Storage/ImportJobStoreFactory.php`
  and `dkan_common`'s `AbstractJobStoreFactory`).

**The testing consequence is unavoidable:** enqueuing is not executing. A test that
imports a CSV and immediately asserts on rows sees nothing until the queue is drained.
Pump it with `QueueRunnerTrait` — see
[testing-core.md](testing-core.md#async-and-queues). In production the queue is drained
by cron / `drush queue:run` (or `ddev drush rq`).
