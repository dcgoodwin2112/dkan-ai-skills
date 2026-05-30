---
description: Scaffold a complete custom DKAN 4.x module skeleton
argument-hint: <module_name> [--with-tests] [--service <ServiceName>]
---

Scaffold a complete custom DKAN 4.x module skeleton: info.yml, services.yml, composer.json, `src/`, and (optionally) a standalone PHPUnit test harness with DKAN-namespaced stubs.

Read [SKILL.md](../skills/dkan-module-author/SKILL.md), [reference/dkan-services.md](../skills/dkan-module-author/reference/dkan-services.md), and [reference/dkan-testing.md](../skills/dkan-module-author/reference/dkan-testing.md) before proceeding. The scaffold below is modeled on the real `dkan_query_tools` module — match it exactly.

## Input

`$ARGUMENTS` should be: `<module_name> [--with-tests] [--service <ServiceName>]`

- `module_name`: machine name in `snake_case` (e.g., `my_dkan_tools`). Used verbatim as the namespace segment `Drupal\<module_name>\`.
- `--with-tests`: generate the standalone test harness (`phpunit.xml`, `tests/bootstrap.php`, `tests/stubs/`, `tests/src/Unit/`).
- `--service <ServiceName>`: also scaffold one DI service (PascalCase, e.g., `CatalogReader`) wired in `services.yml`.

Target path defaults to `<webroot>/modules/custom/<module_name>`.

## DKAN 4.x gotchas (do not skip)

- **Module dependencies use the `dkan_` prefix under the `dkan:` project**: `dkan:dkan_metastore`, `dkan:dkan_datastore`, `dkan:dkan_common`. NOT `dkan:metastore`. This is the single most common scaffold mistake.
- **Service-class namespaces also carry the `dkan_` prefix**: `Drupal\dkan_metastore\MetastoreService`, `Drupal\dkan_common\DatasetInfo`.
- **`MetastoreService::get()` / `getAll()` return `RootedData\RootedJsonData`**, not arrays — cast to string and `json_decode`, or use accessors. Plan tool/service signatures around this.
- **Standalone test stubs must declare the real 4.x namespaces** (`Drupal\dkan_metastore`, `RootedData`) so `createMock()` resolves the same class names production code type-hints.

## Steps

### 1. Create the directory layout

```
<webroot>/modules/custom/<module_name>/
  <module_name>.info.yml
  <module_name>.services.yml
  composer.json
  .gitignore
  src/
```

With `--with-tests`, also create `tests/bootstrap.php`, `tests/stubs/`, `tests/src/Unit/`, and `phpunit.xml`. With `--service`, also create `src/Service/<ServiceName>.php`.

### 2. `<module_name>.info.yml`

```yaml
name: TODO Human-readable module name
description: TODO One-line description of what this module provides.
type: module
core_version_requirement: ^10.2 || ^11
package: DKAN
dependencies:
  - dkan:dkan_metastore
  - dkan:dkan_datastore
  # Add only the DKAN subsystems you actually use. All take the dkan: project,
  # dkan_-prefixed module form:
  #   - dkan:dkan_common
  #   - dkan:dkan_datastore
  #   - dkan:dkan_metastore
```

### 3. `<module_name>.services.yml`

```yaml
services:
  # Logger channel scoped to this module.
  <module_name>.logger_channel:
    parent: logger.channel_base
    arguments: ['<module_name>']

  # Example service wiring DKAN dependencies. Note the dkan.* service IDs
  # (service IDs are NOT dkan_-prefixed; only module names and namespaces are).
  # <module_name>.example:
  #   class: Drupal\<module_name>\Service\Example
  #   arguments:
  #     - '@dkan.metastore.service'
  #     - '@dkan.datastore.service'
  #     - '@dkan.common.dataset_info'
  #     - '@<module_name>.logger_channel'
```

### 4. `composer.json`

Match the `dkan_query_tools` shape exactly — `type: drupal-custom-module`, empty `require`, dev-only test deps, PSR-4 autoload for both `src/` and `tests/src/`:

```json
{
  "name": "TODO-vendor/<module_name>",
  "description": "TODO One-line description.",
  "type": "drupal-custom-module",
  "license": "GPL-2.0-or-later",
  "require": {},
  "require-dev": {
    "drupal/core": "^10.2 || ^11",
    "phpunit/phpunit": "^9 || ^10",
    "getdkan/mock-chain": "^1"
  },
  "autoload": {
    "psr-4": {
      "Drupal\\<module_name>\\": "src/"
    }
  },
  "autoload-dev": {
    "psr-4": {
      "Drupal\\Tests\\<module_name>\\": "tests/src/"
    }
  },
  "config": {
    "allow-plugins": {
      "drupal/core-composer-scaffold": false
    }
  }
}
```

### 5. `.gitignore`

```
vendor/
composer.lock
.DS_Store
.phpunit.result.cache
```

### 6. `--service <ServiceName>` (optional)

Generate `src/Service/<ServiceName>.php` with constructor-promoted DI, then uncomment/adapt the example service block in `services.yml` (service ID `<module_name>.<snake_case_service_name>`). For DKAN dependency type hints and service IDs, defer to [reference/dkan-services.md](../skills/dkan-module-author/reference/dkan-services.md) or `/scaffold-drupal-service`.

```php
<?php

