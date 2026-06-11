# Testing Drupal AI Plugins

How to test providers, FunctionCall tools, and agents. Two layers: deterministic PHPUnit unit tests for the glue you wrote, and non-deterministic eval runs for model behavior. Patterns below are grounded in `dkan_ai_query` (drupal.org project, 0.x — renamed 2026-06 from `dkan_drupal_ai_query`) and `dkan_query_tools`. Targets `drupal/ai ^1.3` + `ai_agents 1.2.x`.

## 1. The testing pyramid

The model is the one part you cannot make deterministic. Split testing along that line:

- **Unit tests (most of your tests)** — the deterministic glue: tool input parsing/validation, output shaping, error mapping, event subscribers, artifact transforms, eval scoring logic. Pure PHPUnit `TestCase`, mocked services, no LLM, no Drupal kernel. Fast and run in CI.
- **Eval runs (few, run on demand)** — non-deterministic model behavior: does the agent route to the right tool, land on the right dataset, refuse when it should. Scored as pass-rate over a golden set, not as a hard CI gate.

Rule: **never assert exact LLM strings in a unit test.** Mock the provider to return fixed output, or test below the model entirely. Assert on the model's free text only in eval, and only via regex/heuristics (see CaseEvaluator), never `assertSame`.

What goes where:

| Concern | Layer |
|---|---|
| Tool parses `conditions` JSON, clamps `limit`, maps DB errors | Unit |
| Subscriber captures the right artifact/tool-call | Unit |
| Eval scorer marks a case pass/fail | Unit |
| Agent picks `query_datastore` not `sample_rows` | Eval (`expected_tool_calls`) |
| Agent refuses an out-of-scope question | Eval (`expected_refusal`) |

## 2. Unit testing a FunctionCall tool

DKAN's query tools are plain service classes (`DatastoreTools`, `MetastoreTools`, `SearchTools`) wrapped by thin FunctionCall plugins. Test the **service class directly** — mock its injected dependencies, call the public method, assert on the returned array. No plugin manager, no context plumbing.

Pattern from `<webroot>/modules/custom/dkan_query_tools/tests/src/Unit/Tool/DatastoreToolsTest.php`:

```php
protected function createTools(?Query $query = NULL, /* ...other deps... */): DatastoreTools {
  $query = $query ?? $this->createMock(Query::class);
  // Default every dependency to a bare mock; override per test.
  return new DatastoreTools($datastore, $query, $metastore, $datasetInfo, $database, new NullLogger());
}

public function testQueryDatastoreBasic(): void {
  $queryResult = new RootedJsonData(json_encode(['results' => [['name' => 'Alice']], 'count' => 1]));
  $queryService = $this->createMock(Query::class);
  $queryService->method('runQuery')->willReturn($queryResult);

  $tools = $this->createTools(query: $queryService);
  $result = $tools->queryDatastore('test-resource');

  $this->assertEquals(1, $result['result_count']);
  $this->assertArrayNotHasKey('schema', $result);
}
```

Key techniques, all from real tests:

- **Assert the output shape, not prose** — `assertArrayHasKey`, `assertCount`, `assertEquals` on the returned array. Tool output is structured JSON-able data; that *is* deterministic and should be pinned hard.
- **Capture what the tool sent downstream** with `willReturnCallback`, then decode and assert. `testQueryDatastoreCanonicalizesColumnCase` captures the `DatastoreQuery` string passed to `runQuery` and asserts `properties`/`conditions`/`sorts` were canonicalized — verifying transform logic without a live datastore.
- **Test error mapping** — `willThrowException(new \Exception('SQLSTATE[42S22]... Unknown column ...'))` then assert the tool returns `['error' => 'unknown_column', 'column' => 'rate_per_100k', ...]`. The tool's job is turning raw exceptions into LLM-legible errors; that mapping is deterministic and high-value.
- **Test input validation** — bad JSON, wrong operators, alias conflicts, limit clamping (`limit: 9999` → `500`). These are guards you wrote; assert the friendly error text.
- **Assert a dependency is NOT called** with `expects($this->never())->method('get')` (see `testGetDatastoreSchemaNoDictionary`) to pin opt-out / short-circuit paths.

The mock `Query` returns a `RootedData\RootedJsonData` because that is the real return type — match real return types in mocks so the tool's parsing exercises real code, not a coincidentally-shaped array.

