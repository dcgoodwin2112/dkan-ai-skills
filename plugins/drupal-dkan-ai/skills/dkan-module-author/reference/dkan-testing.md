# DKAN Testing Reference

DKAN-specific testing patterns. For the general unit/kernel/functional base classes,
`tests/src/` directory layout, and deprecation-testing conventions, see
[drupal-module-dev/testing-and-standards.md](../../drupal-module-dev/reference/testing-and-standards.md).
This doc covers what DKAN adds: the standalone (no-bootstrap) harness, the mock-chain
library, and DKAN's own test base classes.

## PHPUnit Configuration

**Standalone** (e.g. `dkan_query_tools/phpunit.xml` — a site-specific custom module used as the worked example throughout this doc; it may not exist on your site, but the pattern stands alone) — custom bootstrap, unit tests only, no Drupal container. Run via the module's own composer-installed PHPUnit:
```bash
ddev exec "cd /var/www/html/<webroot>/modules/custom/dkan_query_tools && composer install"
ddev exec "cd /var/www/html/<webroot>/modules/custom/dkan_query_tools && ./vendor/bin/phpunit -c phpunit.xml"
```

**Drupal-integrated** (`<webroot>/modules/contrib/dkan/phpunit.xml`) — Drupal core bootstrap, all test types:
```bash
ddev exec phpunit <webroot>/modules/contrib/dkan/modules/dkan_datastore/tests/
```

## Standalone Module Testing Pattern

A custom module can run its unit tests without a Drupal bootstrap for fast execution. `dkan_query_tools` is a working example: its `phpunit.xml` points at a custom `tests/bootstrap.php` and a `tests/src/Unit` suite.

**Bootstrap** (`tests/bootstrap.php`): Loads the module-local Composer autoloader (`vendor/autoload.php`), then dynamically `require_once`s every stub under `tests/stubs/`.

**Stubs** (`tests/stubs/`): Minimal class/interface declarations standing in for DKAN classes outside the module's Composer autoload scope. They MUST carry the real 4.x namespaces (`Drupal\dkan_metastore`, `Drupal\dkan_datastore`, `Drupal\dkan_common`) so the code-under-test's `use` statements resolve. Real examples from `dkan_query_tools`:

| Stub | Namespace | Key Members |
|---|---|---|
| `MetastoreService.php` | `Drupal\dkan_metastore` | `get(string, string, bool): RootedJsonData`, `getAll(string, ?int, ?int, bool): array`, `count(string, bool): int`, `post(string, RootedJsonData): string` |
| `DatastoreService.php` | `Drupal\dkan_datastore` | `getStorage(string, ?string): DatabaseTableInterface`, `summary(string)`, `import(...)`, `drop(...)` |
| `QueryService.php` (declares `class Query`) | `Drupal\dkan_datastore\Service` | `runQuery(DatastoreQuery)` |
| `DatastoreQuery.php` | `Drupal\dkan_datastore\Service` | `__construct(string $json, $rows_limit = NULL)`, `__toString()` |
| `DatabaseTableInterface.php` | `Drupal\dkan_common\Storage` | `getSchema(): array`, `getTableName(): string` |
| `DatasetInfo.php` | `Drupal\dkan_common` | `gather(string $uuid): array` |
| `RootedJsonData.php` | `RootedData` | castable to JSON string via `__toString()` |

Add new stubs when your tests reference DKAN classes outside the module's autoload scope.

## Mock-Chain Library

`getdkan/mock-chain` provides a fluent builder for complex mock object graphs.

### Chain — Basic Mock Building

```php
use MockChain\Chain;

$storage = (new Chain($this))
  ->add(DatabaseTableInterface::class, 'query', $rows)
  ->addd('getSchema', $schema)
  ->getMock();
```

- Constructor takes the test case (`$this`)
- `add(class, method, returnValue)` — sets up a method expectation
- `addd(method, returnValue)` — adds another method to the same class
- `getMock()` — returns the configured mock

### Options — Indexed Dispatch (Container Mocking)

```php
use MockChain\Options;

$services = (new Options())
  ->index(0)
  ->add('dkan.metastore.service', $metastore)
  ->add('dkan.datastore.service', $datastore)
  ->add('logger.factory', $loggerFactory);

$container = (new Chain($this))
  ->add(ContainerInterface::class, 'get', $services)
  ->getMock();

\Drupal::setContainer($container);
```

`index(0)` tells Options which argument to use as the lookup key. Maps input values to return values — ideal for `ContainerInterface::get()`.

### Sequence — Successive Return Values

```php
use MockChain\Sequence;

$storage = (new Chain($this))
  ->add(DatabaseTableInterface::class, 'query', (new Sequence())
    ->add($rows)                              // First call returns data rows
    ->add([(object) ['expression' => $count]]) // Second call returns count
  )
  ->getMock();
```

Returns different values on each successive call to the same method.

## Test Base Classes

### Api1TestBase (Functional)

`Drupal\Tests\dkan_common\Functional\Api1TestBase` extends `BrowserTestBase`.

Key properties:
- `$httpClient` — Guzzle HTTP client
- `$spec` — Decoded OpenAPI spec from `/api/1`
- `$auth` / `$authNoPerms` — Credential pairs `[username, password]`
- `$validator` — OpenAPI response validator
- `static $modules` — Enables `dkan_common`, `dkan_datastore`, `dkan_metastore`, `dkan_harvest`, `dkan_sample_content`, `node`, `workflows`

`setUp()` creates test users, initializes HTTP client, loads API spec, and configures OpenAPI validator.

### ConfigFormTestBase (Kernel)

`Drupal\Tests\dkan_common\Kernel\ConfigFormTestBase` extends `KernelTestBase`.

Data-driven config form testing via `provideFormData()` data provider:
```php
public static function provideFormData(): array {
  return [
    'form_key' => [
      '#value' => $testValue,
      '#config_name' => 'config.object',
      '#config_key' => 'config.key',
    ],
  ];
}
```

Submits form values via `\Drupal::formBuilder()->submitForm()` and asserts config values match.

## Service Container in Tests

**Unit**: No container. Inject mocks via constructor or `\Drupal::setContainer()` with a Chain/Options mock.

**Kernel**: Declare required modules and install schemas in `setUp()`:
```php
class MyServiceTest extends KernelTestBase {
  protected static $modules = ['dkan_common', 'dkan_harvest', 'dkan_metastore'];

  protected function setUp(): void {
    parent::setUp();
    $this->installEntitySchema('harvest_run');
  }

  public function testService() {
    $service = $this->container->get('dkan.harvest.storage.harvest_run_repository');
    // assertions...
  }
}
```

**Functional**: Full stack available via `BrowserTestBase`. Container, HTTP, and database all active.
