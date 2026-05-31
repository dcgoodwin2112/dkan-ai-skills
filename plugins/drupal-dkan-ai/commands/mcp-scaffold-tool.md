---
description: Scaffold a Tool plugin for the contrib MCP Server module (drupal/mcp_server)
argument-hint: <module_path> <ToolName> [--write]
---

Scaffold a new `#[Tool]` plugin for the `mcp_server` module — exposes one callable
action to MCP clients.

Read [SKILL.md](../skills/drupal-mcp-server/SKILL.md),
[tool-plugins.md](../skills/drupal-mcp-server/reference/tool-plugins.md), and
[auth-and-access.md](../skills/drupal-mcp-server/reference/auth-and-access.md)
before proceeding.

## Input

`$ARGUMENTS` should be: `<module_path> <ToolName> [--write]`

- `module_path`: Path to the target module relative to the project root, or just the machine name.
- `ToolName`: PascalCase class name (e.g., `QueryDatastore`, `GetWeather`). A `Tool` suffix is conventional but optional.
- `--write`: Optional. Marks the tool as a mutating operation — adds `checkAccess()` with a permission gate and sets the destructive/readOnly annotations accordingly. Omit for read-only tools.

## Steps

### 1. Version gate

This scaffold targets the **0.6 / `dev-main`** SDK API (`execute(array $arguments,
ClientGateway $gateway)`, `Mcp\Server\ClientGateway`). Confirm the installed
reality:

```bash
composer show drupal/mcp_server mcp/sdk
```

- If `mcp/sdk` is `0.4`/`0.5` (API `Builder::addTool()`, no `ClientGateway`) while `mcp_server` is `2.x`, **stop** — the module references SDK classes that aren't installed and won't load. Tell the user to align the versions (bump `mcp/sdk` to `dev-main`, or pin `mcp_server` to a matching branch) first.
- Verify the base class and interface exist: `ls <webroot>/modules/contrib/mcp_server/src/Plugin/ToolPluginBase.php`.

### 2. Locate module and derive identifiers

- Read `<module_path>/<module_name>.info.yml` for the machine name.
- Plugin ID / **MCP wire name**: snake_case of `ToolName`, no module prefix (e.g. `QueryDatastore` → `query_datastore`). MCP wire names are flat — **no `:`** (reserved; `.` only for derivatives).
- Class FQN: `Drupal\<module_name>\Plugin\Tool\<ToolName>`.

### 3. Update `<module_name>.info.yml` dependencies

Ensure `mcp_server:mcp_server` is present under `dependencies:`.

### 4. Generate the Tool plugin class

Path: `<module_path>/src/Plugin/Tool/<ToolName>.php`. **Directory is `Plugin/Tool/`
(singular, PascalCase).**

```php
<?php

declare(strict_types=1);

namespace Drupal\<module_name>\Plugin\Tool;

use Drupal\Core\StringTranslation\TranslatableMarkup;
use Drupal\mcp_server\Attribute\Tool;
use Drupal\mcp_server\Plugin\ToolPluginBase;
use Mcp\Server\ClientGateway;
// --write only:
// use Drupal\Core\Access\AccessResult;
// use Drupal\Core\Access\AccessResultInterface;
// use Drupal\Core\Session\AccountInterface;

#[Tool(
  id: '<snake_case_name>',
  label: new TranslatableMarkup('<Human Label>'),
  description: new TranslatableMarkup('TODO: One precise sentence — the LLM reads this to decide when to call. State inputs and outputs.'),
  inputSchema: [
    'type' => 'object',
    'properties' => [
      'input' => ['type' => 'string', 'description' => 'TODO describe.'],
    ],
    'required' => ['input'],
  ],
  // outputSchema is advisory; add it for high-value structured returns.
  readOnly: <TRUE unless --write>,
  destructive: <FALSE unless --write>,
  idempotent: FALSE,
  openWorld: FALSE,
)]
final class <ToolName> extends ToolPluginBase {

  /**
   * {@inheritdoc}
   *
   * Native plugins start disabled; opt this one in.
   */
  protected function defaultConfiguration(): array {
    return ['enabled' => TRUE];
  }

  // Inject services by overriding create() (call parent first — it wires current_user):
  // public static function create(ContainerInterface $c, array $cfg, $id, $def): static {
  //   $i = parent::create($c, $cfg, $id, $def);
  //   $i->myService = $c->get('<service_id>');
  //   return $i;
  // }

  /**
   * {@inheritdoc}
   */
  public function execute(array $arguments, ClientGateway $gateway): mixed {
    // 1. Validate/normalize $arguments (keys match inputSchema properties).
    // 2. Call the injected service / perform the action.
    // 3. Return a JSON-serializable result. Catch exceptions and return a
    //    structured error rather than throwing (an uncaught throw can abort
    //    the stdio run loop).
    return ['success' => TRUE, 'data' => []];
  }

}
```