## 3. Asserting tool dispatch (collector/subscriber)

To verify *which tools an agent invoked* and *what it captured*, subscribe to `ai_agents` tool events. DKAN has two subscribers on `AgentToolFinishedExecutionEvent`:

- `ArtifactCaptureSubscriber` (`<webroot>/modules/custom/dkan_ai_query/src/EventSubscriber/ArtifactCaptureSubscriber.php`) — transforms tool output into UI artifacts (data tables, charts, aux panels, a debug `tool_call` snapshot).
- `ToolCallEvalCollectorSubscriber` (priority `-100`) — records every call into `EvalToolCallCollector`, keyed by thread/runner id, for eval scoring.

Unit-test a subscriber by constructing it directly and firing a real event with a **stub tool**. `FunctionCallStub` (`<webroot>/modules/custom/dkan_ai_query/tests/stubs/FunctionCallStub.php`) lives outside any namespace and implements only the surface subscribers touch: `getFunctionName()`, `getReadableOutput()`, `getContextValues()`.

```php
$tool = new \FunctionCallStub(
  'query_datastore',
  json_encode(['results' => [['a' => 1]], 'total_rows' => 1234]),
  ['resource_id' => 'rid__1', 'limit' => 3],
);
$subscriber->onToolFinished(new AgentToolFinishedExecutionEvent('thread-x', $tool));
```

For the **eval collector** (`ToolCallEvalCollectorSubscriberTest`), assert tool name, recorded input, output bytes, and iteration order:

```php
$calls = $this->collector->load('thread-1');
$this->assertSame('get_datastore_schema', $calls[0]['tool']);
$this->assertSame(['resource_id' => 'abc__v1'], $calls[0]['input']);
```

Notes from the real subscriber: in CLI eval runs `getThreadId()` is empty and the runner id carries the thread — the subscriber falls back to `getAgentRunnerId()`, and the test pins both paths (`testFallsBackToRunnerIdWhenThreadIdEmpty`). The collector is per-process in-memory; `EvalRunner` reads then `forget()`s after each case.

For the **artifact subscriber** (`ArtifactCaptureSubscriberTest`), mock `ArtifactStorage` and capture appended entries via `willReturnCallback`. Because every `onToolFinished` also writes a `tool_call` debug snapshot, filter by `$entry['type']` to isolate the artifact under test (`bindCaptureByType`). Assert error output is skipped (`testCaptureDataIgnoresErrorOutput`) and unrelated tools emit only the snapshot (`testNoDomainArtifactForUnrelatedTools`).

## 4. Golden-case eval harness

When unit tests can't help — you need to know whether the *model* does the right thing — use the golden-case harness in `<webroot>/modules/custom/dkan_ai_query/src/Eval/`. Define expected behavior in YAML, run each case through the real agent, score, report.

- **`GoldenCase`** (`GoldenCase.php`) — one immutable case loaded from a YAML row. Fields beyond `id`/`question`: `expectedDatasetId`, `expectedAnswerPattern` (regex), `forbiddenAnswerPattern`, `expectedRefusal`, `expectedRefusalCategory`, `expectedToolCalls`, `forbiddenToolCalls`, `expectedFailureCategory`. The YAML set lives at `tests/eval/golden_set.yml`.
- **`EvalRunner`** (`EvalRunner.php`) — runs cases through the live `dkan_data_query` agent, bypassing the HTTP controller. Per case: create provider + agent, prepend catalog context (mirrors production), `setAiConfiguration(['temperature' => 0])` for max determinism, `setProgressTracking(FALSE)` (no session under Drush), `determineSolvability()` then `solve()`. Flushes all caches between cases for clean state. Reads captured refusal + tool calls afterward.
- **`CaseEvaluator`** (`CaseEvaluator.php`) — pure, fully unit-tested scoring. Decides `[outcome, category]`. Prefers a structured `RefuseTool` payload, falls back to refusal regex heuristics. Checks `expectedAnswerPattern` as a case-insensitive regex (not exact match), then `checkToolCallExpectations()` for required/forbidden tools. **This is the deterministic core of eval and should have thorough unit tests** (`tests/src/Unit/Eval/CaseEvaluatorTest.php`).
- **`RunReporter`** (`RunReporter.php`) — writes `run-{label}.jsonl` (one decoded result per line, machine-diffable) and `run-{label}.md` (pass-rate, failures-by-category table). Runs land in `tests/eval/phase*/`. Compare runs with `tests/eval/scripts/compare-runs.py`.

