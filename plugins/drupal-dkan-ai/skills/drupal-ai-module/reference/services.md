# Drupal AI Module — Service Reference

Service IDs to inject when writing custom AI module code, with classes and key method signatures. Targets `drupal/ai ^1.3`.

## Plugin managers

| Service ID | Class | Key methods |
|---|---|---|
| `ai.provider` | `Drupal\ai\AiProviderPluginManager` | `createInstance($id)`, `hasProvidersForOperationType($op, $setup = TRUE)`, `getDefaultProviderForOperationType($op)`, `getSimpleProviderModelOptions($op)`, `loadProviderFromSimpleOption($value)` |
| `plugin.manager.ai.function_calls` | `Drupal\ai\Service\FunctionCalling\FunctionCallPluginManager` | `createInstance($id)`, `getDefinitions()`, `clearCachedDefinitions()` |
| `plugin.manager.ai_agents` | `Drupal\ai_agents\PluginManager\AiAgentManager` | `createInstance($id)` — then `setChatInput()` → `determineSolvability()` → `solve()` |
| `ai_assistant_api.action_plugin.manager` | `Drupal\ai_assistant_api\AiAssistantActionPluginManager` | `createInstance($id)`, `getDefinitions()`. Note the singular `ai_assistant_api` and the unconventional service ID (not `plugin.manager.*`). |
| `plugin.manager.ai_automator` | `Drupal\ai_automators\PluginManager\AiAutomatorTypeManager` | `createInstance($id)`, `getDefinitions()`. Service ID is `plugin.manager.ai_automator` (no `_type` suffix); class is `AiAutomatorTypeManager` (no `Plugin` infix). |
| `plugin.manager.ai_api_explorer` | `Drupal\ai_api_explorer\AiApiExplorerPluginManager` | `createInstance($id)`, `getDefinitions()` |

## Helpers

