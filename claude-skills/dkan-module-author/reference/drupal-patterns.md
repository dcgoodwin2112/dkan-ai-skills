# Drupal Core Conventions

Quick reference for Drupal 10.6 / PHP 8.3 patterns. For DKAN-specific patterns (metastore, datastore, references, resource IDs), see `dkan-*.md`.

## 1. Dependency Injection

| Class type | Interface | `create()` signature |
|---|---|---|
| Controller | `ControllerBase` (extends) | `create(ContainerInterface $container): static` |
| Block/Plugin | `ContainerFactoryPluginInterface` | `create(ContainerInterface $container, array $configuration, $plugin_id, $plugin_definition)` |
| Form | `FormBase` (extends, has DI built in) | `create(ContainerInterface $container): static` |
| Service | None — constructor injection via `services.yml` | N/A |
| Event subscriber | None — constructor injection via `services.yml` | N/A |

### Controller (ControllerBase)

```php
class DataPreviewController extends ControllerBase {

  public function __construct(
    protected ResourceIdResolver $resourceResolver,
    protected MetastoreService $metastore,
  ) {}

  public static function create(ContainerInterface $container): static {
    return new static(
      $container->get('dkan.data_preview.resource_resolver'),
      $container->get('dkan.metastore.service'),
    );
  }

}
```

### Block plugin (ContainerFactoryPluginInterface)

Four-param `create()` — the first three (`$configuration`, `$plugin_id`, `$plugin_definition`) are passed through to `__construct()`:

```php
class DataPreviewBlock extends BlockBase implements ContainerFactoryPluginInterface {

  public function __construct(
    array $configuration,
    $plugin_id,
    $plugin_definition,
    protected DataPreviewBuilder $previewBuilder,
    protected LoggerInterface $logger,
  ) {
    parent::__construct($configuration, $plugin_id, $plugin_definition);
  }

  public static function create(ContainerInterface $container, array $configuration, $plugin_id, $plugin_definition) {
    return new static(
      $configuration,
      $plugin_id,
      $plugin_definition,
      $container->get('dkan.data_preview.builder'),
      $container->get('logger.factory')->get('datastore_data_preview'),
    );
  }

}
```

> **Warning**: `\Drupal::service()` is only correct in **static** and **procedural** contexts (`.module` files, static `#pre_render` callbacks). In any class with DI available, inject via constructor.

## 2. Service Definitions

Services are defined in `{module_name}.services.yml`. Class names use a leading backslash in YAML, not in PHP `use` statements.

```yaml
services:
  dkan.data_preview.builder:
    class: \Drupal\datastore_data_preview\Service\DataPreviewBuilder
    arguments:
      - '@request_stack'
      - '@pager.manager'

  dkan.data_preview.datasource.database:
    class: \Drupal\datastore_data_preview\DataSource\DatabaseDataSource
    arguments:
      - '@dkan.datastore.service'
```

### Naming conventions

| Pattern | Example |
|---|---|
| Module services | `{module_name}.{service_name}` |
| Drupal core services | `entity_type.manager`, `request_stack`, `pager.manager` |
| Logger channels | `logger.factory` → `->get('channel_name')` |
| Injected references | `'@service_id'` in YAML `arguments` |

### Event subscriber tag

```yaml
  my_module.event_subscriber:
    class: \Drupal\my_module\EventSubscriber\MySubscriber
    arguments:
      - '@some.service'
    tags:
      - { name: event_subscriber }
```

> **Warning**: Leading backslash on class names in YAML (`\Drupal\...`), no backslash in PHP `use` statements (`use Drupal\...`).

## 3. Render Arrays

### Core `#type` values

| `#type` | Purpose |
|---|---|
| `table` | Sortable table with `#header`, `#rows`, `#empty`, `#sticky` |
| `pager` | Pagination with `#element`, `#parameters` |
| `container` | Wrapper `<div>` with `#attributes` |
| `html_tag` | Arbitrary HTML element via `#tag`, `#value` |
| `select` | Dropdown with `#options`, `#value` |
| `textfield` | Text input |
| `markup` | Raw HTML via `#markup` |
| `link` | Anchor with `#title`, `#url` |
| `details` | Collapsible fieldset with `#open` |

### `#theme` vs `#type`

- `#type` → render element class (PHP, extends `RenderElementBase`)
- `#theme` → template file (Twig, registered in `hook_theme()`)

Both can appear in the same render array — `#type` for the element structure, `#theme` for custom template output:

```php
return [
  '#theme' => 'datastore_data_preview',
  '#table' => ['#type' => 'table', '#header' => $header, '#rows' => $rows],
  '#pager' => ['#type' => 'pager', '#element' => 0],
  '#attached' => ['library' => ['datastore_data_preview/data_preview']],
  '#cache' => [
    'contexts' => ['url.query_args:page', 'url.query_args:sort'],
  ],
];
```

### `#cache`

| Key | Purpose | Example |
|---|---|---|
| `contexts` | Vary by request context | `['url.query_args:page', 'user.roles']` |
| `tags` | Invalidate when data changes | `['node:42', 'node_list']` |
| `max-age` | TTL in seconds | `3600`, `0` (uncacheable), `-1` (permanent) |

### `#pre_render`

Static callbacks — `\Drupal::service()` is correct here (no DI available):

```php
'#pre_render' => [
  [static::class, 'preRender'],
],
```

## 4. Render Elements

PHP attribute (D10.3+) replaces `@RenderElement` annotation:

```php
#[RenderElement('data_preview')]
class DataPreview extends RenderElementBase {

  public function getInfo() {
    return [
      '#resource_id' => '',
      '#columns' => [],
      '#pre_render' => [
        [static::class, 'preRender'],
      ],
    ];
  }

  public static function preRender(array $element): array {
    $builder = \Drupal::service('dkan.data_preview.builder');
    // ... build and return $element
    return $element;
  }

}
```

Usage: `['#type' => 'data_preview', '#resource_id' => $id]`

## 5. Routing

```yaml
datastore_data_preview.preview:
  path: '/admin/dkan/data-preview/{resource_id}'
  defaults:
    _controller: '\Drupal\datastore_data_preview\Controller\DataPreviewController::preview'
    _title_callback: '\Drupal\datastore_data_preview\Controller\DataPreviewController::title'
  requirements:
    _permission: 'administer dkan'
  options:
    _admin_route: TRUE
```

### Access keys

| Key | Value | Use |
|---|---|---|
| `_permission` | Permission string | User must have this permission |
| `_access` | `'TRUE'` | Unrestricted access |
| `_custom_access` | `'\Drupal\...\Controller::checkAccess'` | Method returns `AccessResult` |

### `AccessResult` methods

```php
AccessResult::allowed()    // Grant access
AccessResult::forbidden()  // Deny access
AccessResult::neutral()    // No opinion (defer to other checks)
  ->addCacheableDependency($entity)
  ->addCacheTags(['node:42'])
  ->addCacheContexts(['user.roles'])
```

> **Warning**: Title callbacks must return `string` or `TranslatableMarkup`, never a render array.

## 6. Plugin Annotations

### `@Block`

```php
/**
 * @Block(
 *   id = "datastore_data_preview",
 *   admin_label = @Translation("Data Preview Table"),
 *   category = @Translation("DKAN"),
 * )
 */
class DataPreviewBlock extends BlockBase implements ContainerFactoryPluginInterface {
```

### `@QueueWorker`

```php
/**
 * @QueueWorker(
 *   id = "my_queue",
 *   title = @Translation("My queue worker"),
 *   cron = {"time" = 60}
 * )
 */
```

### D10.2+ PHP attribute alternative

| Annotation key | Attribute parameter |
|---|---|
| `id` | First positional arg |
| `admin_label` | `admin_label: new TranslatableMarkup(...)` |
| `category` | `category: new TranslatableMarkup(...)` |

`@Translation()` in annotations → `new TranslatableMarkup()` in attributes.

## 7. Entity Queries

```php
$storage = $this->entityTypeManager->getStorage('node');
$ids = $storage->getQuery()
  ->accessCheck(TRUE)
  ->condition('type', 'data')
  ->condition('status', 1)
  ->sort('created', 'DESC')
  ->range(0, 10)
  ->execute();
$nodes = $storage->loadMultiple($ids);
```

> **Warning**: `accessCheck()` is **required** since D10.2 (deprecation notice in D10, fatal error in D11). Always call `->accessCheck(TRUE)` or `->accessCheck(FALSE)` explicitly. Inject `EntityTypeManagerInterface`, never use `\Drupal::entityTypeManager()` in classes.

## 8. Form API

### Base class comparison

| Method | `FormBase` | `ConfigFormBase` |
|---|---|---|
| `getFormId()` | Required | Required |
| `buildForm()` | Required | Required |
| `submitForm()` | Required | Required |
| `getEditableConfigNames()` | N/A | **Required** |
| `validateForm()` | Optional | Optional |

### `#states` — conditional visibility

```php
'#states' => [
  'visible' => [
    ':input[name="settings[data_source]"]' => ['value' => 'api'],
  ],
],
```

