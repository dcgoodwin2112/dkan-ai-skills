# Testing DKAN Core

DKAN core tests run **in-repo against a real Drupal kernel** via `ddev phpunit`. This
is a different harness from the one the `dkan-module-author` skill describes in
[`dkan-testing.md`](../../dkan-module-author/reference/dkan-testing.md) — that one is a
**standalone**, no-bootstrap PHPUnit run where DKAN classes are supplied by local
stubs, for testing a *custom* module in isolation. **Do not mix them up:** inside core
you have the real services, real DB, and DKAN's own base classes and traits — you do
not write stubs for DKAN classes.

## The in-repo harness

- Config: `<dkan>/phpunit.xml` — a single `default` testsuite scanning `.`; coverage
  spans `src` + each module's `tests`.
- Tests live per module at `<dkan>/modules/<module>/tests/src/{Unit,Kernel,Functional}/`
  (submodules have their own `tests/` too), namespace
  `Drupal\Tests\<module>\<Type>`.
- Run with `ddev phpunit` (the `phpunit` command comes from the `ddev-drupal-contrib`
  addon, not a project `require-dev`).

## Test types and base classes

| Type | Base class | Bootstrap | Use for |
|---|---|---|---|
| Unit | `Drupal\Tests\UnitTestCase` | none | pure logic, mocked collaborators |
| Kernel | `Drupal\KernelTests\KernelTestBase`; `ConfigFormTestBase` (`dkan_common/tests/src/Kernel/`) for config forms | minimal container + DB | service behavior, storage, import with a real DB |
| Functional | `Drupal\Tests\BrowserTestBase`; **`Api1TestBase`** (`dkan_common/tests/src/Functional/`) for REST API tests | full site | end-to-end HTTP, the `/api/1/*` surface |

`Api1TestBase` gives you an authenticated HTTP client and OpenAPI-aware assertions for
the v1 API — extend it for anything exercising metastore/datastore/harvest endpoints
rather than re-wiring a client. Most DKAN coverage is **kernel** tests (real services,
fast-ish); reserve functional/browser tests for the HTTP and UI seams.

## DKAN test traits

In `<dkan>/modules/dkan_common/tests/src/Traits/` — reuse these, don't reinvent:

| Trait | Gives you |
|---|---|
| `QueueRunnerTrait` | drain DKAN queues inside a test (see below) |
| `CleanUp` | tear down datasets/datastore tables/harvest state between tests |
| `GetDataTrait` | load sample dataset/resource JSON fixtures |
| `ServiceCheckTrait` | assert/guard on service availability |

## Async and queues

Import and harvest **enqueue** Procrastinator jobs
([core-internals.md](core-internals.md#queues-and-jobs)); the work doesn't happen until
the queue runs. A test that imports then immediately asserts on rows will see nothing.

Pattern: pull in `QueueRunnerTrait`, kick off the work, then drain the relevant
queue(s) before asserting:

```php
use Drupal\Tests\dkan_common\Traits\QueueRunnerTrait;

// in the test, after triggering an import/harvest:
$this->runQueues(['localize_import', 'datastore_import']);   // names per the workers under test
// now the datastore table exists and is populated — assert on it.
```

Match the queue names to the workers your code path uses
(`localize_import`, `datastore_import`, post-import, orphan cleanup, …). Forgetting
this is the #1 cause of flaky/empty DKAN import tests.

## Test groups

CI parallelizes by **group** (`parallelism: 4`). Two conventions:

- Every DKAN test carries `@group dkan`.
- Functional tests are bucketed into **three** groups, `@group functional1` … `@group
  functional3`. Node 0 runs the non-functional suite (`--exclude-group
  functional1,functional2,functional3` — unit + kernel); nodes 1–3 each run `--group
  functional1`/`2`/`3`. A functional test left untagged (or tagged `functional0`, which
  CI does not use) is **not** parallelized onto a functional node — it lands in node 0's
  run alongside unit/kernel.

```php
/**
 * @group dkan
 * @group functional2
 */
final class MyApiTest extends Api1TestBase { /* … */ }
```

Pick `functional1`, `2`, or `3` to keep the three functional nodes roughly balanced
(glance at where sibling tests in the module are assigned).

## Cypress e2e

Browser/UI coverage lives in `<dkan>/cypress/e2e/*.cy.js`, fixtures in
`cypress/fixtures/`. Run with `ddev dkan-module-test-cypress` (it provisions the
`testadmin` user, runs specs, cleans up). CI splits specs by timing across nodes. Add
e2e only for genuinely UI-level behavior; prefer kernel/functional PHPUnit for API and
service logic.

## Update-path tests and fixtures

DKAN tests the database **update path** (old site → run `update.php` → assert) using
gzipped DB dumps under `<dkan>/tests/fixtures/update/*.php.gz`. These are produced from
a built site via Drupal's `core/scripts/db-tools.php dump-database-d8-mysql | gzip`,
not hand-written. If you add an update hook that migrates stored data
([contributing-and-ci.md](contributing-and-ci.md#update-hooks)), add or update a
fixture-backed test so the migration is exercised.

## Commands

```bash
ddev phpunit --filter MyTest                         # one test
ddev phpunit modules/dkan_metastore/tests            # one module's suite
ddev phpunit --group dkan --group functional1        # mimic a functional CI node
ddev dkan-module-test-cypress                        # e2e
```

> Run the relevant suite before opening a PR — CI runs the whole matrix, but failing
> tests you could have caught locally waste a review cycle. New code needs tests
> (it's a PR requirement — [contributing-and-ci.md](contributing-and-ci.md)).
