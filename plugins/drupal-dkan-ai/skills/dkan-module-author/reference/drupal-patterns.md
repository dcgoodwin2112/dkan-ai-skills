# Drupal Core Conventions

Quick reference for Drupal 10.2+ / 11 / PHP 8.3 patterns. Examples use a placeholder `my_dkan_module`; for real, working DKAN 4.x modules to model, see `<webroot>/modules/custom/dkan_query_tools` and `dkan_drupal_ai_query`. For DKAN-specific patterns (metastore, datastore, references, resource IDs), see `dkan-*.md`.

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
      $container->get('my_dkan_module.resource_resolver'),
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
      $container->get('my_dkan_module.builder'),
      $container->get('logger.factory')->get('my_dkan_module'),
    );
  }

}
```

> **Warning**: `\Drupal::service()` is only correct in **static** and **procedural** contexts (`.module` files, static `#pre_render` callbacks). In any class with DI available, inject via constructor.

## 2. Service Definitions

Services are defined in `{module_name}.services.yml`. Class names use a leading backslash in YAML, not in PHP `use` statements.

```yaml
services:
  my_dkan_module.builder:
    class: \Drupal\my_dkan_module\Service\DataPreviewBuilder
    arguments:
      - '@request_stack'
      - '@pager.manager'

  my_dkan_module.datasource.database:
    class: \Drupal\my_dkan_module\DataSource\DatabaseDataSource
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
  '#theme' => 'my_dkan_module',
  '#table' => ['#type' => 'table', '#header' => $header, '#rows' => $rows],
  '#pager' => ['#type' => 'pager', '#element' => 0],
  '#attached' => ['library' => ['my_dkan_module/data_preview']],
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
    $builder = \Drupal::service('my_dkan_module.builder');
    // ... build and return $element
    return $element;
  }

}
```

Usage: `['#type' => 'data_preview', '#resource_id' => $id]`

## 5. Routing

```yaml
my_dkan_module.preview:
  path: '/admin/dkan/data-preview/{resource_id}'
  defaults:
    _controller: '\Drupal\my_dkan_module\Controller\DataPreviewController::preview'
    _title_callback: '\Drupal\my_dkan_module\Controller\DataPreviewController::title'
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
 *   id = "my_dkan_module",
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
function my_dkan_module_theme() {
  return [
    'my_dkan_module' => [
      'variables' => [
        'table' => NULL,
        'pager' => NULL,
        'page_size_form' => NULL,
        'result_summary' => NULL,
      ],
      'template' => 'my-dkan-module',
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

> **Warning**: Template filename uses **hyphens** (`my-dkan-module.html.twig`), theme hook and `#theme` value use **underscores** (`my_dkan_module`). These must match.

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
name: My DKAN Module
description: Example custom module that extends DKAN.
type: module
core_version_requirement: ^10.2 || ^11
package: DKAN
dependencies:
  - dkan:dkan_common
  - dkan:dkan_datastore
  - dkan:dkan_metastore
```

Dependencies format: `{project}:{module}` (e.g., `dkan:dkan_datastore`). DKAN 4.x submodule machine names are `dkan_`-prefixed. Use `drupal:{module}` for core modules.

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

## 16. Custom Entities

For a stateful module that owns its own storage, define entity types. DI, forms, and config-read patterns are covered above (sections 1, 8, 9); this section covers only the entity definitions. Working examples: `<webroot>/modules/custom/dkan_drupal_ai_query/src/Entity/`.

> **Note**: D10.3+ supports PHP attribute entity definitions (`#[ContentEntityType(...)]`, `#[ConfigEntityType(...)]`). The DKAN custom modules in this checkout still use the **docblock annotation** form (`@ContentEntityType`, `@ConfigEntityType`) shown below. Both are valid; the attribute form is the same keys expressed as named arguments.

### Content entity

`Conversation` and `Message` extend `ContentEntityBase`. Annotation declares `id`, `base_table`, `entity_keys`, optional `handlers`; base fields come from `baseFieldDefinitions()`.