### Form element `#type` quick reference

| `#type` | Key properties |
|---|---|
| `textfield` | `#title`, `#default_value`, `#required`, `#description` |
| `select` | `#options` (assoc array), `#default_value` |
| `checkbox` | `#title`, `#default_value` (bool) |
| `number` | `#min`, `#max`, `#step` |
| `url` | Like textfield, validates URL format |
| `submit` | `#value` (button text) |

> **Warning**: `ConfigFormBase` requires `getEditableConfigNames()` returning an array of config object names. Omitting it silently fails to save config.

## 9. Configuration API

### Read/write with injected `ConfigFactoryInterface`

```php
// Read.
$value = $this->configFactory->get('my_module.settings')->get('key');

// Write.
$this->configFactory->getEditable('my_module.settings')
  ->set('key', $value)
  ->save();
```

Schema file: `config/schema/{module_name}.schema.yml`

> **Warning**: Never use `\Drupal::config()` in classes with DI. Inject `ConfigFactoryInterface`.

## 10. Event Subscribers

```php
class MySubscriber implements EventSubscriberInterface {

  public function __construct(
    protected SomeService $service,
  ) {}

  public static function getSubscribedEvents(): array {
    return [
      SomeEvent::EVENT_NAME => ['onEvent', 100],
    ];
  }

  public function onEvent(SomeEvent $event): void {
    // Handle event.
  }

}
```

Register in `services.yml` with `event_subscriber` tag (see section 2). Prefer events over hooks for new code.

## 11. Theming

### `hook_theme()`

```php
function datastore_data_preview_theme() {
  return [
    'datastore_data_preview' => [
      'variables' => [
        'table' => NULL,
        'pager' => NULL,
        'page_size_form' => NULL,
        'result_summary' => NULL,
      ],
      'template' => 'datastore-data-preview',
    ],
  ];
}
```

### Libraries (`{module}.libraries.yml`)

```yaml
data_preview:
  css:
    component:
      css/data-preview.css: {}
  js:
    js/data-preview.js: {}
  dependencies:
    - core/drupal
    - core/once
```

Attach in render arrays: `'#attached' => ['library' => ['module_name/library_name']]`

> **Warning**: Template filename uses **hyphens** (`datastore-data-preview.html.twig`), theme hook and `#theme` value use **underscores** (`datastore_data_preview`). These must match.

## 12. String Translation

Use `StringTranslationTrait` in services, `$this->t()` in controllers/forms/blocks (inherited from base classes).

```php
$this->t('Showing @start-@end of @total results', [
  '@start' => number_format($start),
  '@end' => number_format($end),
  '@total' => number_format($totalCount),
]);
```

Placeholder types: `@variable` (escaped), `%variable` (escaped + `<em>`), `:variable` (escaped + URL-safe).

> **Warning**: Never concatenate translated strings (`$this->t('Hello') . ' ' . $this->t('world')`). Use a single `t()` call with placeholders.

## 13. Logging

### Injection

```php
$container->get('logger.factory')->get('channel_name')
```

### Placeholder syntax

| Prefix | Behavior |
|---|---|
| `@` | Escaped string |
| `%` | Escaped + wrapped in `<em>` |
| `:` | Escaped + URL-safe |

```php
$this->logger->error('Block preview error for @id: @message', [
  '@id' => $config['resource_id'],
  '@message' => $e->getMessage(),
]);
```

PSR-3 levels: `emergency`, `alert`, `critical`, `error`, `warning`, `notice`, `info`, `debug`.

## 14. Module Info

```yaml
name: Datastore Data Preview
description: Provides a reusable paginated, sortable HTML table for previewing datastore data.
type: module
core_version_requirement: ^10.2 || ^11
package: DKAN
dependencies:
  - dkan:common
  - dkan:datastore
  - dkan:metastore
```

Dependencies format: `{project}:{module}` (e.g., `dkan:datastore`). Use `drupal:{module}` for core modules.

## 15. Drush Commands

```php
class McpServeCommand extends DrushCommands {

  public function __construct(
    protected McpServerFactory $serverFactory,
  ) {
    parent::__construct();
  }

  /**
   * Start the MCP server.
   *
   * @command dkan-mcp:serve
   * @aliases dkan-mcp
   */
  public function serve(): void {
    // ...
  }

}
```

Register in `drush.services.yml` (separate file from `{module}.services.yml`):

```yaml
services:
  my_module.drush.command:
    class: \Drupal\my_module\Drush\MyCommand
    arguments:
      - '@some.service'
    tags:
      - { name: drush.command }
```
