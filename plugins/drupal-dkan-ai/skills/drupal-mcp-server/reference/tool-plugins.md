# Tool Plugins

The primary extension point: a `#[Tool]` plugin exposes one callable action to
MCP clients (`tools/list` advertises it, `tools/call` invokes it). Signatures
here are the **0.6** SDK API (`mcp/sdk ^0.6`; `0.6.0` tagged) — verify against your
installed version (see [SKILL.md](../SKILL.md) volatility note).

## Anatomy

- **Discovery:** `#[Tool]` PHP 8 attribute on a class under `src/Plugin/Tool/`,
  namespace `Drupal\<module>\Plugin\Tool`. Manager: `ToolPluginManager`
  (`plugin.manager.mcp_server.tool`). Cache backend `mcp_server_tool_plugins`,
  tag `mcp_server:tools`.
- **Base class:** extend `Drupal\mcp_server\Plugin\ToolPluginBase` (implements
  `ToolPluginInterface` + `ContainerFactoryPluginInterface`).
- **Handler:** implement `execute(array $arguments, ClientGateway $gateway): mixed`
  — inherited contract from the SDK's `ToolHandlerInterface`, **not**
  defined on the base. This is the method the SDK calls on `tools/call`.

## The `#[Tool]` attribute

Constructor params (`src/Attribute/Tool.php`). The attribute is the authoring
surface; `get()` builds the typed `ToolDefinition` the manager returns.

| Param | Type | Notes |
|---|---|---|
| `id` | `string` | Plugin ID = MCP wire name. **Required.** No `:` (use `.` for derivatives). |
| `label` | `TranslatableMarkup` | **Required.** |
| `description` | `TranslatableMarkup` | **Required.** What the LLM reads to decide when to call. Be precise about inputs/outputs. |
| `inputSchema` | `array` | JSON Schema for arguments. Lives here, not in code (see below). |
| `outputSchema` | `?array` | Optional JSON Schema for the structured result. `NULL` = none. |
| `module_dependencies` | `string[]` | Modules this tool needs (e.g. `['node']`). |
| `deriver` | `?class-string` | Deriver for dynamic/derivative tools. |
| `readOnly` | `bool` | Annotation: no side effects. Default `FALSE`. |
| `destructive` | `bool` | Annotation: may modify/delete. Default **`TRUE`**. |
| `idempotent` | `bool` | Annotation: repeats are no-ops. Default `FALSE`. |
| `openWorld` | `bool` | Annotation: touches external systems. Default `TRUE`. |

The four annotation flags are **client hints** surfaced on `tools/list` — they do
**not** enforce anything. Set them honestly so clients can prompt for
confirmation, but gate real access with a `RequestEvent` subscriber
([auth-and-access.md](auth-and-access.md)).

> **Schemas live in the attribute.** `ToolPluginBase::getInputSchema()` /
> `getOutputSchema()` return empty/`NULL`; the factory feeds the SDK from the
> attribute's `inputSchema:` / `outputSchema:`, which take precedence. Write JSON
> Schema property names to match the keys you read from `$arguments`.

## `ToolPluginInterface` / `ToolPluginBase`

```php
interface ToolPluginInterface extends PluginInspectionInterface, ToolHandlerInterface {
  getTitle(): TranslatableMarkup;
  getDescription(): ?TranslatableMarkup;
  getDependencies(): array;                                      // module machine names
  checkAccess(AccountInterface $account): AccessResultInterface; // declared; NOT auto-called
  checkToolAccess(string $toolId, AccountInterface $account): AccessResultInterface;
  getConfiguration(): array;
  setConfiguration(array $configuration): void;
  isEnabled(): bool;
  // execute(array $arguments, ClientGateway $gateway): mixed;   // from ToolHandlerInterface
}
```

`ToolPluginBase` provides everything except `execute()`. Defaults worth knowing:

- Injects `current_user` (`AccountProxyInterface`) via `create()`; metadata reads
  from the typed `$this->pluginDefinition` (`ToolDefinition`).
- `checkAccess()` returns `AccessResult::allowed()` — override to restrict, **but
  overriding alone does nothing** until a subscriber calls it.
- `isEnabled()` reads `configuration['enabled']`; `defaultConfiguration()` returns
  `['enabled' => FALSE]` — **native tools must override to `TRUE`** (next section).