```php
use Drupal\Core\Entity\ContentEntityBase;
use Drupal\Core\Entity\EntityTypeInterface;
use Drupal\Core\Field\BaseFieldDefinition;

/**
 * @ContentEntityType(
 *   id = "dkan_aiq_conversation",
 *   label = @Translation("DKAN AI Query Conversation"),
 *   handlers = {
 *     "access" = "Drupal\dkan_drupal_ai_query\Entity\ConversationAccessControlHandler",
 *   },
 *   base_table = "dkan_aiq_conversations",
 *   entity_keys = {
 *     "id" = "id",
 *     "uuid" = "uuid",
 *     "label" = "title",
 *     "uid" = "uid",
 *   },
 *   internal = TRUE,
 * )
 */
class Conversation extends ContentEntityBase {

  public static function baseFieldDefinitions(EntityTypeInterface $entity_type): array {
    $fields = parent::baseFieldDefinitions($entity_type);
    $fields['title'] = BaseFieldDefinition::create('string')
      ->setLabel(t('Title'))
      ->setRequired(TRUE)
      ->setSettings(['max_length' => 255]);
    $fields['uid'] = BaseFieldDefinition::create('entity_reference')
      ->setSetting('target_type', 'user');
    // ...created/changed via 'created'/'changed' field types.
    return $fields;
  }

}
```

`entity_keys` map the entity's special keys to base-field names. Only keys with a backing field are listed — `Message` declares just `"id" = "id"` (no uuid/label). `internal = TRUE` hides the type from generic UIs. Common handlers: `list_builder`, `access`, `form`, `route_provider`, `views_data` — declare only what you use (`Conversation` ships just `access`). Entity-reference base fields point at other custom types (`Message.conversation_id` targets `dkan_aiq_conversation`).

### Config entity

`DatasetCaveat` extends `ConfigEntityBase` and implements its interface. No base fields — persisted properties are listed in `config_export`, and a matching schema entry is required.

```php
/**
 * @ConfigEntityType(
 *   id = "dataset_caveat",
 *   label = @Translation("Dataset caveat"),
 *   handlers = {
 *     "list_builder" = "Drupal\dkan_drupal_ai_query\DatasetCaveatListBuilder",
 *     "form" = {
 *       "add" = "Drupal\dkan_drupal_ai_query\Form\DatasetCaveatForm",
 *       "edit" = "Drupal\dkan_drupal_ai_query\Form\DatasetCaveatForm",
 *       "delete" = "Drupal\Core\Entity\EntityDeleteForm",
 *     },
 *     "route_provider" = {
 *       "html" = "Drupal\Core\Entity\Routing\DefaultHtmlRouteProvider",
 *     },
 *   },
 *   admin_permission = "administer dkan dataset caveats",
 *   config_prefix = "caveat",
 *   entity_keys = { "id" = "id", "label" = "label" },
 *   config_export = { "id", "label", "dataset_uuid", "suppression", "column_caveats", "freshness", "code_lists" },
 *   links = {
 *     "collection" = "/admin/dkan/ai-query/caveats",
 *     "add-form" = "/admin/dkan/ai-query/caveats/add",
 *     "edit-form" = "/admin/dkan/ai-query/caveats/{dataset_caveat}/edit",
 *   }
 * )
 */
class DatasetCaveat extends ConfigEntityBase implements DatasetCaveatInterface {
  protected $id;
  protected $label;
  // ...one typed property per config_export key.
}
```

Each `config_export` key needs a `mapping` entry in `config/schema/{module}.schema.yml` under `{module}.{config_prefix}.*` (here `dkan_drupal_ai_query.caveat.*`, `type: config_entity`). Config entities persist as `{module}.{config_prefix}.{id}` config objects, so `DefaultHtmlRouteProvider` + the declared `form` handlers + `links` give you the admin CRUD UI for free. `config_prefix` defaults to the entity ID when omitted.

> **Warning**: Content entity tables are created by the entity schema, not by `hook_schema()`. In kernel tests call `$this->installEntitySchema('dkan_aiq_conversation')` before saving (cross-ref `dkan-testing.md`). Config entities need no schema install but **will** fail config import/validation if a `config_export` key lacks a schema mapping.