| Service ID | Class | Use for |
|---|---|---|
| `ai.form_helper` | `Drupal\ai\Service\AiProviderFormHelper` | Standardized provider/model selectors in config forms — `getAiProvidersOptions($op)` for a `<select>` source, `generateAiProvidersForm(...)` to render the selector subform, `generateAiProviderFromFormSubmit(...)` to resolve the submitted value into a configured provider instance. (To resolve a plain saved value, use `ai.provider`'s `loadProviderFromSimpleOption()`.) |
| `key.repository` | resolves to `Drupal\key\KeyRepository`; typehint as `Drupal\key\KeyRepositoryInterface` | Resolve API key references — `getKey($key_id)->getKeyValue()`. Always inject when a plugin uses an API key. **Never store raw keys** in config. |
| `logger.factory` | `LoggerChannelFactoryInterface` | Inject and call `->get('<channel_name>')` to obtain a `LoggerInterface`. **`logger.channel.ai` does NOT exist** as a registered service. Provider/agent base classes already inject this and expose `$this->loggerFactory`; custom services should follow the same pattern (e.g. `$this->loggerFactory->get('my_module')`). The `ai_logging` (now `ai_observability`) submodule subscribes to events to capture per-call data — no special channel needed. |
| `event_dispatcher` | `Symfony\Component\EventDispatcher\EventDispatcherInterface` | Dispatch/listen to `Drupal\ai\Event\PreGenerateResponseEvent`, `PostGenerateResponseEvent` |

## Typical DI patterns

### Provider plugin

**`AiProviderClientBase::__construct()` is `final`** — subclasses cannot override the constructor. The base injects 8 services (`http_client`, `config.factory`, `logger.factory`, `cache.default`, `key.repository`, `module_handler`, `event_dispatcher`, `file_system`); access them via the protected properties the base sets up:

- `$this->httpClient` (`Psr\Http\Client\ClientInterface`)
- `$this->configFactory` (`ConfigFactoryInterface`)
- `$this->loggerFactory` (`LoggerChannelFactoryInterface`) — call `$this->loggerFactory->get('<channel>')`
- `$this->cacheBackend` (`CacheBackendInterface`)
- `$this->keyRepository` (`KeyRepositoryInterface`)
- `$this->moduleHandler`, `$this->eventDispatcher`, `$this->fileSystem`

To add a custom service, declare a property with `@var` (Drupal phpcs requires it; PHP 8.2+ deprecates dynamic properties), override `create()` only, and assign on the parent instance:

```php
/**
 * The custom service.
 *
 * @var \Drupal\my_module\MyServiceInterface
 */
protected $myService;

/**
 * {@inheritdoc}
 */
public static function create(ContainerInterface $container, array $configuration, $plugin_id, $plugin_definition) {
  $instance = parent::create($container, $configuration, $plugin_id, $plugin_definition);
  $instance->myService = $container->get('my_module.my_service');
  return $instance;
}
```

### FunctionCall plugin

`FunctionCallBase`'s constructor takes 5 args: `(array $configuration, $plugin_id, $plugin_definition, ContextDefinitionNormalizer $context_definition_normalizer, ?AiDataTypeConverterPluginManager $data_type_converter_manager = NULL)`. Don't override the constructor for typical tools — the base's `create()` already wires both services. Most built-in tools (e.g. `HtmlToMarkdown` in `<webroot>/modules/contrib/ai/src/Plugin/AiFunctionCall/`) define neither.

To inject extra services, declare a property with `@var` (Drupal phpcs requires it; PHP 8.2+ deprecates dynamic properties), override `create()` only, and assign on the parent instance:

```php
/**
 * The custom service.
 *
 * @var \Drupal\my_module\MyServiceInterface
 */
protected $myService;

/**
 * {@inheritdoc}
 */
public static function create(ContainerInterface $container, array $configuration, $plugin_id, $plugin_definition): static {
  $instance = parent::create($container, $configuration, $plugin_id, $plugin_definition);
  $instance->myService = $container->get('my_module.my_service');
  return $instance;
}
```

`FunctionCallBase` uses `ContextAwarePluginTrait` — read inputs via `$this->getContextValue('arg_name')`, declared in the `#[FunctionCall(context_definitions: [...])]` attribute. Write output via `$this->setOutput($string)`. The base class also already implements `OverridableFunctionCallInterface` — don't redeclare it on subclasses. All FunctionCalling interfaces live in `Drupal\ai\Service\FunctionCalling\` (`FunctionCallInterface`, `ExecutableFunctionCallInterface`, `OverridableFunctionCallInterface`).

### Agent plugin

`AiAgentBase`'s constructor already takes 8 services (`AgentHelper`, `FileSystemInterface`, `ConfigFactoryInterface`, `AccountProxyInterface`, `ExtensionPathResolver`, `PromptJsonDecoderInterface`, `AiProviderPluginManager`, `EntityTypeManagerInterface`). **Do not redefine the constructor** unless you add new services — and if you do, you must accept all 8 base services and pass them to `parent::__construct()`. Easier pattern: extend `create()` only, and attach additional services to the parent instance.

```php
/**
 * The extra service.
 *
 * @var \Drupal\my_module\MyServiceInterface
 */
protected $myExtraService;

/**
 * {@inheritdoc}
 */
public static function create(ContainerInterface $container, array $configuration, $plugin_id, $plugin_definition) {
  $parent_instance = parent::create($container, $configuration, $plugin_id, $plugin_definition);
  $parent_instance->myExtraService = $container->get('my_module.my_service');
  return $parent_instance;
}
```

The base class exposes these helpers for the `solve()` and `determineSolvability()` implementations:

- `$this->aiProvider` — provider instance (set by base from default `chat_with_complex_json` provider)
- `$this->modelName` — model ID
- `$this->getChatInput()` / `$this->setChatInput(ChatInput $input)` — conversation state
- `$this->runAiProvider($prompt, $images = [], $strip_tags = TRUE, $promptFile = '')` — single LLM call
- `$this->runSubAgent($file, array $userContext, $module, $subDirectory, $promptType = 'yaml', $outputType = 'json')` — load a YAML prompt and call the LLM with structured-output decoding
- `$this->actionYamlPrompts($type, array $userPrompts, $module, $subDirectory = '')` — drive a multi-step YAML prompt sequence
- `$this->getStructuredOutput()` — return the agent's `StructuredResultData` for the orchestrator

Typical `solve()` shape:

1. Read the task: `$task = $this->getTask()`; `$input = $this->getChatInput()`
2. Run a YAML prompt: `$result = $this->runSubAgent('determineFoo.yml', $context, 'my_module', '<plugin_id>')`
3. Branch on `$result` — call additional prompts, mutate Drupal state, etc.
4. Return a string summary

Agents are routed by the orchestration framework based on `agentsCapabilities()` — they are not driven by an LLM tool-calling loop the way `FunctionCall` plugins are.

## Events

| Event class | When dispatched | Use for |
|---|---|---|
| `Drupal\ai\Event\PreGenerateResponseEvent` | Before any provider call | Modify `ChatInput`, log request, inject context |
| `Drupal\ai\Event\PostGenerateResponseEvent` | After any provider call | Inspect/modify `ChatOutput`, log response, audit |

Subscribe via tagged service in `*.services.yml`:

```yaml
my_module.ai_audit:
  class: Drupal\my_module\EventSubscriber\AiAuditSubscriber
  tags:
    - { name: event_subscriber }
```

## Version notes

- AI Assistant API plugin manager service ID is `ai_assistant_api.action_plugin.manager` (the module is `ai_assistant_api`, singular).
- For logging, use `logger.factory` and call `->get('<channel>')`. The `logger.channel.ai` service is not registered.
- Current-version facts and the 2.0.x stance live in [SKILL.md](../SKILL.md) rule 3 — deliberately not restated here.
- `PreGenerateResponseEvent` and `PostGenerateResponseEvent` (in `Drupal\ai\Event\`) are stable in 1.x — verified at `<webroot>/modules/contrib/ai/src/Event/`.
