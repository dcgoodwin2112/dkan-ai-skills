---
name: drupal-module-dev
description: Conventions and decision support for writing or modifying any custom/contrib Drupal module — .module/.install/*.info.yml/*.services.yml/*.routing.yml, plugins (src/Plugin/**), forms, controllers, hooks (src/Hook/**), event subscribers, entities, config schema, or module tests — and questions about Drupal 10/11 APIs, conventions, or deprecations (dependency injection, render arrays, #[Hook], plugin attributes vs annotations, config validation, hook_update_N vs post_update, PHPUnit base classes). Targets Drupal 10.2+ / 11. This is the general Drupal layer; for DKAN specifics see dkan-module-author, for drupal/ai plugins see drupal-ai-module, for mcp_server plugins see drupal-mcp-server.
---

# Drupal Module Development

The general Drupal module-authoring layer: dependency injection, hooks/events/plugins,
routing/forms/rendering, config & entities, the module lifecycle, and testing &
standards — for Drupal 10.2+ / 11 on PHP 8.3.

> **General Drupal, not DKAN.** This skill is the foundation the domain skills build
> on. For DKAN metastore/datastore/harvest specifics use
> [`dkan-module-author`](../dkan-module-author/SKILL.md); for `drupal/ai` plugins use
> [`drupal-ai-module`](../drupal-ai-module/SKILL.md); for `mcp_server` plugins use
> [`drupal-mcp-server`](../drupal-mcp-server/SKILL.md). Those skills cross-reference
> here for the conventions below rather than restating them.

> **Verify against your core version.** Facts below cite the Drupal version that
> introduced them. The API surface moved fast across 10.2→11.x (OOP hooks, plugin
> attributes, config validation, the requirements split, the D11.4 testing changes).
> Check the running core version before relying on a leading-edge item; the ones most
> in flux are flagged inline.

## Pick the right doc for the task

| Task | Read |
|---|---|
| Inject a service; write `services.yml`; autowiring; logging; translation; Drush commands | [reference/services-and-di.md](reference/services-and-di.md) |
| Implement a hook (OOP `#[Hook]` vs procedural); subscribe to an event; define a plugin (attribute vs annotation) | [reference/hooks-events-plugins.md](reference/hooks-events-plugins.md) |
| Add a route + controller; build a form; assemble a render array; theme/library | [reference/routing-forms-rendering.md](reference/routing-forms-rendering.md) |
| Read/write config; config schema & validation; define a content or config entity | [reference/config-and-entities.md](reference/config-and-entities.md) |
| `.info.yml`; install/uninstall/schema; `hook_update_N` vs `post_update`; requirements; recipes | [reference/module-lifecycle.md](reference/module-lifecycle.md) |
| Write a unit/kernel/functional test; deprecation testing; phpcs/phpstan | [reference/testing-and-standards.md](reference/testing-and-standards.md) |
| Scaffold a service / route / event subscriber | run `/scaffold-drupal-service`, `/add-drupal-route`, `/add-event-subscriber` |

## Always-true rules (the things people get wrong on first attempt)

1. **Inject services; never `\Drupal::service()` in a DI-capable class.** Controllers,
   forms, plugins, services, and subscribers all get dependencies via constructor
   injection (`create()` or `services.yml`). `\Drupal::` static access is only correct
   in procedural contexts (`.module`/`.install` files, static `#pre_render`/`#lazy_builder`
   callbacks) where no container is wired. ([services-and-di.md](reference/services-and-di.md))
2. **`->accessCheck(TRUE|FALSE)` is mandatory on every entity query.** Deprecated in
   D10, **fatal since D11** if omitted. Decide explicitly: `TRUE` for user-facing lists,
   `FALSE` for system/internal logic. ([routing-forms-rendering.md](reference/routing-forms-rendering.md), [config-and-entities.md](reference/config-and-entities.md))
3. **PHP attributes are the default for plugins.** Available for all plugin types by
   D10.2–11.2; `@Annotation` discovery is deprecated. Omitting the attribute class is
   deprecated in **D11.2**, required in **D12**, annotations removed in **D13**. New
   code uses attributes; `@Translation()` becomes `new TranslatableMarkup()`.
   ([hooks-events-plugins.md](reference/hooks-events-plugins.md))
4. **Prefer OOP `#[Hook]` for new code** (D11.1, a class in `src/Hook/`, autowired). For
   a module that must also run on D10, keep one procedural `hook_x()` that delegates and
   mark the OOP method `#[LegacyHook]` so the hook doesn't fire twice. Install/update/
   schema/requirements hooks stay procedural. ([hooks-events-plugins.md](reference/hooks-events-plugins.md))
5. **Config schema is effectively required.** Tests run with strict schema checking
   (D10.2) and config is constraint-validated; unschema'd keys fail. Mark validatable
   config `FullyValidatable` (D10.3) and give every property a type + constraints.
   ([config-and-entities.md](reference/config-and-entities.md))
6. **`hook_update_N` = schema/raw-DB only; `hook_post_update_NAME` = entity/config CRUD.**
   Update hooks run before the container/entity definitions are guaranteed current —
   doing entity or config API work there breaks. Use `post_update` for anything touching
   entities, config objects, or services. ([module-lifecycle.md](reference/module-lifecycle.md))
7. **`hook_requirements` is split (D11.2).** Runtime checks → `hook_runtime_requirements`;
   update-time → `hook_update_requirements`; install-time → an
   `InstallRequirementsInterface` class at `src/Install/Requirements/`. The combined
   `hook_requirements` is deprecated. ([module-lifecycle.md](reference/module-lifecycle.md))
8. **Prefer events over hooks** when both exist — a tagged `event_subscriber` service is
   testable and DI-aware. ([hooks-events-plugins.md](reference/hooks-events-plugins.md))
9. **Template filename hyphens vs theme-hook underscores must match.** Theme hook /
   `#theme` value use underscores (`my_module_widget`); the Twig file uses hyphens
   (`my-module-widget.html.twig`). A mismatch silently falls back to default markup.
   ([routing-forms-rendering.md](reference/routing-forms-rendering.md))

## Top pitfalls

Symptom → cause → fix.

1. **`QueryException`/fatal on an entity query.** Cause: no `accessCheck()`. Fix: add
   `->accessCheck(TRUE)` or `->accessCheck(FALSE)` explicitly (rule 2).
2. **`ConfigFormBase` saves nothing.** Cause: `getEditableConfigNames()` not implemented
   (or returns the wrong object name). Fix: return the exact config object name(s) the
   form edits.
3. **Config save fails a strict-schema test** (`Schema errors for … missing schema`).
   Cause: a config key with no schema entry, or a validatable object not marked
   `FullyValidatable`. Fix: add the `config/schema/*.schema.yml` mapping for every key.
4. **A hook fires twice.** Cause: an OOP `#[Hook]` method plus a still-live procedural
   `hook_x()` doing the same work. Fix: mark the OOP method `#[LegacyHook]` and have the
   procedural shim only delegate (or delete it if D11-only).
5. **Update breaks on entity/config access.** Cause: entity or config API calls in
   `hook_update_N`. Fix: move them to `hook_post_update_NAME` (rule 6).
6. **Translated string renders with literal `@`/concatenated fragments.** Cause:
   concatenating `t()` calls or using the wrong placeholder prefix. Fix: a single `t()`
   with `@`/`%`/`:` placeholders — never string concatenation.
7. **`Error: Class "Drupal" not found` / null container in a class.** Cause:
   `\Drupal::service()` in a DI-capable class. Fix: inject via constructor (rule 1).

## Cheat sheets

**DI `create()` by class type:**

| Class type | Base / interface | `create()` signature |
|---|---|---|
| Controller | `ControllerBase` | `create(ContainerInterface $c): static` |
| Form | `FormBase` / `ConfigFormBase` | `create(ContainerInterface $c): static` |
| Block / factory plugin | `…Base` + `ContainerFactoryPluginInterface` | `create($c, array $configuration, $plugin_id, $plugin_definition)` |
| Service / EventSubscriber | none (define in `services.yml`) | N/A — constructor args, or autowire |

**Version floor & deprecation quick-hits (D11.0):**

| Item | Fact |
|---|---|
| PHP / Symfony | PHP **8.3** floor, **Symfony 7** |
| Entity queries | `->accessCheck()` mandatory (fatal) |
| JS | `jQuery.once` removed → `core/once` |
| Removed core modules | Book, Forum, Statistics, Tracker, Tour, Actions UI (moved to contrib) |

**Plugin attribute / annotation timeline:**

| Milestone | State |
|---|---|
| D10.2 | Attributes introduced (first plugin types) |
| ~D11.2 | All core plugin types support attributes; omitting attribute class deprecated |
| D12 | Attribute class **required** |
| D13 | Annotation discovery **removed** |

## Version & deprecation notes

- **OOP hooks:** `#[Hook]` (D11.1) supersedes procedural hooks for most cases; preprocess
  functions gained OOP support in D11.1. `#[LegacyHook]` is the D10 back-compat bridge;
  hook ordering uses `order:` on the attribute or `#[ReorderHook]` (D11.2).
- **Recipes & config actions** (D10.3+) are stabilizing across the 11.x line — treat the
  exact action set (`createIfNotExists`, `simpleConfigUpdate`, `setProperties` added
  D11.2, `grantPermissions`) and stability as version-dependent; verify against your core.
- **Deprecation testing changed in D11.4:** `expectDeprecation()` / `@group legacy` are
  superseded by `#[IgnoreDeprecations]` + `expectUserDeprecationMessage()`. Use the form
  that matches your core version. ([testing-and-standards.md](reference/testing-and-standards.md))
- **Cross-refs:** DKAN module authoring → [`dkan-module-author`](../dkan-module-author/SKILL.md);
  AI plugins → [`drupal-ai-module`](../drupal-ai-module/SKILL.md); MCP tools →
  [`drupal-mcp-server`](../drupal-mcp-server/SKILL.md). Scaffolds: `/scaffold-drupal-service`,
  `/add-drupal-route`, `/add-event-subscriber`.
