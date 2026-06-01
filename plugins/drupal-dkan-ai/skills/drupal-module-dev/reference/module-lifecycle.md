# Module Lifecycle

The install→update→uninstall path: `*.info.yml`, install/schema hooks, the
`hook_update_N` vs `hook_post_update_NAME` split, the requirements split (D11.2), and
recipes/config actions. Examples use `my_module`.

## `*.info.yml`

```yaml
name: My Module
description: Example custom module.
type: module
core_version_requirement: ^10.2 || ^11
package: Custom
dependencies:
  - drupal:node
  - drupal:views
```

- `core_version_requirement` — a Composer-style constraint; `^10.2 || ^11` is typical.
- `dependencies` use `{project}:{module}` — `drupal:` for core, the project machine name
  for contrib (`token:token`).

## Install-phase hooks (`.install`, procedural)

These are **not** OOP-discovered; they stay as functions.

| Hook | Runs | For |
|---|---|---|
| `hook_install` | once, on enable | seed data/state; prefer config in `config/install` or a recipe |
| `hook_uninstall` | on disable | clean up state/tables the module owns |
| `hook_schema` | defines `{database}` tables | only for non-entity custom tables (rare; prefer entities) |

## `hook_update_N` vs `hook_post_update_NAME`

This is the most common lifecycle mistake. The two run in different phases with
different guarantees.

| | `hook_update_N` | `hook_post_update_NAME` |
|---|---|---|
| Name | numeric: `my_module_update_NNNN()` | named: `my_module_post_update_add_field()` |
| Runs | early — schema/update phase | after all `update_N`, container rebuilt |
| Safe for | low-level schema changes, raw DB (`\Drupal::database()`) | entity API, config API, services |
| **Not** safe for | entity/config API (definitions may be stale) | — |

### `hook_update_N` numbering

`my_module_update_NNNN()` where `N` encodes `{major}{minor}{sequence}` — e.g.
`my_module_update_10001()`. The schema version is tracked per module; updates run in
numeric order. **`x000` is reserved and never runs** (it's the install baseline) — start
at `9001`/`10001`.

```php
/**
 * Add the 'priority' column.
 */
function my_module_update_10001(): void {
  $spec = ['type' => 'int', 'not null' => TRUE, 'default' => 0];
  \Drupal::database()->schema()->addField('my_table', 'priority', $spec);
}
```

```php
/**
 * Backfill widget labels.
 */
function my_module_post_update_backfill_labels(): void {
  // Entity API is safe here.
  $storage = \Drupal::entityTypeManager()->getStorage('my_widget');
  // ...load, modify, save.
}
```

## Requirements (split in D11.2)

The combined `hook_requirements($phase)` is deprecated. Split by phase:

| Concern | D11.2+ form | Location |
|---|---|---|
| Runtime status (admin status report) | `hook_runtime_requirements()` | `.module` or `#[Hook]` |
| Update-time gate | `hook_update_requirements()` | `.install` |
| Install-time gate | `InstallRequirementsInterface::getRequirements()` | `src/Install/Requirements/MyModuleRequirements.php` |

```php
// src/Install/Requirements/MyModuleRequirements.php
namespace Drupal\my_module\Install\Requirements;

use Drupal\Core\Extension\InstallRequirementsInterface;

class MyModuleRequirements implements InstallRequirementsInterface {
  public static function getRequirements(): array {
    return [
      'my_module_ext' => [
        'title' => t('My module: ext extension'),
        'value' => extension_loaded('ext') ? t('Enabled') : t('Missing'),
        'severity' => extension_loaded('ext') ? REQUIREMENT_OK : REQUIREMENT_ERROR,
      ],
    ];
  }
}
```

> **Version-dependent.** The split landed in D11.2 and the old `hook_requirements`
> deprecation was formalized in later 11.x. On D10/early-11 use `hook_requirements($phase)`
> with the `$phase` switch. Verify against your core version.

## Recipes & config actions (D10.3+)

A **recipe** is a reusable, declarative way to apply config — installing modules,
importing config, and running **config actions** (idempotent mutations on existing
config). Recipes shift install-time config out of `hook_install`.

```yaml
# recipe.yml
name: 'My feature'
type: 'Site feature'
install:
  - node
  - my_module
config:
  import:
    my_module: '*'
  actions:
    system.site:
      simpleConfigUpdate:
        slogan: 'Powered by my_module'
    user.role.editor:
      grantPermissions:
        - 'access my_module reports'
```

Common actions: `createIfNotExists`, `simpleConfigUpdate`, `setProperties` (added
D11.2), `grantPermissions`. Actions target config entities/objects that are
`FullyValidatable` (see [config-and-entities.md](config-and-entities.md)).

> **Version-dependent and stabilizing.** Recipes were experimental in D10.3 and have
> stabilized across the 11.x line; the available action plugins and their names differ
> by core version. Treat the exact action set as version-specific and verify against the
> running core before relying on it.
