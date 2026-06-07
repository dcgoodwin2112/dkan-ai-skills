# Config & Entities

The persistence layer: the Config API, config schema & validation (now effectively
required), and content vs config entity definitions. Examples use `my_module`.

## Config API

Inject `ConfigFactoryInterface` (`@config.factory`); never `\Drupal::config()` in a
DI-capable class.

```php
// Read (immutable).
$value = $this->configFactory->get('my_module.settings')->get('key');

// Write (editable).
$this->configFactory->getEditable('my_module.settings')
  ->set('key', $value)
  ->save();
```

### The three config directories

| Dir | Role |
|---|---|
| `config/install/` | Default config imported **on module install**. Names must match the file (`my_module.settings.yml`). |
| `config/schema/` | Type/validation definitions for config objects (`my_module.schema.yml`). |
| `config/optional/` | Config installed **only if its dependencies are met** (and on later install of those deps). Avoids `UnmetDependenciesException` for config that references other modules. |

## Config schema & validation

Schema is no longer optional in practice: tests run with strict schema checking (D10.2),
and config is constraint-validated. Every config key needs a schema entry.

```yaml
# config/schema/my_module.schema.yml
my_module.settings:
  type: config_object
  label: 'My module settings'
  mapping:
    enabled:
      type: boolean
      label: 'Enabled'
    api_url:
      type: uri
      label: 'API URL'
      constraints:
        NotBlank: {}
```

### `FullyValidatable` (D10.3)

Mark a config object `FullyValidatable` so the validation system asserts that **every**
property has a type and the value satisfies its constraints — the basis for safe
config-via-API and recipes. Use `nullable: true` for optional values and `requiredKey:
false` for keys that may be absent:

```yaml
my_module.settings:
  type: config_object
  constraints:
    FullyValidatable: ~
  mapping:
    api_url:
      type: uri
      nullable: true
      constraints:
        NotBlank: {}
```

> **Strict-schema failures in tests.** A missing schema mapping or an un-`FullyValidatable`
> object surfaces as `Schema errors for my_module.settings` in kernel/functional tests
> (`$strictConfigSchema` defaults on — see [testing-and-standards.md](testing-and-standards.md)).
> Fix the schema, don't disable the check.

## Simple config vs config entities

| | Simple config | Config entity |
|---|---|---|
| Count | one object (`my_module.settings`) | many instances (`my_module.widget.foo`, `.bar`) |
| Edited via | a `ConfigFormBase` | entity CRUD UI (list/add/edit/delete) |
| Defined by | just a schema entry | a `ConfigEntityType` class + schema |
| Use when | global settings | user-creatable named configurations |

## Content vs config entities

Both define an entity type via a plugin attribute (D10.3+) or the older docblock
annotation; the keys are identical, attributes just express them as named arguments.

| | Content entity | Config entity |
|---|---|---|
| Base class | `ContentEntityBase` | `ConfigEntityBase` |
| Attribute | `#[ContentEntityType]` | `#[ConfigEntityType]` |
| Storage | database tables (entity schema) | config objects (`{module}.{prefix}.{id}`) |
| Fields | `baseFieldDefinitions()` + field UI | `config_export` properties + schema |
| Test setup | `installEntitySchema('…')` | none (config), but schema mapping required |

### Content entity

```php
use Drupal\Core\Entity\Attribute\ContentEntityType;
use Drupal\Core\Entity\ContentEntityBase;
use Drupal\Core\StringTranslation\TranslatableMarkup;

#[ContentEntityType(
  id: 'my_widget',
  label: new TranslatableMarkup('Widget'),
  base_table: 'my_widget',
  entity_keys: [
    'id' => 'id',
    'uuid' => 'uuid',
    'label' => 'title',
  ],
  handlers: [
    'access' => 'Drupal\my_module\WidgetAccessControlHandler',
  ],
)]
class Widget extends ContentEntityBase {

  public static function baseFieldDefinitions(EntityTypeInterface $entity_type): array {
    $fields = parent::baseFieldDefinitions($entity_type);
    $fields['title'] = BaseFieldDefinition::create('string')
      ->setLabel(new TranslatableMarkup('Title'))
      ->setRequired(TRUE)
      ->setSetting('max_length', 255);
    return $fields;
  }

}
```

- `entity_keys` maps the special keys (`id`/`uuid`/`label`/`bundle`/`uid`…) to base-field
  names — list only keys backed by a field.
- Declare only the **handlers** you use (`list_builder`, `access`, `form`,
  `route_provider`, `views_data`); each is optional.
- Tables come from the **entity schema**, not `hook_schema()`. In kernel tests call
  `$this->installEntitySchema('my_widget')` before saving.

### Config entity

```php
#[ConfigEntityType(
  id: 'my_widget_type',
  label: new TranslatableMarkup('Widget type'),
  config_prefix: 'type',
  admin_permission: 'administer my_module',
  entity_keys: ['id' => 'id', 'label' => 'label'],
  config_export: ['id', 'label', 'settings'],
  handlers: [
    'list_builder' => 'Drupal\my_module\WidgetTypeListBuilder',
    'form' => [
      'add' => 'Drupal\my_module\Form\WidgetTypeForm',
      'edit' => 'Drupal\my_module\Form\WidgetTypeForm',
      'delete' => 'Drupal\Core\Entity\EntityDeleteForm',
    ],
    'route_provider' => ['html' => 'Drupal\Core\Entity\Routing\DefaultHtmlRouteProvider'],
  ],
  links: [
    'collection' => '/admin/my-module/widget-types',
    'add-form' => '/admin/my-module/widget-types/add',
    'edit-form' => '/admin/my-module/widget-types/{my_widget_type}/edit',
  ],
)]
class WidgetType extends ConfigEntityBase implements WidgetTypeInterface {
  protected $id;
  protected $label;
  protected $settings = [];
}
```

- Persisted properties are exactly the `config_export` keys; **each needs a matching
  schema mapping** under `{module}.{config_prefix}.*` (`type: config_entity`), or config
  import/validation fails.
- `config_prefix` defaults to the entity ID when omitted; instances persist as
  `{module}.{config_prefix}.{id}`.
- `DefaultHtmlRouteProvider` + the `form` handlers + `links` give a full admin CRUD UI
  for free.

> **`accessCheck()` on entity queries is mandatory** (throws since Drupal 10) — see
> [routing-forms-rendering.md](routing-forms-rendering.md) and the SKILL.md rules.
