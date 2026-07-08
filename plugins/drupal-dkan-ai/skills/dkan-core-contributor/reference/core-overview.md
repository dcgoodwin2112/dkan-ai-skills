# DKAN Core — Contributor Orientation

Where things live in the `drupal/dkan` package, how the repo relates to a running
site, and the dependency surface you inherit. Read this first.

This doc is **navigation**, not architecture. For the consumer-level model — what a
Distribution / Reference / Perspective *is*, the module dependency graph, service IDs
and event constants — read the `dkan-module-author` skill's
[`dkan-overview.md`](../../dkan-module-author/reference/dkan-overview.md) and
[`dkan-services.md`](../../dkan-module-author/reference/dkan-services.md). Don't
re-derive them here; this skill assumes them.

## Package vs. built site

DKAN ships as a single Drupal module package, **not** a site. Two things get conflated:

- **The package** (`drupal/dkan`, `type: drupal-module`) — the source you contribute
  to. Top level: `modules/`, `schema/`, `config/`, `tests/`, `cypress/`, `docs/`,
  plus `dkan.info.yml` / `dkan.install` / `dkan.module` and the dev infra
  (`.ddev/`, `.circleci/`, `phpcs.xml`, `phpunit.xml`).
- **A built site** that installs it — e.g. a recommended-project checkout where the
  package sits at `docroot/modules/contrib/dkan/` (or is symlinked there for dev).
  In the local `dkan-core/` layout: `dkan/` is the package, `docroot/` is the built
  site, `vendor/` is Composer's.

When this skill says `<dkan>/`, it means the **package** root. Edit there. The DDEV
dev loop (below) symlinks the package into a throwaway site so tests run against real
Drupal without you hand-building one.

## Module tree

Core modules (each depends on `dkan_common`; load in dependency order):

| Module | Responsibility |
|---|---|
| `dkan_common` | Shared infra: storage factories, `JobStore`, plugin managers (DatasetInfo, DkanApiDocs), file-fetcher wiring, stream wrapper, base APIs |
| `dkan_metastore` | Metadata catalog — JSON stored as Drupal `data` nodes; CRUD service, schema validation, the reference lifecycle |
| `dkan_datastore` | Tabular import — CSV → per-resource DB tables; the datastore query API; resource processors |
| `dkan_harvest` | ETL ingestion of external `data.json` catalogs into the metastore; harvest plans/runs/hashes |
| `dkan_js_frontend` | Decoupled React frontend integration |
| `dkan_sample_content` | Demo datasets + fixtures |

Submodules (optional, under their parent's `modules/`): `dkan_metastore_search`,
`dkan_metastore_admin`, `dkan_data_dictionary_widget` (under metastore);
`dkan_datastore_mysql_import` (under datastore). Each submodule has its **own**
`.info.yml`, `.install`, and `tests/`.

```
<dkan>/
  modules/dkan_{common,metastore,datastore,harvest,js_frontend,sample_content}/
    src/                      # the code you change
    tests/src/{Unit,Kernel,Functional}/   # in-repo PHPUnit (see testing-core.md)
    dkan_<name>.{info.yml,install,services.yml,routing.yml,module}
    modules/<submodule>/      # nested submodules
  schema/collections/*.json   # DCAT-US metadata schemas — the source of truth
  tests/fixtures/update/*.php.gz   # gzipped DB dumps for update-path tests
  cypress/e2e/*.cy.js         # browser e2e
  .ddev/ .circleci/ phpcs.xml phpunit.xml   # dev infra
```

## Package identity & branches

- **Package:** `drupal/dkan`, `type: drupal-module`, `core_version_requirement: ^10.2 || ^11`, `package: DKAN`.
- **Development:** GitHub **`GetDKAN/dkan`**. Active long-lived branches: `2.x`, `3.x`,
  `4.x`. Feature branches target one of these; PRs merge back to it.
- **Targeting:** confirm which branch your change is for and verify every fact against
  it (`git show 4.x:<path>`). A working tree often sits ahead of, or aside from,
  mainline. See [core-internals.md](core-internals.md#schema-validation) for a live
  example where the checkout's deps differ from `4.x`.

## The `getdkan/*` dependency surface

DKAN factors a lot of logic into small `getdkan/*` libraries (Composer, not Drupal
modules). When a bug is "in DKAN" it's often in one of these — know where the seam is.
On **`4.x`** (`composer.json`):

| Dependency | Role |
|---|---|
| `getdkan/contracts` (^1.2) | Factory / retriever interfaces DKAN implements |
| `getdkan/procrastinator` (^5.0.3) | Async, resumable job execution — the import/harvest queue engine |
| `getdkan/csv-parser` (^1.3.3) | CSV parsing for datastore import |
| `getdkan/file-fetcher` (^5.1) | Resumable remote-file download (resource localization) |
| `getdkan/rooted-json-data` (^1.0) | `RootedJsonData` — JSON-path-addressable, schema-validated metadata wrapper |
| `getdkan/pdlt` (^0.1.7) | Date/format helper |
| `opis/json-schema` (^2.4) | Metastore schema validation (see the validator note below) |
| `justinrainbow/json-schema` (^5.2 \|\| ^6.6.1) | Still required on some validation paths |

> A change that touches CSV handling, file download, or queue/job state usually means
> a PR (and version bump) to the corresponding `getdkan/*` repo — not just `drupal/dkan`.
> The justinrainbow → opis validator migration **landed on `4.x`** — current state
> and gotchas live in [core-internals.md](core-internals.md#schema-validation) (the
> single home for that fact).

## REST API surface

Routes/controllers live per module (`dkan_<name>.routing.yml` + `src/Controller/`,
plus harvest's `src/WebServiceApi.php`). The endpoint **shapes** and permissions are
documented from the consumer side in
[`dkan-api.md`](../../dkan-module-author/reference/dkan-api.md) — read that rather than
re-tracing routes. What matters for a contributor: the REST API is the **stability
contract**, so changing a response shape is a breaking change requiring deliberate
versioning, while internal service signatures are not contractually frozen.
