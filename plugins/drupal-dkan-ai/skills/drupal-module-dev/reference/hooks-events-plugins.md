# Hooks, Events & Plugins

The three extension mechanisms and which to reach for: **hooks** (now OOP-capable),
**events** (preferred when both exist), and **plugins** (attribute-discovered). Examples
use `my_module`.

## OOP hooks (`#[Hook]`, D11.1)

A hook is now a method on a class in `src/Hook/`, autowired via the container, and
marked with the `#[Hook]` attribute. This replaces the procedural `my_module_hook_x()`
function for most cases.

```php
namespace Drupal\my_module\Hook;

use Drupal\Core\Hook\Attribute\Hook;
use Drupal\Core\Entity\EntityTypeManagerInterface;

class WidgetHooks {

  public function __construct(
    protected EntityTypeManagerInterface $entityTypeManager,
  ) {}

  #[Hook('entity_presave')]
  public function entityPresave(EntityInterface $entity): void {
    // ...
  }

  #[Hook('theme')]
  public function theme(): array {
    return ['my_module_widget' => ['variables' => ['items' => []]]];
  }

}
```

- The class is **autowired** — type-hint dependencies in the constructor, no
  `services.yml` entry needed.
- **Preprocess functions** also support the OOP form (D11.1):
  `#[Hook('preprocess_node')]`.
- **Ordering:** pass `order:` on the attribute, or use `#[ReorderHook]` (D11.2) to move
  another module's hook relative to yours.

### `#[LegacyHook]` — D10 back-compat

OOP hook discovery is D11.1+. To support D10 from the same codebase, keep a thin
procedural function that delegates to the class, and mark the OOP method
`#[LegacyHook]` so that on D11 the procedural function is **not** also invoked (avoiding
double execution):

```php
// my_module.module
function my_module_entity_presave(EntityInterface $entity): void {
  \Drupal::service(WidgetHooks::class)->entityPresave($entity);
}
```

```php
#[Hook('entity_presave')]
#[LegacyHook]
public function entityPresave(EntityInterface $entity): void { /* ... */ }
```

On a D11-only module, skip the shim and the `#[LegacyHook]` marker — just the `#[Hook]`
method.

### What stays procedural

Install-phase and schema hooks are **not** OOP-discovered and remain functions in
`.install`/`.module`: `hook_install`, `hook_uninstall`, `hook_schema`,
`hook_update_N`, `hook_post_update_NAME`, and the requirements hooks. See
[module-lifecycle.md](module-lifecycle.md).

## Events (preferred over hooks)

When a subscribable event exists for what you need, prefer it — a subscriber is a normal
DI-injected, unit-testable service.

```php
class MySubscriber implements EventSubscriberInterface {

  public function __construct(
    protected WidgetBuilder $builder,
  ) {}

  public static function getSubscribedEvents(): array {
    return [
      KernelEvents::REQUEST => ['onRequest', 100],   // [method, priority]
    ];
  }

  public function onRequest(RequestEvent $event): void {
    // ...
  }

}
```

Register with the `event_subscriber` tag (see
[services-and-di.md](services-and-di.md#event-subscriber-tag)); with `autoconfigure: true`
the tag is applied automatically from the implemented interface. Higher priority runs
first.

## Plugins: attribute discovery

PHP attributes are the default discovery mechanism. The attribute class is the plugin
type (`#[Block]`, `#[QueueWorker]`, `#[FieldType]`, …); the first positional argument is
the plugin ID, and `@Translation()` labels become `new TranslatableMarkup()`.

```php
use Drupal\Core\Block\Attribute\Block;
use Drupal\Core\StringTranslation\TranslatableMarkup;

#[Block(
  id: 'my_module_widget',
  admin_label: new TranslatableMarkup('Widget'),
  category: new TranslatableMarkup('My module'),
)]
class WidgetBlock extends BlockBase implements ContainerFactoryPluginInterface {
  // create()/__construct() — see services-and-di.md
}
```

### Annotation → attribute mapping

| Annotation | Attribute |
|---|---|
| `id = "x"` | first positional arg `'x'` |
| `admin_label = @Translation("…")` | `admin_label: new TranslatableMarkup('…')` |
| `category = @Translation("…")` | `category: new TranslatableMarkup('…')` |
| `cron = {"time" = 60}` | `cron: ['time' => 60]` |

### Discovery timeline

| Milestone | State |
|---|---|
| D10.2 | Attributes introduced for the first plugin types |
| ~D11.2 | All core plugin types support attributes; omitting the attribute class is deprecated |
| D12 | Attribute class **required** |
| D13 | `@Annotation` discovery **removed** |

New code: attributes only. Maintaining a module that targets a span including pre-10.2,
keep annotations until the floor moves.

### Render elements

Render elements are plugins too — the `#[RenderElement]` attribute (D10.3+) replaces
`@RenderElement`:

```php
#[RenderElement('my_widget')]
class Widget extends RenderElementBase {
  public function getInfo(): array {
    return [
      '#columns' => [],
      '#pre_render' => [[static::class, 'preRender']],
    ];
  }
  public static function preRender(array $element): array {
    // Static callback — \Drupal::service() is correct here (no DI).
    return $element;
  }
}
```

Usage in a render array: `['#type' => 'my_widget', '#columns' => $cols]`. See
[routing-forms-rendering.md](routing-forms-rendering.md) for render arrays.
