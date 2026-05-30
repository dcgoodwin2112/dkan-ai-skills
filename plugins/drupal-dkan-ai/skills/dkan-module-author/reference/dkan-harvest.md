# Authoring DKAN Harvest ETL Components

## Key insight: ETL components are plain PHP classes, NOT Drupal plugins

Harvest extractors, transformers, and loaders are **plain PHP classes referenced by fully-qualified class name (FQN) as strings in the harvest plan JSON**. There is:

- **No plugin attribute** (no `#[...]`, no `*.plugin.yml`)
- **No plugin manager** and no discovery
- **No `drush cr` needed** to register a new component — the class only needs to be autoloadable (i.e. PSR-4 under any enabled module's `src/`)

The ETL factory instantiates them directly via `new $class(...)` after a bare `class_exists()` check.

**Verified:** `Drupal\dkan_harvest\ETL\Factory::get()` reads `$plan->extract->type`, each entry in `$plan->transforms`, and `$plan->load->type` as class-strings, calls `validateClass()` (just `class_exists`), then `new $class(...)`.
File: `<webroot>/modules/contrib/dkan/modules/dkan_harvest/src/ETL/Factory.php` (lines 80-125, 178-184).

## The three contracts

All live under namespace `Drupal\dkan_harvest\ETL\*`.

### Extract

```php
interface ExtractInterface {
  public function run(): array;  // returns array of PHP objects, keyed by id
}
```
File: `.../src/ETL/Extract/ExtractInterface.php`.

Extend the abstract base instead of implementing the interface directly. The base's `run()` calls your `getItems()`, then **enforces that items are non-empty and that the first item is a PHP object** (throws otherwise).

```php
abstract class Extract implements ExtractInterface {
  public function run(): array;            // final-ish; validates then returns getItems()
  abstract protected function getItems();  // implement this; return array of objects
}
```
File: `.../src/ETL/Extract/Extract.php` (lines 13-35).

Constructor signature is **not** fixed by the base, but the Factory calls extract with `new $class($harvestPlan, $client)`. The plan object and a Guzzle client (may be NULL) are passed positionally.
Reference impl: `Drupal\dkan_harvest\ETL\Extract\DataJson` — `__construct(object $harvest_plan, ?ClientInterface $client = NULL)`, reads `$harvestPlan->extract->uri`, supports `file://` and HTTP. File: `.../src/ETL/Extract/DataJson.php`.

### Transform

```php
abstract class Transform {
  public function __construct(object|string $harvest_plan);
  abstract public function run(object $item);  // return the transformed item
}
```
File: `.../src/ETL/Transform/Transform.php`.

**The return value of `run()` becomes the item.** The Harvester replaces the working item with whatever `run()` returns: `$transformed_item = $transformer->run($transformed_item)`. Transforms run **per item**, chained in plan order.
File: `.../src/Harvester.php` (`executeTransformersSingle()` lines 186-204, `transform()` lines 217-228).

The Harvester already passes a `clone` of the item into each transform, so cloning inside `run()` is optional. Reference impl `AddId` clones, mutates the clone, but returns the **original** `$item` — copy this pattern carefully; whatever you return is what propagates downstream. File: `.../src/ETL/Transform/AddId.php`.

### Load

```php
abstract class Load {
  public function __construct(object $harvest_plan, object $hash_storage, object $item_storage);
  public function run(object $item): int;          // provided: hash-compares then calls saveItem
  abstract protected function saveItem(object $item);  // implement this
}
```
File: `.../src/ETL/Load/Load.php`.

The base `run()` does change-detection via hash storage and returns one of the `Harvester` constants: `HARVEST_LOAD_NEW_ITEM` (0), `HARVEST_LOAD_UPDATED_ITEM` (1), `HARVEST_LOAD_UNCHANGED` (2). It only calls your `saveItem()` for new/updated items. File: `.../src/Harvester.php` (lines 12-14).

To support `revertHarvest()`, also implement `removeItem(string $id): void` — the Harvester checks `method_exists($load, 'removeItem')` and throws if missing. File: `.../src/Harvester.php` (`revert()` lines 41-57).

Reference impls:
- `Drupal\dkan_harvest\ETL\Load\Simple` — stores JSON to item storage, has `removeItem()`. File: `.../src/ETL/Load/Simple.php`.
- `Drupal\dkan_harvest\Load\Dataset` — the production loader; writes into the metastore. Note this one lives under `Drupal\dkan_harvest\Load` (**not** `...\ETL\Load`). File: `.../src/Load/Dataset.php`.

## Harvest plan JSON structure

Schema-validated shape (`.../schema/schema.json`, draft-07). Required: `identifier`, `extract` (with `type`+`uri`), `load` (with `type`). `transforms` is an optional array of class-strings.

```json
{
  "identifier": "my_harvest",
  "extract": {
    "type": "\\Drupal\\dkan_harvest\\ETL\\Extract\\DataJson",
    "uri": "https://example.com/data.json"
  },
  "transforms": [
    "\\Drupal\\dkan_harvest\\ETL\\Transform\\AddId"
  ],
  "load": {
    "type": "\\Drupal\\dkan_harvest\\Load\\Dataset"
  }
}
```

`type` / transform entries are **FQN strings** (leading `\` optional; Factory passes them straight to `new`). The plan is validated against the schema by `Factory::validateHarvestPlan()` before any ETL runs (Opis JSON Schema validator). File: `.../src/ETL/Factory.php` (lines 138-165).

Real example to copy from: `.../tests/files/plan.json`.

> Note: `config/samples/harvest-plan-example.json` uses legacy keys (`sourceId`/`source`) and bare class names — it is **stale** and will not validate against the current schema. Use the structure above.

## HarvestService API

Service ID: `dkan.harvest.service` → `Drupal\dkan_harvest\HarvestService`.
File: `.../src/HarvestService.php`; service def `.../dkan_harvest.services.yml`.

```php
getAllHarvestIds(bool $has_run_record = FALSE): array       // plan IDs
getHarvestPlan(string $plan_id): ?string                    // plan as JSON string
getHarvestPlanObject(string $plan_id): ?object
registerHarvest(object $plan): string                       // validates + stores; returns identifier
deregisterHarvest(string $plan_id): bool                    // drops plan + its support tables
runHarvest(string $plan_id): array                          // runs ETL, stores run, returns result
revertHarvest(string $id): int                              // removes loaded items (needs Load::removeItem)
getHarvestRunInfo(string $plan_id, string $timestamp): bool|string
getHarvestRunResult(string $plan_id, ?string $timestamp = NULL): array
getRunIdsForHarvest(string $plan_id): array
publish(string $harvestId): array                           // publish last run's datasets; returns UUIDs
archive(string $harvestId): array                           // archive last run's datasets; returns UUIDs
validateHarvestPlan(object $plan): bool                     // proxies Factory::validateHarvestPlan
```

`registerHarvest()` takes a **plan object** (decoded JSON) with an `identifier` property; it validates against the schema and stores. `runHarvest()` throws if extraction yields zero items.

Run from CLI with `drush dkan:harvest:*` commands (see the drush reference for specifics) — they wrap this service.

## Minimal worked example: a custom Extract

Place in any enabled module, e.g. `<webroot>/modules/custom/my_module/src/Harvest/Extract/CsvRows.php`:

```php
<?php

namespace Drupal\my_module\Harvest\Extract;

use Drupal\dkan_harvest\ETL\Extract\Extract;

/**
 * Extract dataset items from a local CSV manifest.
 */
class CsvRows extends Extract {

  public function __construct(object $harvest_plan, $client = NULL) {
    $this->harvestPlan = $harvest_plan;
  }

  protected function getItems(): array {
    $rows = array_map('str_getcsv', file($this->harvestPlan->extract->uri));
    $header = array_shift($rows);
    $items = [];
    foreach ($rows as $row) {
      $item = (object) array_combine($header, $row);
      // Key by identifier; base run() requires non-empty array of objects.
      $items[$item->identifier] = $item;
    }
    return $items;
  }

}
```

Reference it in the plan by FQN — no rebuild, no cache clear, just make sure the module is enabled so the class autoloads:

```json
{
  "identifier": "csv_harvest",
  "extract": {
    "type": "\\Drupal\\my_module\\Harvest\\Extract\\CsvRows",
    "uri": "file:///var/www/data/manifest.csv"
  },
  "load": { "type": "\\Drupal\\dkan_harvest\\Load\\Dataset" }
}
```

The same approach applies to custom Transform (extend `...\ETL\Transform\Transform`, implement `run()`) and Load (extend `...\ETL\Load\Load`, implement `saveItem()` and optionally `removeItem()`).

## Pitfalls

- **Looking for a plugin manager — there isn't one.** No attribute, no annotation, no discovery, no `drush cr`. The class is referenced purely by FQN string in the plan.
- **Forgetting transforms must return the item.** The return value of `Transform::run()` becomes the working item. Mutate and `return $item;` — returning `void`/`NULL` drops the data.
- **Extracted items must be a non-empty array of PHP objects** keyed by id. The base `Extract::run()` throws if empty or if the first value isn't an object. Use `(object)` casts, not arrays.
- **`saveItem()` only fires for new/changed items.** The base `Load::run()` short-circuits unchanged items via hash comparison; don't put required side effects only in `saveItem()` if they must run every harvest.
- **`Dataset` loader is not under `ETL`.** It's `Drupal\dkan_harvest\Load\Dataset`; the abstract base and `Simple` are under `Drupal\dkan_harvest\ETL\Load`.
- **`revertHarvest()` needs `removeItem()`.** Without it the Harvester throws on revert.
- **The `config/samples` plan is stale.** Don't model new plans on it; follow `schema/schema.json` and `tests/files/plan.json`.
