# DKAN Testing Reference

## Test Types

| Type | Base Class | Drupal Bootstrap | Use Case |
|---|---|---|---|
| Unit | `PHPUnit\Framework\TestCase` | No | Pure logic, isolated services, mock all deps |
| Kernel | `Drupal\KernelTests\KernelTestBase` | Yes (container + DB) | Service integration, entity operations |
| Functional | `Drupal\Tests\BrowserTestBase` | Yes (full HTTP) | API endpoints, UI, full stack |

## Directory & Namespace Conventions

```
modules/{module}/tests/src/Unit/        → Drupal\Tests\{module}\Unit\
modules/{module}/tests/src/Kernel/      → Drupal\Tests\{module}\Kernel\
modules/{module}/tests/src/Functional/  → Drupal\Tests\{module}\Functional\
```

- Class naming: `{ClassName}Test.php`, base classes `*TestBase.php`

## PHPUnit Configuration

**Standalone** (`datastore_data_preview/phpunit.xml`) — custom bootstrap, unit tests only:
```bash
cd datastore_data_preview && phpunit
cd datastore_data_preview && phpunit tests/src/Unit/SomeTest.php
```

**Drupal-integrated** (`web/modules/contrib/dkan/phpunit.xml`) — Drupal core bootstrap, all test types:
```bash
ddev exec phpunit web/modules/contrib/dkan/modules/datastore/tests/
```

## Standalone Module Testing Pattern

`datastore_data_preview` runs unit tests without a Drupal bootstrap for fast execution.

**Bootstrap** (`tests/bootstrap.php`): Loads Composer autoloader, then dynamically requires all stubs from `tests/stubs/`.

**Stubs** (`tests/stubs/`): Minimal class/interface declarations for DKAN dependencies not in the module's Composer scope:

| Stub | Key Members |
|---|---|
| `Query.php` | Properties: `$conditions`, `$count`, `$limit`, `$offset`, `$sorts`, `$properties`. Methods: `limitTo()`, `offsetBy()`, `sortByAscending()`, `filterByProperty()` |
| `DatabaseTableInterface.php` | `query(Query)`, `getSchema(): array` |
| `DatastoreService.php` | `getStorage(string, ?string)` |
| `MetastoreService.php` | `get(string, string): string` |
| `NodeInterface.php` | `get(string)` |

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
  ->add('dkan.data_preview.builder', $builder)
  ->add('dkan.data_preview.datasource.database', $dbSource)
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

`Drupal\Tests\common\Functional\Api1TestBase` extends `BrowserTestBase`.

Key properties:
- `$httpClient` — Guzzle HTTP client
- `$spec` — Decoded OpenAPI spec from `/api/1`
- `$auth` / `$authNoPerms` — Credential pairs `[username, password]`
- `$validator` — OpenAPI response validator
- `static $modules` — Enables `common`, `datastore`, `metastore`, `node`, `sample_content`, `workflows`

`setUp()` creates test users, initializes HTTP client, loads API spec, and configures OpenAPI validator.

### ConfigFormTestBase (Kernel)

`Drupal\Tests\common\Kernel\ConfigFormTestBase` extends `KernelTestBase`.

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
  protected static $modules = ['common', 'harvest', 'metastore'];

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