- `DERIVATIVE_SEPARATOR` is `.` (not core's `:`).
- `buildConfigurationForm()` / validate / submit are no-op hooks for the
  `mcp_server_ui` settings form.

## Enablement (native vs. config)

A code-defined tool isn't registered unless `isEnabled()` is true. There is no
saved config for a native plugin out of the box, so override:

```php
protected function defaultConfiguration(): array {
  return ['enabled' => TRUE];
}
```

(Forget this and the tool is discovered but absent from `tools/list`. This is
interim — upstream tools-UI work will make enablement config-driven.)

## Full example

`mcp_server_examples`' `EchoTool`, trimmed — the canonical shape:

```php
<?php

declare(strict_types=1);

namespace Drupal\my_module\Plugin\Tool;

use Drupal\Core\StringTranslation\TranslatableMarkup;
use Drupal\mcp_server\Attribute\Tool;
use Drupal\mcp_server\Plugin\ToolPluginBase;
use Mcp\Server\ClientGateway;

#[Tool(
  id: 'echo',
  label: new TranslatableMarkup('Echo'),
  description: new TranslatableMarkup('Echoes back the input message, optionally with a prefix.'),
  inputSchema: [
    'type' => 'object',
    'properties' => [
      'message' => ['type' => 'string', 'description' => 'The message to echo back.'],
      'prefix' => ['type' => 'string', 'description' => 'Optional prefix.'],
    ],
    'required' => ['message'],
  ],
  outputSchema: [
    'type' => 'object',
    'properties' => ['echo' => ['type' => 'string']],
    'required' => ['echo'],
  ],
  readOnly: TRUE,
  destructive: FALSE,
  idempotent: TRUE,
  openWorld: FALSE,
)]
final class EchoTool extends ToolPluginBase {

  protected function defaultConfiguration(): array {
    return ['enabled' => TRUE];
  }

  public function execute(array $arguments, ClientGateway $gateway): mixed {
    $message = $arguments['message'] ?? '';
    $prefix = $arguments['prefix'] ?? '';
    $result = $prefix !== '' ? "$prefix: $message" : $message;
    return ['success' => TRUE, 'message' => $result, 'data' => ['echo' => $result]];
  }

}
```

### Injecting services

Override `create()` to pull dependencies, calling the parent first (it wires
`current_user`):

```php
public static function create(ContainerInterface $container, array $configuration, $plugin_id, $plugin_definition): static {
  $instance = parent::create($container, $configuration, $plugin_id, $plugin_definition);
  $instance->myService = $container->get('my_module.my_service');
  return $instance;
}
```

This is how a DKAN tool plugin delegates to a DKAN service — keep the plugin a
thin adapter (validate `$arguments`, call the service, shape the return). See
[dkan-integration.md](dkan-integration.md).

### `$arguments` and the return value

- `$arguments` is the validated, decoded argument map (keys = your
  `inputSchema` property names). The SDK validates against `inputSchema` before
  calling you.
- Return any JSON-serializable `mixed`. A `['success' => ..., 'data' => ...]`
  shape is the example convention, not a requirement. For robustness, catch
  exceptions and return a structured error rather than throwing — an uncaught
  throw can abort the stdio run loop.
- `$gateway` (`Mcp\Server\ClientGateway`) lets a tool call back to the client —
  notably **sampling** (ask the client's LLM to generate text). Most tools ignore
  it. See the SDK's `references/sdk/client-sampling.md`.

## Derivers

For one plugin class that emits many tools (e.g. one per entity type), set
`deriver:` on the attribute. The deriver returns derivative definitions; Drupal's
`DerivativeDiscoveryDecorator` finds it via `ToolDefinition::getDeriver()` and
clones the base with `ToolDefinition::withDerivative(...)` to populate
derivative-only fields. **Emit derivative IDs with `.`** (`base.derivative`) — the
`DotDerivativeDiscoveryDecorator` enforces MCP name validity; a `:` is rejected by
the SDK `NameValidator`. Canonical example: `references/tools/tool-api-bridge.md`
(the `mcp_server_tool_bridge` `ToolApi` deriver).

## Lookup API

- `ToolPluginManager::getDefinitions()` → `array<string, ToolDefinition>` (base + derivatives).
- `ToolPluginManager::createInstance($id)` → plugin instance from its typed definition.

`getAllTools()`, `getTool()`, `getRegistrations()`, `parseToolId()`, and the old
`ToolRegistration` DTO **no longer exist** — the encoded plugin ID is the sole
wire identifier and `ToolDefinition` the sole metadata carrier.

## Verify discovery

```bash
drush cr
drush ev "var_dump(array_keys(\Drupal::service('plugin.manager.mcp_server.tool')->getDefinitions()));"
```

Your `id` should appear. Then exercise it end-to-end over a transport
([mcp-overview.md#transports](mcp-overview.md#transports)). Don't report done on
scaffold output alone — attribute typos and `create()` service errors only surface
at instantiation.