Why pin tool calls in eval: `expected_tool_calls`/`forbidden_tool_calls` catch routing regressions a prompt edit might introduce (e.g. "first N rows" must use `query_datastore`, not `sample_rows`). The scorer fails these as `missing_required_tool` / `used_forbidden_tool`.

Treat eval as a tracked metric (pass-rate over time, per phase), not a binary CI gate — model output drifts and a single flaky case shouldn't fail the build.

## 5. Mocking ai.provider / ChatOutput

A provider's `chat()` returns a `ChatOutput` wrapping a `ChatMessage`. To mock the model in a test or local run, return a hand-built `ChatOutput`:

```php
use Drupal\ai\OperationType\Chat\ChatMessage;
use Drupal\ai\OperationType\Chat\ChatOutput;

$message = new ChatMessage('assistant', 'canned answer text');
$output = new ChatOutput($message, ['mock' => TRUE], []); // (normalized, rawOutput, metadata)
```

For a **tool-calling** turn, attach `ToolsFunctionOutput` objects to the message — the agent reads these to dispatch tools:

```php
$message = new ChatMessage('assistant', '');
$message->setTools([new ToolsFunctionOutput($functionInput, $callId, $args)]);
return new ChatOutput($message, ['mock' => TRUE], []);
```

The agent consumes output via `ChatOutput::getNormalized()`, which returns the `ChatMessage` (or a `StreamedChatMessageIteratorInterface` when streaming — don't stream in tests). `$message->getText()` is the answer; `$message->getTools()` is the tool calls.

DKAN ships a full mock provider rather than ad-hoc mocking for end-to-end runs: `dkan_ai_query_mock` (`<webroot>/modules/custom/dkan_ai_query/modules/dkan_ai_query_mock/`). Its `DkanAiqMockProvider` is a real `AiProvider` plugin (`getSupportedOperationTypes() => ['chat']`, capabilities `ChatTools` + `ChatSystemRole`) that replays scripted YAML scenarios (`scenarios/*.yml`: `match` block + ordered `turns` of `tool_calls`/`final_answer`). Real tools still execute against the datastore — only the LLM is replaced. Use it to exercise the full controller/polling/artifact UI without API cost or non-determinism.

Critical shape detail (from the mock's `chat()`): tool-call turns must put an array of `ToolsFunctionOutput` directly on the assistant `ChatMessage` via `setTools()`, matching `OpenAiProvider`. Wrapping them in a `ToolsOutput` (as `EchoProvider` does) crashes the agent in `FunctionCallPluginManager::convertToolResponseToObject()`.

## 6. Pitfalls

- **Asserting exact model strings** — `assertSame('The answer is 42', $answer)` is flaky by construction. Use regex/heuristics in eval (`expectedAnswerPattern: '22[,.\s]?008'`), and pin exact output only on deterministic tool results, never on LLM prose.
- **Live-model tests in CI** — slow, costly, rate-limited, non-deterministic. `EvalRunner` even sleeps between cases to dodge rate limits. Keep live-model runs out of CI; run them on demand and track pass-rate. For deterministic end-to-end coverage, use the mock provider submodule.
- **Forgetting `temperature => 0`** — eval sets it via `setAiConfiguration(['temperature' => 0])`. Without it, run-to-run variance swamps the signal you're measuring.
- **Stale state between cases** — `EvalRunner` flushes all caches and `forget()`s per-thread collectors between cases. A leaked tool-call or refusal record cross-contaminates the next case's score.
- **Stub return types drifting from reality** — mock `Query::runQuery` returns real `RootedJsonData`, mock storage returns the real schema shape. If a mock returns a plain array where the code expects a typed object, the test passes while production breaks. Match real return types.
- **Subscriber priority / double-capture** — `ToolCallEvalCollectorSubscriber` runs at `-100` so artifact/refusal subscribers (priority 0) have already mutated output before it measures size. Every `onToolFinished` writes a `tool_call` snapshot in addition to any domain artifact — filter by `type` in tests or you'll match the wrong entry.
- **Mock provider tool-output wrapping** — see §5; wrong wrapper class is a silent agent crash, not a clean failure.