declare(strict_types=1);

namespace Drupal\<module_name>\Service;

use Drupal\dkan_metastore\MetastoreService;

/**
 * TODO: describe <ServiceName>.
 */
class <ServiceName> {

  public function __construct(
    protected MetastoreService $metastore,
  ) {}

  // Remember: MetastoreService::get()/getAll() return RootedData\RootedJsonData.

}
```

### 7. `--with-tests` (optional): standalone harness

This runs unit tests with plain `vendor/bin/phpunit` (no Drupal kernel), so DKAN classes are supplied by local stubs that carry the **real 4.x namespaces**.

`phpunit.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<phpunit xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:noNamespaceSchemaLocation="https://schema.phpunit.de/9.6/phpunit.xsd"
  bootstrap="tests/bootstrap.php"
  colors="true"
  failOnRisky="true"
  failOnWarning="true"
  beStrictAboutTestsThatDoNotTestAnything="true">
  <testsuites>
    <testsuite name="unit">
      <directory>tests/src/Unit</directory>
    </testsuite>
  </testsuites>
</phpunit>
```

`tests/bootstrap.php` — loads Composer autoload, then every stub:

```php
<?php

/**
 * @file
 * Bootstrap for PHPUnit tests.
 */

$autoloader = __DIR__ . '/../vendor/autoload.php';
if (file_exists($autoloader)) {
  require $autoloader;
}

$stubDir = __DIR__ . '/stubs';
foreach (glob($stubDir . '/*.php') as $stub) {
  require_once $stub;
}
```

`tests/stubs/RootedJsonData.php` — the return type of metastore reads:

```php
<?php

namespace RootedData;

/**
 * Stub for RootedData\RootedJsonData.
 */
class RootedJsonData {

  protected string $json;

  public function __construct(string $json = '{}', $schema = '{}') {
    $this->json = $json;
  }

  public function __toString(): string {
    return $this->json;
  }

  public function set(string $path, $value): void {
    if ($path === '$') {
      $this->json = json_encode($value);
    }
  }

}
```

`tests/stubs/MetastoreService.php` — note the **`Drupal\dkan_metastore`** namespace and `RootedJsonData` returns:

```php
<?php

namespace Drupal\dkan_metastore;

use RootedData\RootedJsonData;

/**
 * Stub for Drupal\dkan_metastore\MetastoreService.
 */
class MetastoreService {

  public function getAll(string $schema_id, ?int $start = NULL, ?int $length = NULL, $unpublished = FALSE): array {
    return [];
  }

  public function get(string $schema_id, string $identifier, bool $published = TRUE): RootedJsonData {
    return new RootedJsonData('{}');
  }

  public function count(string $schema_id, bool $unpublished = FALSE): int {
    return 0;
  }

}
```

Add one stub per DKAN class your code type-hints (e.g. `Drupal\dkan_common\DatasetInfo`, `Drupal\dkan_datastore\DatastoreService`), each in its real 4.x namespace. See the full set in `<webroot>/modules/custom/dkan_query_tools/tests/stubs/`.

`tests/src/Unit/ExampleTest.php` — sample unit test (namespace `Drupal\Tests\<module_name>\Unit`):

```php
<?php

namespace Drupal\Tests\<module_name>\Unit;

use Drupal\dkan_metastore\MetastoreService;
use PHPUnit\Framework\TestCase;
use RootedData\RootedJsonData;

class ExampleTest extends TestCase {

  public function testMetastoreReturnsRootedJsonData(): void {
    $metastore = $this->createMock(MetastoreService::class);
    $metastore->method('get')->willReturn(
      new RootedJsonData(json_encode(['identifier' => 'abc-123']))
    );

    $data = json_decode((string) $metastore->get('dataset', 'abc-123'), TRUE);
    $this->assertSame('abc-123', $data['identifier']);
  }

}
```

## Post-scaffold steps

1. Fill in the `TODO` fields in `info.yml` and `composer.json` (name, description, vendor).
2. Enable the module: `ddev drush en <module_name>`.
3. With `--with-tests`: install dev deps and run tests:
   ```bash
   cd <webroot>/modules/custom/<module_name> && composer install && vendor/bin/phpunit
   ```
4. Validate the module: `/validate-module <module_name>`.

## Pitfall checks before reporting done

- [ ] `info.yml` deps use the `dkan:dkan_*` form (e.g. `dkan:dkan_metastore`), not `dkan:metastore`.
- [ ] `composer.json` is `type: drupal-custom-module` with empty `require` and dev-only test deps.
- [ ] Service-class type hints use `dkan_`-prefixed namespaces; service IDs in YAML use the un-prefixed `dkan.*` form.
- [ ] Test stubs declare real 4.x namespaces (`Drupal\dkan_metastore`, `RootedData`).
- [ ] Code consuming metastore reads handles `RootedJsonData`, not arrays.
