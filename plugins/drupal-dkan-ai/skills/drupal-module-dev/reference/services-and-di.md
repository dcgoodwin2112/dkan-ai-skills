# Services & Dependency Injection

Drupal-specific DI conventions, autowiring, and Drush commands. Examples use a
placeholder `my_module`. The `create()` signatures per class type are in
[SKILL.md#cheat-sheets](../SKILL.md#cheat-sheets).

## Dependency injection

- Controllers and forms: `create(ContainerInterface $container): static` + constructor
  property promotion (the current idiom — no separate property declarations).
- Factory plugins (blocks, etc.): the four-param
  `create($container, array $configuration, $plugin_id, $plugin_definition)` — the
  first three pass through `__construct()` and on to `parent::__construct()`.

> **`\Drupal::service()` rule.** Static container access is correct **only** in
> procedural code (`.module`/`.install`) and static callbacks (`#pre_render`,
> `#lazy_builder`) where no instance container is available. In any class that has a
> `create()` factory or a `services.yml` definition, inject via the constructor.

## Service definitions

Services live in `{module}.services.yml`; module service IDs follow `{module}.{name}`.
Class names take a **leading backslash in YAML**, none in PHP `use` statements.

```yaml
services:
  my_module.builder:
    class: \Drupal\my_module\WidgetBuilder
    arguments:
      - '@request_stack'
      - '@entity_type.manager'
```

### Event subscriber tag

Tag the service `{ name: event_subscriber }` (applied automatically under
`autoconfigure: true`). `/add-event-subscriber` scaffolds one.

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

## Logging & translation

Inject `logger.factory` and get a channel (`->get('my_module')` returns a PSR-3
`LoggerChannelInterface`). For `t()` in plain services add `StringTranslationTrait`;
controllers/forms/plugins inherit `$this->t()` from their base classes.

Placeholder prefixes (same for logging and `t()`): `@` escaped · `%` escaped + `<em>` ·
`:` escaped URL.

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
    tags:
      - { name: drush.command }
```

The older `@command`/`@aliases` docblock annotation style still works on Drush
generators but new commands should use the attribute form.
