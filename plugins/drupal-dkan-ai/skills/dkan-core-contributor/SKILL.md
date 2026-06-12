---
name: dkan-core-contributor
description: Reference and decision support for contributing to DKAN core itself — modifying the drupal/dkan package source (dkan_common, dkan_metastore, dkan_datastore, dkan_harvest), its internals, tests, and CI. Loads when editing files under modules/contrib/dkan/ or a dkan/ package checkout, changing Drupal\dkan_common\*, Drupal\dkan_metastore\*, Drupal\dkan_datastore\*, or Drupal\dkan_harvest\* core classes, adding/altering DKAN core PHPUnit/Cypress tests, or working on DKAN's phpcs/CircleCI setup. For building custom modules that *use* DKAN, use dkan-module-author instead. Targets DKAN 4.x (GitHub GetDKAN/dkan) on Drupal ^10.2 || ^11.
---

# DKAN Core Contributor's Reference

This skill loads when you're working **inside** the DKAN codebase — changing core
behavior, fixing a bug in `dkan_metastore`, adding a built-in plugin, or making a
test/CI change land mergeably. Its job is to surface the internals and contribution
mechanics that are non-obvious from the code alone, and to point you at the right
detail doc.

> **Which skill?** This skill is for contributing **to** DKAN core (`drupal/dkan`).
> If you're writing a custom module under `modules/custom/` that *consumes* DKAN's
> services / REST API / events, that's **`dkan-module-author`** — use it instead.
> The two overlap on namespaces (`Drupal\dkan_*`) but differ in perspective: this
> one modifies the package; that one builds against it.

> **Path convention**: the DKAN package root is written `<dkan>/` — that's
> `modules/contrib/dkan/` in a built site (e.g. `dkan-core/docroot/...`) or a
> standalone `dkan/` checkout. Substitute your actual path.

