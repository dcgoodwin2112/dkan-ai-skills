# Testing & Standards

PHPUnit base classes, the test directory layout, config-schema enforcement in tests,
deprecation testing (which changed in D11.4), and the coding-standards/static-analysis
toolchain. Examples use `my_module`.

## Test base classes

| Base class | Scope | Bootstraps |
|---|---|---|
| `UnitTestCase` | pure unit — no Drupal | nothing; mock all collaborators |
| `KernelTestBase` | integration with real services | minimal kernel; modules **loaded, not installed** |
| `BrowserTestBase` | functional (no JS) | full site install, Mink/Goutte |
| `WebDriverTestBase` | functional + JS | full site + ChromeDriver |

Directory layout under `tests/src/`:

```
tests/src/Unit/             → UnitTestCase
tests/src/Kernel/           → KernelTestBase
tests/src/Functional/       → BrowserTestBase
tests/src/FunctionalJavascript/ → WebDriverTestBase
```

Group tests with the `#[Group('my_module')]` attribute (or the `@group my_module`
annotation on older cores) so they run in a named suite.

## Kernel tests: loaded vs installed

`KernelTestBase::$modules` **loads** code but does not install schema or config. Install
explicitly what the test touches:

```php
class WidgetTest extends KernelTestBase {

  protected static $modules = ['my_module', 'user', 'field'];

  protected function setUp(): void {
    parent::setUp();
    $this->installEntitySchema('my_widget');   // content entity tables
    $this->installConfig(['my_module']);       // config/install/*.yml + schema
  }

}
```

- `installEntitySchema('…')` — creates a content entity's tables (see
  [config-and-entities.md](config-and-entities.md)).
- `installConfig(['my_module'])` — imports `config/install` and validates against schema.
- `installSchema('module', ['table'])` — only for legacy `hook_schema` tables.

## Config schema enforcement

`KernelTestBase::$strictConfigSchema` defaults to **TRUE**: any config saved during the
test is validated against its schema, and a missing/mismatched mapping fails the test.
This is the mechanism that makes config schema effectively mandatory — do **not** set it
to `FALSE` to "fix" a failure; add the schema instead (see
[config-and-entities.md](config-and-entities.md#config-schema--validation)).

## Deprecation testing (changed in D11.4)

How you assert a deprecation notice fires depends on core version:

| Core | Mechanism |
|---|---|
| D10 / pre-11.4 | `@group legacy` + `$this->expectDeprecation('…')` |
| **D11.4+** | `#[IgnoreDeprecations]` + `$this->expectUserDeprecationMessage('…')` |

```php
// D11.4+
#[IgnoreDeprecations]
public function testOldApi(): void {
  $this->expectUserDeprecationMessage('my_module_old() is deprecated in …');
  my_module_old();
}
```

```php
// D10 / pre-11.4
/** @group legacy */
public function testOldApi(): void {
  $this->expectDeprecation('my_module_old() is deprecated in …');
  my_module_old();
}
```

> **Version-dependent.** `expectDeprecation()`/`@group legacy` are deprecated in D11.4 in
> favor of the attribute form. Use whichever matches the core you target; verify before
> relying on either.

## Coding standards

`drupal/coder` provides the `Drupal` and `DrupalPractice` phpcs standards:

```bash
vendor/bin/phpcs --standard=Drupal,DrupalPractice path/to/my_module
vendor/bin/phpcbf --standard=Drupal,DrupalPractice path/to/my_module   # auto-fix
```

## Static analysis

`mglaman/phpstan-drupal` teaches PHPStan about Drupal's container, plugins, and entity
APIs; pair it with the deprecation rules to catch removed-API usage before upgrade.

```neon
# phpstan.neon
includes:
  - vendor/mglaman/phpstan-drupal/extension.neon
  - vendor/phpstan/phpstan-deprecation-rules/rules.neon
parameters:
  level: 5
  drupal:
    drupal_root: web
```

`drupal-check` wraps the same rules for a quick "is this ready for the next major" pass.
