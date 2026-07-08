# Authorization & Access Control

The most important thing to get right — and the easiest to get wrong. **Core
ships zero auth policy.** Read this before exposing any write tool.

## Threat model: the lethal trifecta

Risk concentrates when one agent context holds all three: **private data** (the
metastore, datastore rows, harvest config), **untrusted content** (tool outputs
count — a dataset title or harvest error your *read* tool returns is
attacker-controllable text the model will follow), and a way to **exfiltrate or
mutate** (a write tool). Any two are survivable; all three is exploitable
(OWASP LLM01/05/06).

The policy consequence this module's DKAN deployment implements: keep read-only
and read-write tools on **distinct, separately-credentialed surfaces** (the
`dkan-ro` / `dkan-rw` split — per-account stdio `--user` plus the OAuth
`dkan_mcp:read`/`dkan_mcp:write` scopes) so text injected on the read path has no
write tool in reach, and **human-gate destructive verbs** (`delete`, `drop`,
`unpublish`, bulk `patch`) behind approval that shows full, untruncated
parameters. The enforcement mechanics follow.

## The gotcha: `checkAccess()` is declared but not enforced

`ToolPluginInterface` declares `checkAccess()` / `checkToolAccess()`, and
`ToolPluginBase` implements them (returning `AccessResult::allowed()`). It is
**tempting to assume** overriding `checkAccess()` to deny will block a call. **It
will not.** Nothing in the `tools/call` dispatch path calls those methods.
Out of the box, **any client that can reach the endpoint can call any enabled
tool**, including destructive ones.

(Resources are different — the resource handler closure *does* call the
provider's `checkAccess()` on read. The gap is specific to **tools**.)

Enforcement comes from one of:

1. **`mcp_server_oauth`** — OAuth2 scopes (reads tool *config*, not the plugin's
   `checkAccess()`).
2. **Your own `RequestEvent` subscriber** — the general mechanism, below. This is
   what you write to honor a plugin's `checkAccess()` or apply any Drupal-permission
   / role / API-key policy.

## The extension point: `Mcp\Event\RequestEvent`

The SDK dispatches `Mcp\Event\RequestEvent` for **every** JSON-RPC request,
*before* any handler runs. A subscriber inspects the request and, to deny, throws
`Drupal\mcp_server\Exception\McpAuthorizationDeniedException($reason, $httpStatus)`.
`McpServerController` catches it and returns HTTP 401/403.

```
SDK Protocol::handleRequest()
 └─ dispatch Mcp\Event\RequestEvent
     ├─ subscriber inspects request
     └─ throw McpAuthorizationDeniedException($reason, $status)  → 401/403
 └─ (no throw) run the matching handler (ReferenceHandler → your plugin::execute)
```

First subscriber to throw wins; dispatch aborts immediately.

## Pattern: enforce a tool plugin's own `checkAccess()`

To make per-plugin `checkAccess()` actually gate calls, subscribe to
`RequestEvent`, resolve the plugin from the `CallToolRequest` name, and invoke its
check against the current user. This is the `ToolAccessSubscriber` shape
`dkan_mcp_server` ships ([dkan-integration.md](dkan-integration.md)):

```php
declare(strict_types=1);

namespace Drupal\my_module\EventSubscriber;

use Drupal\Core\Session\AccountInterface;
use Drupal\mcp_server\Exception\McpAuthorizationDeniedException;
use Drupal\mcp_server\Plugin\ToolPluginManager;
use Mcp\Event\RequestEvent;
use Mcp\Schema\Request\CallToolRequest;
use Symfony\Component\EventDispatcher\EventSubscriberInterface;

final class ToolAccessSubscriber implements EventSubscriberInterface {

  public function __construct(
    private readonly ToolPluginManager $toolManager,
    private readonly AccountInterface $currentUser,
  ) {}

  public static function getSubscribedEvents(): array {
    return [RequestEvent::class => 'onRequest'];
  }

  public function onRequest(RequestEvent $event): void {
    $request = $event->getRequest();
    if (!$request instanceof CallToolRequest) {
      return;
    }
    $id = $request->name;                       // wire name == plugin ID
    if (!$this->toolManager->hasDefinition($id)) {
      return;
    }
    $plugin = $this->toolManager->createInstance($id);
    if (!$plugin->checkToolAccess($id, $this->currentUser)->isAllowed()) {
      throw new McpAuthorizationDeniedException('forbidden', 403);
    }
  }

}
```

Register it (args confirmed against the DKAN plan):

```yaml
# my_module.services.yml
my_module.tool_access_subscriber:
  class: Drupal\my_module\EventSubscriber\ToolAccessSubscriber
  arguments: ['@plugin.manager.mcp_server.tool', '@current_user']
  tags:
    - { name: event_subscriber }
```

Then each write tool overrides `checkAccess()`:

```php
public function checkAccess(AccountInterface $account): AccessResultInterface {
  return AccessResult::allowedIfHasPermission($account, 'administer my_module via mcp');
}
```

> **Also gate the list, not just the call.** The subscriber above denies
> `CallToolRequest`. To hide write tools from unprivileged clients entirely, also
> filter `ListToolsRequest` by `checkToolAccess()`. Without it, write tools appear
> in `tools/list` but 403 on call — a leak of capability names. Same contract,
> ~20 extra lines.

## Generic policy (API key, role, allowlist)

Any scheme fits the same event. Minimal API-key gate:

```php
public function onRequest(RequestEvent $event): void {
  if (!$event->getRequest() instanceof CallToolRequest) {
    return;
  }
  $provided = $this->requestStack->getCurrentRequest()?->headers->get('X-Api-Key', '') ?? '';
  $expected = (string) $this->configFactory->get('my_module.settings')->get('api_key');
  if ($provided === '') {
    throw new McpAuthorizationDeniedException('authentication_required', 401);
  }
  if (!hash_equals($expected, $provided)) {
    throw new McpAuthorizationDeniedException('invalid_api_key', 403);
  }
}
```

## The `mcp_server_oauth` companion project

A separate project since 2026-06-09 (extracted from an in-tree submodule; no
tagged release yet): `composer require drupal/mcp_server_oauth`, then enable it
for OAuth2 scope enforcement (needs `simple_oauth` / `simple_oauth_21`).
When on, its `McpAuthorizeOAuthSubscriber`:

1. Subscribes to `RequestEvent`.
2. For each `CallToolRequest`, finds the matching `mcp_tool_config` entity and
   reads its third-party settings under `mcp_server_oauth`:
   `authentication_mode` (`disabled`|`required`) + `scopes[]`.
3. When `required`, validates the Bearer token's scopes — missing token → 401
   `authentication_required`; insufficient scopes → 403 `insufficient_scope`.
4. Appends `oauth2` to the `mcp_server.handle` route's `_auth` (so cookie-only
   core also accepts Bearer tokens).