**`--write` only** — add a permission gate (and set `readOnly: FALSE`,
`destructive: TRUE` in the attribute):

```php
public function checkAccess(AccountInterface $account): AccessResultInterface {
  return AccessResult::allowedIfHasPermission($account, 'administer <module_name> via mcp');
}
```

Then **remind the user**: `checkAccess()` is inert until a `RequestEvent`
subscriber enforces it — scaffold or point them at the `ToolAccessSubscriber`
pattern in [auth-and-access.md](../skills/drupal-mcp-server/reference/auth-and-access.md),
and declare `administer <module_name> via mcp` in `<module_name>.permissions.yml`.

### 5. Generate a unit test stub

Path: `<module_path>/tests/src/Unit/Plugin/Tool/<ToolName>Test.php`. Test the logic
you own — `execute()` argument handling, the delegated service call, and the
return shape. Mock injected services; pass a mocked `ClientGateway`. Don't test
framework discovery. See
[testing.md](../skills/drupal-mcp-server/reference/testing.md).

### 6. Cache rebuild

```bash
drush cr   # or: ddev drush cr
```

### 7. Verify runtime discovery

Don't report done on scaffold output alone — attribute typos and `create()`
service errors only surface here:

```bash
drush ev "var_dump(array_key_exists('<snake_case_name>', \Drupal::service('plugin.manager.mcp_server.tool')->getDefinitions()) ? 'FOUND' : 'NOT FOUND');"
```

Expected: `FOUND`. If `NOT FOUND`: missing `drush cr`, or `defaultConfiguration()`
didn't set `enabled => TRUE`, or the attribute failed to parse.

### 8. Print next steps

1. Implement `execute()` — validate `$arguments`, call the service, shape the return; catch exceptions into a structured error.
2. Refine `description:` and `inputSchema` — the client validates input against the schema and the LLM selects the tool from the description.
3. Set the annotation flags honestly (`readOnly`/`destructive`/`idempotent`/`openWorld`) — they're client hints, not enforcement.
4. For write tools: enforce access via a `RequestEvent` subscriber; declare the permission.
5. Exercise it end-to-end over a transport (`drush mcp:server`, or `POST` the HTTP route — verify its path).
6. Run the unit test: `cd <module_path> && vendor/bin/phpunit tests/src/Unit/Plugin/Tool/<ToolName>Test.php`.

## Pitfall checks before reporting done

- [ ] SDK/module versions are compatible (step 1) — else the module won't load.
- [ ] Directory is exactly `src/Plugin/Tool/`; namespace `Drupal\<module>\Plugin\Tool`.
- [ ] `defaultConfiguration()` returns `['enabled' => TRUE]` (native tools start disabled).
- [ ] `execute(array $arguments, ClientGateway $gateway): mixed` — exact signature.
- [ ] `inputSchema` property names match the keys read from `$arguments`.
- [ ] Plugin ID has no `:`.
- [ ] `--write`: `checkAccess()` added **and** the user is told it needs a `RequestEvent` subscriber + a declared permission.
- [ ] `drush cr` ran; discovery verified (`FOUND`).
