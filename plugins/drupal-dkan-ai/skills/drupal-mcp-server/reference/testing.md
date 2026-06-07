# Testing MCP Server Plugins

## Principle: test your module, not the framework

From the module's own testing philosophy: **if a test would pass or fail
regardless of your code, it's testing the framework.** Don't test attribute
discovery, plugin-manager wiring, SDK dispatch, or `ToolPluginBase` accessors —
those are upstream's. Test the behavior **you** wrote: argument
validation/normalization, the service call, response shaping, error handling, and
your access policy.

This keeps the plugin layer thin enough that exhaustive per-plugin tests aren't
needed — if a `#[Tool]` plugin only adapts arguments and delegates, test the
delegate (the logic class) directly and the plugin lightly.

## Unit test a tool plugin's logic

The high-value target is `execute()`'s argument handling and return shape. Mock
injected services; instantiate the plugin directly; assert on the structured
return.

```php
// Construct with ([], 'id', $definition, $currentUser) or via create() with a
// mocked container; set the injected service to a mock, then:
$result = $plugin->execute(['message' => 'hi', 'prefix' => 'x'], $gatewayMock);
$this->assertSame(['echo' => 'x: hi'], $result['data']);
```

Assert the three things you own:
- **Validation/normalization** — clamping, defaults, bad input → structured error.
- **Delegation** — the injected service is called with the mapped arguments.
- **Error handling** — a thrown service exception becomes a returned error, not an
  uncaught throw (which can abort the stdio loop).

When the logic lives in a separate class (the DKAN pattern — `HarvestTools`,
`dkan_query_tools.*`), unit-test **that class** with mocked DKAN services; the
plugin wrapper needs only a smoke test.

## Standalone stubs (no Drupal bootstrap)

DKAN's `dkan_mcp` tests run on the site-level PHPUnit with **standalone stubs** —
minimal local implementations of DKAN/Drupal classes (`tests/stubs/*.php`) loaded
via `tests/bootstrap.php`, so logic tests need no running site or DB. Mirror this
when your tool delegates to heavy services: stub the service's contract, assert
your adapter calls it correctly. Fast, hermetic, and unaffected by the
hand-rolled-vs-`mcp_server` migration (the logic classes don't change).

## Kernel test the integration (sparingly)

One kernel test enabling `mcp_server` + your module is enough to prove wiring:

- `tools/list` includes your tool ID with its schema/annotations.
- One read tool returns the expected structured output.
- One denied write returns 403 (proves your `RequestEvent` subscriber fires) —
  see [auth-and-access.md](auth-and-access.md).

Don't reproduce this per tool. Keep expensive (kernel/functional) setup minimal:
the module caps to one Functional + one FunctionalJavaScript class, one test
method each, with helper methods inside.

## Access subscriber test

If you ship a `ToolAccessSubscriber`, unit-test the three cases directly: denies
an anonymous user on a write tool, allows a permission holder, and leaves reads
open. This is the security-critical seam — `checkAccess()` is inert without it.

## Tool-permission contract test (regression guard)

The access-subscriber test proves the gate works *today*; a contract test proves no
*future* tool quietly slips it. Snapshot the tool surface and fail the build when it
drifts toward more agency:

- Enumerate `plugin.manager.mcp_server.tool` definitions; for each, record whether
  it is write/destructive and whether it is gated (declares a non-default access
  policy the `ToolAccessSubscriber` enforces).
- Assert the invariant: **every write/destructive tool is gated.** A new `delete_*`
  / `drop_*` / `unpublish` tool added without a gate fails the suite, not production
  (OWASP LLM06 excessive agency).
- Keep a committed snapshot of the read-only vs read-write split; a diff — a read
  tool gaining a write path, or a required permission changing — is a review signal,
  not a silent change (the rug-pull guard).

Same "go red the moment the contract changes" goal as an upstream contract test,
applied to *authorization*.

## Commands

```bash
# Contrib module's own suite (run from the Drupal root):
vendor/bin/phpunit <webroot>/modules/contrib/mcp_server/tests/

# A custom module with standalone stubs (DKAN dkan_mcp style):
cd <webroot>/modules/custom/<module> && ../../../../vendor/bin/phpunit

vendor/bin/phpcs --standard=Drupal,DrupalPractice <webroot>/modules/custom/<module>/
```

The `/validate-module` command runs phpcs + phpunit + a permission audit + cache
rebuild over a module.