5. Publishes scope metadata on the RFC 9728 endpoint (`simple_oauth_21`).

This keys off `mcp_tool_config` entities (the `drupal/tool` bridge), so it gates
**bridged** tools; static native plugins (like `echo`) without a backing config
are skipped. For native-plugin permission gating, use your own subscriber (above).
DKAN's `dkan_mcp_server` does not use this project — it ships its own scope
wiring on `simple_oauth_21` ([dkan-integration.md](dkan-integration.md)).

## Appending an auth provider to the route

Core's `mcp_server.handle` ships `_auth: ['cookie']`. Add providers via a
`RouteSubscriberBase::alterRoutes()` that augments the route's `_auth` option
(this is how `mcp_server_oauth` adds `oauth2`).

## CORS

Browser clients need CORS on the endpoint. In this module CORS is handled in-core
(compiler pass) rather than by a per-site response subscriber. If your browser
client fails preflight, verify the response exposes `Mcp-Session-Id` and allows
`Mcp-Protocol-Version`; if the in-core set is too narrow for your client, add a
thin response subscriber. (DKAN's `dkan_mcp_server` augments the in-core set via
a compiler pass, `McpCorsAuthHeaderPass`.)

## Sessions

HTTP sessions persist across requests via `SharedTempStoreSessionStore`
(`@mcp_server.shared_tempstore_session_store`), backed by `keyvalue.expirable`
(~1-week TTL, GC'd by cron). The client carries the `Mcp-Session-Id` header. stdio
is a single long-lived process — no session store needed.

## stdio per-call-denial wrinkle

`McpServerCommands::server()` catches `McpAuthorizationDeniedException`, writes a
JSON-RPC error, then **rethrows** — which kills the stdio run loop on a single
denied call (and output buffering can drop the error body). HTTP is clean
(per-request 403). Mitigation for stdio: run it as a privileged/trusted user so
denials don't fire, and rely on the HTTP layer for multi-client gating. (Known
upstream issue; verify whether your build has fixed it.)