> **Verify against the target branch, not the checkout.** Canonical package is
> `drupal/dkan`; development is on GitHub **`GetDKAN/dkan`** across active `2.x`,
> `3.x`, and `4.x` branches. A working tree may sit on a feature branch whose APIs
> and dependencies differ from mainline. Before relying on a class, signature, or
> dependency, confirm it on the branch you're targeting: `git show 4.x:<path>`.
> (Concrete example: a `justinrainbow/json-schema` → `opis/json-schema` migration
> lives on a feature branch and is **not** on `4.x` — see
> [reference/core-internals.md](reference/core-internals.md#schema-validation).)

## Pick the right doc for the task

| Task | Read |
|---|---|
| Orienting: where modules/schema/tests live, package identity, the `getdkan/*` deps | [reference/core-overview.md](reference/core-overview.md) |
| The storage/factory indirection, schema validation, the reference lifecycle, queues | [reference/core-internals.md](reference/core-internals.md) |
| Adding a built-in plugin (DatasetInfo, DkanApiDocs, ResourceProcessor), a harvest ETL class, a queue worker, or a new metastore schema | [reference/extending-core.md](reference/extending-core.md) |
| Writing or running a DKAN core test (PHPUnit suites, base classes, traits, `@group`) | [reference/testing-core.md](reference/testing-core.md) — or run `/dkan-core-test` to scaffold one |
| DDEV setup, phpcs/standards, CI gates, update hooks, opening a PR | [reference/contributing-and-ci.md](reference/contributing-and-ci.md) |
| Publishing a contrib module on drupal.org GitLab (MRs, drupalcode CI) — *not* DKAN core's GitHub flow | [drupal-module-dev/drupalorg-gitlab.md](../drupal-module-dev/reference/drupalorg-gitlab.md) |
| Consumer concerns: injecting a DKAN service, the REST API shapes, events, custom-module patterns | [../dkan-module-author/SKILL.md](../dkan-module-author/SKILL.md) — don't re-derive these here |

## Always-true rules (the things people get wrong on first attempt)

These are the contributor-specific concepts that aren't visible from a quick grep.

1. **Verify facts against the branch you target (`4.x`), not the checked-out branch.** Feature branches change signatures and deps. `git show 4.x:<path>` / `git diff 4.x -- <path>` before asserting an API exists. See the JSON-schema-library migration in [core-internals.md](reference/core-internals.md#schema-validation) for why this bites.
2. **Tests run in-repo via `ddev phpunit` against a real Drupal kernel** — this is **not** the standalone-stub harness `dkan-module-author` describes (that one is for testing *custom* modules in isolation). Different harness, different base classes; don't mix the patterns. See [testing-core.md](reference/testing-core.md).
3. **Async work doesn't run in a test unless you pump the queue.** Datastore import and harvest enqueue Procrastinator jobs; asserting on results without draining the queue yields empty/flaky tests. Use `QueueRunnerTrait`. See [testing-core.md](reference/testing-core.md#async-and-queues).
4. **Functional tests need a `@group functionalN`** (N = 0–3) or CI's parallelized split won't run them; all DKAN tests also carry `@group dkan`. A green local run with no group annotation silently never runs in CI.
5. **Never reach past the storage-factory layer to hit the DB directly.** Business logic goes through `DataFactory→NodeData` (metastore) and `DatabaseTableFactory→DatabaseTable` (datastore), both atop `dkan_common`'s `AbstractDatabaseTable` / `StorageFactoryInterface`. Direct queries break the abstraction, the perspective/UUID mapping, and tests. See [core-internals.md](reference/core-internals.md#storage).
6. **Metastore items are Drupal nodes** (type `data`, fields `field_json_metadata` + `field_data_type`), not a custom entity. The JSON in `<dkan>/schema/collections/*.json` is the source of truth; validation flows through `RootedJsonData` via `ValidMetadataFactory`. Changing a shape means changing the schema, not just PHP.
7. **Schema / config / DB-shape changes require an update hook** — `<module>_update_NNNN()` (9xxx series) in *that submodule's* `.install` — and, where it alters stored data, a fixture-backed update-path test. See [contributing-and-ci.md](reference/contributing-and-ci.md#update-hooks).
8. **A mergeable PR passes phpcs `Drupal,DrupalPractice` and the full CircleCI matrix, and includes tests + docs + a linked issue.** There is no PHPStan gate. See [contributing-and-ci.md](reference/contributing-and-ci.md).

## Top pitfalls

The most expensive mistakes when changing DKAN core. Symptom → cause → fix.

1. **Import/harvest test asserts on rows that aren't there.** Symptom: count is 0, or the table doesn't exist. Cause: the import job sat in the queue and never ran. Fix: pull in `QueueRunnerTrait` and drain the queue in the test ([testing-core.md](reference/testing-core.md#async-and-queues)).
2. **New test runs on the wrong CI node (or not in parallel).** Cause: missing/incorrect `@group functionalN`. Fix: tag functional tests `@group functional1`, `2`, or `3` (node 0 runs the non-functional suite) plus `@group dkan`.
3. **Relying on a class/method/dep that only exists on a feature branch.** Symptom: "works on my checkout," fails review/CI on `4.x`. Cause: asserted against the wrong branch. Fix: `git show 4.x:<path>` to confirm before coding.
4. **"Fixing DKAN" while actually editing a copy under `modules/custom/`.** Cause: wrong tree/perspective. Fix: confirm you're in `<dkan>/` core source (the `drupal/dkan` package), not a vendored custom module; if it's a custom module, switch to `dkan-module-author`.
5. **Schema or config change merged with no update hook.** Symptom: existing sites error on `drush updatedb` / config import. Fix: add `<module>_update_NNNN()` in the right `.install` ([contributing-and-ci.md](reference/contributing-and-ci.md#update-hooks)).
6. **Querying a datastore table by name directly.** Symptom: table-not-found or wrong rows. Cause: bypassing the factory + UUID/perspective mapping. Fix: resolve through `DatastoreService` / the table factory, not a raw `SELECT`.

## Core-internals cheat sheet

The load-bearing indirection and the in-core extension points (full detail in
[core-internals.md](reference/core-internals.md) and
[extending-core.md](reference/extending-core.md)):

| Layer / extension point | Where |
|---|---|
| Storage factory contract | `<dkan>/modules/dkan_common/src/Storage/{StorageFactoryInterface,AbstractDatabaseTable,JobStore}.php` |
| Metastore storage | `<dkan>/modules/dkan_metastore/src/Storage/{DataFactory,NodeData}.php` |
| Datastore storage | `<dkan>/modules/dkan_datastore/src/Storage/{DatabaseTableFactory,DatabaseTable}.php` |
| Reference lifecycle | `<dkan>/modules/dkan_metastore/src/LifeCycle/LifeCycle.php` + `src/Reference/{Referencer,Dereferencer,ReferenceLookup,OrphanChecker}.php` |
| Schema source of truth | `<dkan>/schema/collections/*.json` + `dkan_metastore/src/{SchemaRetriever,ValidMetadataFactory}.php` |
| DatasetInfo plugin | `<dkan>/modules/dkan_common/src/DatasetInfoPluginManager.php`; plugins in `*/src/Plugin/DatasetInfo/` |
| API-docs plugin | `<dkan>/modules/dkan_common/src/Plugin/DkanApiDocs/`; manager `DkanApiDocsPluginManager.php` |
| Datastore resource processor | `<dkan>/modules/dkan_datastore/src/Service/ResourceProcessor/` (e.g. `DictionaryEnforcer.php`) |
| Harvest ETL | `<dkan>/modules/dkan_harvest/src/ETL/{Extract,Transform,Load}/` + `Factory.php` |
| Queue workers | `*/src/Plugin/QueueWorker/` (`ImportQueueWorker`, `LocalizeQueueWorker`, …) |

```bash
# from the DKAN package root, in a DDEV project:
ddev phpunit --filter MyTest                 # in-repo PHPUnit (kernel/functional/unit)
ddev dkan-module-test-cypress                # Cypress e2e
ddev exec vendor/bin/phpcs --standard=Drupal,DrupalPractice modules/dkan_metastore
git show 4.x:composer.json                   # check a fact on the target branch
```

## Version notes

- Targets **DKAN 4.x** on Drupal `^10.2 || ^11`. CI exercises Drupal ~10.5 / ~10.6 / ~11.2 / ~11.3 across PHP 8.1–8.4 (mysql 5.7 + mariadb 10.11) — see [contributing-and-ci.md](reference/contributing-and-ci.md#ci).
- DKAN 4.x submodules carry the `dkan_` prefix (`dkan_common`, `dkan_metastore`, `dkan_datastore`, `dkan_harvest`); pre-4.x un-prefixed names are gone.
- Internal APIs (service signatures, event constants, storage internals) are **not** guaranteed stable across DKAN minors — they're fair game to change in a core PR, which is exactly why downstream consumers get a stability contract only on the REST API and documented service IDs.
- Dependencies in this doc reflect **`4.x`**; confirm with `git show 4.x:composer.json` since the working tree may be ahead of mainline.
