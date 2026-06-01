# Services & Dependency Injection

Dependency injection, service definitions, autowiring, logging, string translation, and
Drush commands. Examples use a placeholder `my_module`.

## Dependency injection

| Class type | Interface / base | `create()` signature |
|---|---|---|
| Controller | `ControllerBase` (extends) | `create(ContainerInterface $container): static` |
| Form | `FormBase` / `ConfigFormBase` (DI built in) | `create(ContainerInterface $container): static` |
| Block / factory plugin | `…Base` + `ContainerFactoryPluginInterface` | `create($container, array $configuration, $plugin_id, $plugin_definition)` |
| Service | none — constructor injection via `services.yml` | N/A |
| Event subscriber | none — constructor injection via `services.yml` | N/A |

### Controller

```php
class WidgetController extends ControllerBase {

  public function __construct(
    protected WidgetBuilder $builder,
    protected EntityTypeManagerInterface $entityTypeManager,
  ) {}

  public static function create(ContainerInterface $container): static {
    return new static(
      $container->get('my_module.builder'),
      $container->get('entity_type.manager'),
    );
  }

}
```

### Factory plugin (block, etc.)

Four-param `create()` — the first three (`$configuration`, `$plugin_id`,
`$plugin_definition`) pass through to `__construct()` and on to `parent::__construct()`:

```php
class WidgetBlock extends BlockBase implements ContainerFactoryPluginInterface {

  public function __construct(
    array $configuration,
    $plugin_id,
    $plugin_definition,
    protected WidgetBuilder $builder,
    protected LoggerInterface $logger,
  ) {
    parent::__construct($configuration, $plugin_id, $plugin_definition);
  }

  public static function create(ContainerInterface $container, array $configuration, $plugin_id, $plugin_definition) {
    return new static(
      $configuration,
      $plugin_id,
      $plugin_definition,
      $container->get('my_module.builder'),
      $container->get('logger.factory')->get('my_module'),
    );
  }

}
```

> **`\Drupal::service()` rule.** Static container access is correct **only** in
> procedural code (`.module`/`.install`) and static callbacks (`#pre_render`,
> `#lazy_builder`) where no instance container is available. In any class that has a
> `create()` factory or a `services.yml` definition, inject via the constructor.

## Service definitions

Services live in `{module}.services.yml`. Class names take a **leading backslash in
YAML**, none in PHP `use` statements.

```yaml
services:
  my_module.builder:
    class: \Drupal\my_module\WidgetBuilder
    arguments:
      - '@request_stack'
      - '@entity_type.manager'
```

### Naming & references

| Pattern | Example |
|---|---|
| Module service IDs | `{module}.{name}` (`my_module.builder`) |
| Core service IDs | `entity_type.manager`, `request_stack`, `config.factory` |
| Logger channel | `logger.factory` → `->get('my_module')` |
| Injected reference | `'@service_id'` in YAML `arguments` |

### Event subscriber tag

```yaml
  my_module.subscriber:
    class: \Drupal\my_module\EventSubscriber\MySubscriber
    arguments: ['@entity_type.manager']
    tags:
      - { name: event_subscriber }
```

## Autowiring (D10 / D11)

Autowiring resolves constructor arguments by **type-hint** so you don't list each
`arguments` entry. Opt in per file with `_defaults`:

```yaml
services:
  _defaults:
    autowire: true
    autoconfigure: true   # auto-applies tags by implemented interface (e.g. EventSubscriberInterface)
  my_module.builder:
    class: \Drupal\my_module\WidgetBuilder
```

- A constructor parameter typed to a service **interface** is wired automatically.
- When an interface is ambiguous (multiple services implement it) or you need a specific
  named service, disambiguate at the parameter with the **`#[Autowire]`** attribute:

  ```php
  use Drupal\Core\DependencyInjection\Attribute\Autowire;

  public function __construct(
    #[Autowire(service: 'cache.default')]
    protected CacheBackendInterface $cache,
  ) {}
  ```

- **Explicit `arguments:` are still needed** for scalar/parameter args, factory-created
  services, or where no unambiguous type-hint exists. Autowiring is opt-in; plenty of
  core services are not autowireable, so a hybrid `services.yml` is normal.

Constructor **property promotion** (`protected Foo $foo` in the signature) is the current
idiom for all of the above — no separate property declarations or assignments.

## Logging

Inject `logger.factory` and get a channel; the channel is a PSR-3 logger.

```php
$container->get('logger.factory')->get('my_module')   // LoggerChannelInterface
```

```php
$this->logger->error('Build failed for @id: @message', [
  '@id' => $id,
  '@message' => $e->getMessage(),
]);
```

Placeholder prefixes: `@` escaped · `%` escaped + `<em>` · `:` escaped URL.
PSR-3 levels: `emergency`, `alert`, `critical`, `error`, `warning`, `notice`, `info`,
`debug`.

## String translation

Use `$this->t()` in controllers/forms/plugins (inherited from base classes); in plain
services add `StringTranslationTrait`.

```php
$this->t('Showing @start–@end of @total', [
  '@start' => $start, '@end' => $end, '@total' => $total,
]);
```

Placeholder types match the logging prefixes (`@`/`%`/`:`).

> **Never concatenate translated strings** (`$this->t('Hello') . $this->t('world')`) —
> word order is not translatable that way. One `t()` call with placeholders.

## Drush commands

Drush 12+ uses **PHP attributes** on a command class; register the class with the
`drush.command` tag in `{module}.services.yml` (or a dedicated `drush.services.yml` —
both are read).

```php
use Drush\Attributes as CLI;
use Drush\Commands\DrushCommands;

class MyCommands extends DrushCommands {

  public function __construct(
    protected WidgetBuilder $builder,
  ) {
    parent::__construct();
  }

  #[CLI\Command(name: 'my_module:rebuild', aliases: ['mmr'])]
  #[CLI\Argument(name: 'id', description: 'Widget id.')]
  public function rebuild(string $id): void {
    // ...
  }

}
```

```yaml
services:
  my_module.commands:
    class: \Drupal\my_module\Drush\Commands\MyCommands
    arguments: ['@my_module.builder']
    tags:
      - { name: drush.command }
```

The older `@command`/`@aliases` docblock annotation style still works on Drush
generators but new commands should use the attribute form.
