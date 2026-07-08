# Routing, Forms & Rendering

The request→response surface: routes and access, the Form API, render arrays, and
theming. Examples use `my_module`. DI patterns for controllers are in
[services-and-di.md](services-and-di.md).

## Routing

```yaml
my_module.report:
  path: '/admin/my-module/report/{id}'
  defaults:
    _controller: '\Drupal\my_module\Controller\ReportController::view'
    _title_callback: '\Drupal\my_module\Controller\ReportController::title'
  requirements:
    _permission: 'administer my_module'
  options:
    _admin_route: TRUE
```

### Access keys

| Key | Value | Use |
|---|---|---|
| `_permission` | permission string (`'+'`/`','` for OR/AND) | user must have permission |
| `_role` | role id | user must have role (prefer `_permission`) |
| `_access` | `'TRUE'` | unrestricted |
| `_custom_access` | `'\Drupal\…\Controller::access'` | method returns `AccessResultInterface` |
| `_entity_access` | `'entity.operation'` (`node.update`) | delegates to the entity's access handler |

### Defining permissions (`my_module.permissions.yml`)

Every `_permission` string must be defined, or the check denies everyone except
user 1. Keys are the literal permission strings used in routing and
`hasPermission()`:

```yaml
administer my_module:
  title: 'Administer My Module'
  description: 'Configure My Module settings.'
  restrict access: true
permission_callbacks:
  - '\Drupal\my_module\MyModulePermissions::permissions'
```

`restrict access: true` adds the "security implications" warning in the UI.
`permission_callbacks` (top-level, not per-permission) generates dynamic
permissions — the callback returns an array in the same shape (e.g. one entry per
bundle). New permissions appear after a cache rebuild; *granting* them is config
(`user.role.*`), so existing sites need an update hook or config change to assign
them.

### `AccessResult` + cacheability

```php
return AccessResult::allowedIf($account->hasPermission('administer my_module'))
  ->addCacheableDependency($entity)        // invalidate with the entity
  ->addCacheContexts(['user.permissions']) // vary by permission
  ->cachePerPermissions();
```

`allowed()` / `forbidden()` / `neutral()` — `forbidden()` from any checker wins;
`neutral` defers. Always attach the cacheability that the decision depends on.

> **Title callbacks return `string` or `TranslatableMarkup`, never a render array.**

## Form API

Extend `FormBase`, or `ConfigFormBase` for settings forms. The `ConfigFormBase`
gotcha: `getEditableConfigNames()` must return the exact config object names the form
edits — omit it and `parent::submitForm()` saves nothing — and `buildForm()`/
`submitForm()` must call their `parent::` implementations.

## Render arrays

A render array is a tree of `#`-prefixed properties resolved late (the render pipeline),
which is what makes caching and lazy building possible.

### `#type` vs `#theme`

- `#type` → a **render element** plugin (PHP, `RenderElementBase`); see
  [hooks-events-plugins.md](hooks-events-plugins.md#render-elements).
- `#theme` → a **template** (Twig) registered in a `theme` hook.

Both can coexist — `#type` for structure, `#theme` for custom output:

```php
return [
  '#theme' => 'my_module_widget',
  '#table' => ['#type' => 'table', '#header' => $header, '#rows' => $rows, '#empty' => $this->t('None.')],
  '#pager' => ['#type' => 'pager'],
  '#attached' => ['library' => ['my_module/widget']],
  '#cache' => [
    'contexts' => ['url.query_args:page'],
    'tags' => ['node_list'],
    'max-age' => 3600,
  ],
];
```

### `#cache`

| Key | Purpose | Example |
|---|---|---|
| `contexts` | vary by request dimension | `['url.query_args:page', 'user.roles']` |
| `tags` | invalidate when data changes | `['node:42', 'node_list']` |
| `max-age` | TTL seconds; `0` uncacheable, `-1` permanent | `3600` |

### `#pre_render` / `#lazy_builder`

Static callbacks deferred to render time. `\Drupal::service()` **is** correct here —
there is no DI:

```php
'#pre_render' => [[static::class, 'preRender']],
'#lazy_builder' => ['my_module.builder:build', [$id]],
```

`#lazy_builder` callbacks must take only scalar args and are the basis for placeholder
caching (BigPipe).

## Theming

### `theme` hook

```php
// OOP (D11.1): a #[Hook('theme')] method, or procedural my_module_theme():
return [
  'my_module_widget' => [
    'variables' => ['items' => [], 'title' => NULL],
    'template' => 'my-module-widget',
  ],
];
```

### Libraries (`{module}.libraries.yml`)

```yaml
widget:
  css:
    component:
      css/widget.css: {}
  js:
    js/widget.js: {}
  dependencies:
    - core/drupal
    - core/once
```

Attach: `'#attached' => ['library' => ['my_module/widget']]`.

> **`core/once`, not `jQuery.once`.** `jQuery.once` was removed in D10. Use the
> `core/once` library and `once('myBehavior', selector, context)` in behaviors.

> **Filename vs hook name.** Template file `my-module-widget.html.twig` (hyphens);
> theme hook and `#theme` value `my_module_widget` (underscores). They must correspond
> or Drupal silently renders nothing custom.
