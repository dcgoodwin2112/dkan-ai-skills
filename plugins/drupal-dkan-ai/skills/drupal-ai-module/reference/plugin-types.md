# Drupal AI Plugin Types — Reference

Class FQNs, attributes, required methods, and example paths for each plugin type the Drupal AI ecosystem exposes. Targets `drupal/ai ^1.3`. Sourced from upstream module code; verify against the installed version before code-gen.

## AI Provider

Adds a new LLM backend (Anthropic, OpenAI, Ollama, internal API).

### Two base classes — pick the right one

| Use case | Base class | Why |
|---|---|---|
| API is OpenAI-compatible (most modern LLMs: Anthropic, Mistral, Groq, Together, OpenRouter, Ollama, Llama-via-cloud) | **`Drupal\ai\Base\OpenAiBasedProviderClientBase`** | Already implements `ChatInterface`, `ModerationInterface`, `EmbeddingsInterface`, `TextToSpeechInterface`, `SpeechToTextInterface`, `TextToImageInterface`. Provides default `isUsable()`, `setAuthentication()`, `loadClient()`, and operation methods. You typically only override `getConfiguredModels()`, `getSupportedOperationTypes()`, `getModelSettings()`, `getSetupData()`, and the `$endpoint` property. |
| Fully custom API (Cohere direct, Gemini direct, internal proprietary) | **`Drupal\ai\Base\AiProviderClientBase`** | Bare base — only `getModelSettings()` is abstract, but you must also implement `isUsable()`, `setAuthentication()`, `getSupportedOperationTypes()`, and any operation methods (e.g. `chat()`) yourself. Use the operation traits (`ChatTrait`, `EmbeddingsTrait`) from `Drupal\ai\Traits\OperationType\*` to reduce boilerplate. |

### Common to both

- **Attribute**: `#[AiProvider(id: 'foo', label: new TranslatableMarkup('Foo'))]` — class `Drupal\ai\Attribute\AiProvider`. Fields: `id`, `label`, optional `deriver`. **No `description` and no `module_dependencies` field** (unlike `#[AiAgent]` and `#[FunctionCall]`, which both take `module_dependencies`).
- **Path**: `src/Plugin/AiProvider/FooProvider.php`
- **Constructor is FINAL** on `AiProviderClientBase` — **cannot be overridden by subclasses**. Take the 8 services it injects (`http_client`, `config.factory`, `logger.factory`, `cache.default`, `key.repository`, `module_handler`, `event_dispatcher`, `file_system`) and trust them. To add custom services, override `create()` and use setter injection on the parent instance.
- **Required to implement (interface contract):**
  - `getModelSettings(string $model_id, array $generalConfig = []): array` — abstract on the base
  - `getSupportedOperationTypes(): array` — declared on `AiProviderInterface`
  - `isUsable(?string $operation_type = NULL, array $capabilities = []): bool` — declared on interface; OpenAI base provides default
  - `setAuthentication(mixed $authentication): void` — declared on interface; OpenAI base provides default
  - One operation method per declared interface: `chat()`, `embeddings()`, `textToImage()`, `moderation()`, `speechToText()`, `textToSpeech()`, `imageClassification()`, `audioToAudio()` — OpenAI base provides defaults for all six it implements; on `AiProviderClientBase` you must write them or use traits
- **Optional / commonly overridden:**
  - `getConfiguredModels(?string $operation_type = NULL, array $capabilities = []): array` — base default returns empty; override for dynamic model lists or capability filtering
  - `getSetupData(): array` — return `key_config_name`, `default_models[<operation>]` for the post-install setup wizard
  - `getApiDefinition(): array` — base loads `definitions/api_defaults.yml` automatically; override only if you need custom location

### Operation interfaces (declare one or more on your class — OpenAI base already declares all six)

`Drupal\ai\OperationType\Chat\ChatInterface`, `Drupal\ai\OperationType\Embeddings\EmbeddingsInterface`, `Drupal\ai\OperationType\TextToImage\TextToImageInterface`, `Drupal\ai\OperationType\TextToSpeech\TextToSpeechInterface`, `Drupal\ai\OperationType\SpeechToText\SpeechToTextInterface`, `Drupal\ai\OperationType\Moderation\ModerationInterface`, `Drupal\ai\OperationType\ImageClassification\ImageClassificationInterface`, `Drupal\ai\OperationType\AudioToAudio\AudioToAudioInterface`.

### `definitions/api_defaults.yml` schema

**Keyed by operation type, NOT by `models`.** Each operation type entry has `input`, `authentication`, and `configuration` sub-keys. Example (chat):

```yaml
chat:
  input:
    description: 'Input provided to the model.'
    type: 'array'
    default:
      - { role: "system", content: "You are a helpful assistant." }
      - { role: "user", content: "Introduce yourself!" }
    required: true
  authentication:
    description: 'API Key.'
    type: 'string'
    default: ''
    required: true
  configuration:
    max_tokens:
      label: 'Max Tokens'
      type: 'integer'
      default: 4096
      required: false
    temperature:
      label: 'Temperature'
      type: 'float'
      default: ''
      required: false
      constraints: { min: 0, max: 1, step: 0.1 }
```

Add one top-level key per operation your provider supports. **Capabilities are NOT declared in this YAML.** Strings like `chat_with_image_vision` and `chat_with_complex_json` are *pseudo operation types* (see the Pseudo Operation Types section below) — declared upstream in `Drupal\ai\Utility\PseudoOperationTypes` and used as keys in `getSetupData()['default_models']`. The underlying capabilities they filter for live in the `Drupal\ai\Enum\AiModelCapability` enum (`ChatWithImageVision`, `ChatJsonOutput`, etc.) and are reported via `getSupportedCapabilities()` and per-model filtering in `getConfiguredModels()`.

### Companion files

- Settings form (`ConfigFormBase`) at `src/Form/<Provider>ConfigForm.php`
- Route under `/admin/config/ai/providers/<plugin_id>` with `_permission: 'administer ai providers'`
- Config schema at `config/schema/<module_name>.schema.yml`
- Default config at `config/install/<module_name>.settings.yml` — only Key entity references, never raw secrets
- `definitions/api_defaults.yml` (per schema above)

### Reference implementations

- [ai_provider_openai](https://www.drupal.org/project/ai_provider_openai) — canonical OpenAI base extension
- [ai_provider_anthropic](https://www.drupal.org/project/ai_provider_anthropic) — also extends OpenAI base (Anthropic's API is OpenAI-compatible). Project ships in `<webroot>/modules/contrib/ai_provider_anthropic/`

## FunctionCall (Tool)

Gives an AI agent a custom action (CRUD an entity, hit an internal API, format data).

- **Base class**: `Drupal\ai\Base\FunctionCallBase` — already implements `OverridableFunctionCallInterface`, provides `getReadableOutput()` / `setOutput()`, uses `ContextAwarePluginTrait`
- **Interfaces** (all in `Drupal\ai\Service\FunctionCalling\`):
  - `FunctionCallInterface` — base contract (extended by the base class)
  - `ExecutableFunctionCallInterface` — declare on the plugin if `execute()` runs server-side (most tools)
  - `OverridableFunctionCallInterface` — already implemented by `FunctionCallBase`; do not redeclare
- **Attribute**: `#[FunctionCall(id: '<module>:<name>', function_name: '<name>', name: 'My Tool', description: '…', group: 'utility', context_definitions: [...])]` — class `Drupal\ai\Attribute\FunctionCall`. ID convention is `<module>:<snake_case_name>` (e.g. `ai_agent:html_to_markdown`); `function_name` is what the LLM sees.
- **Path**: `src/Plugin/AiFunctionCall/MyTool.php` — note **PascalCase singular `AiFunctionCall`**, not `AiFunctionCalls`
- **ContextDefinition syntax**: named arguments — `new ContextDefinition(data_type: 'string', label: new TranslatableMarkup('Label'), description: new TranslatableMarkup('…'), required: TRUE)`
- **Required methods**:
  - `execute()` — perform the action; read inputs via `$this->getContextValue('arg_name')`, write output via `$this->setOutput($string)`. The base class returns `setOutput()` from `getReadableOutput()` automatically; only override `getReadableOutput()` if you need custom formatting.
- **Plugin manager**: `plugin.manager.ai.function_calls`
- **Reference implementations**:
  - `ai_agents` built-in tools: `modules/ai_agents/src/Plugin/AiFunctionCall/`
  - [ai_agents_experimental_collection](https://www.drupal.org/project/ai_agents_experimental_collection) Scratchboards: `ListScratchboards`, `LoadScratchboard`, `SaveScratchboard`, `ExtractScratchboard`

## AI Agent

Autonomous worker that runs a sequence of LLM-driven steps to fulfill a goal — typically a "determine → solve" flow with structured output. **Significantly different from the OpenAI-style "agent calls tools in a loop" pattern**: ai_agents agents drive the LLM via per-operation YAML prompts, not function-calling tool dispatch.

- **Base class**: `Drupal\ai_agents\PluginBase\AiAgentBase` (for code-defined agents) — already implements `AiAgentInterface`. The base constructor takes 8 services; do not redefine the constructor unless adding more services. Use `parent::create()` then attach extras (see DI pattern in [services.md](services.md)).
- **Interface**: `Drupal\ai_agents\PluginInterfaces\AiAgentInterface` (already implemented by base)
- **Attribute**: `#[AiAgent(id: 'my_agent', label: new TranslatableMarkup('My Agent'), module_dependencies: [])]` — class `Drupal\ai_agents\Attribute\AiAgent`. Fields: `id`, `label`, optional `deriver`, optional `module_dependencies`. **There is NO `description` field on the attribute** — describe the agent in `agentsCapabilities()` instead.
- **Plugin ID rule**: due to a known bug, the plugin ID must either equal its "group" or be prefixed with `<group>:`. In practice, use a single underscore-cased ID (e.g. `field_type_agent`).
- **Path**: `src/Plugin/AiAgent/MyAgent.php` (class name typically does NOT include "Agent" suffix — see built-ins `FieldType.php`, `ContentType.php`, `TaxonomyAgent.php`)
- **Required methods to override** (the base class declares everything but leaves these abstract):
  - `getId(): string` — return the plugin ID. Base's `getId()` is implemented but most agents override to hard-code the ID for clarity.
  - `agentsNames(): array` — array of human-readable names. **Abstract in base — must implement.**
  - `answerQuestion()` — interactive Q&A handler. **Abstract in base — must implement.** Return a string; if the agent isn't interactive, return a placeholder like `'Not interactive.'`.
  - `agentsCapabilities(): array` — keyed by plugin ID; each entry has `name`, `description`, `usage_instructions`, `inputs[]` (each: `name`, `type`, `description`, `default_value`, `required`), `outputs[]` (each: `description`, `type`). This is what the orchestration framework reads to route tasks to your agent. Base provides a stub but always override for real agents.
  - `determineSolvability(): int` — return one of the JOB constants on `AiAgentInterface`: `JOB_NOT_SOLVABLE = 0`, `JOB_SOLVABLE = 1`, `JOB_NEEDS_ANSWERS = 2`, `JOB_SHOULD_ANSWER_QUESTION = 3`, `JOB_INFORMS = 4`. **No `JOB_NEEDS_MORE_INFO`** — common AI hallucination.
  - `solve()` — main work; typically calls `$this->runAiProvider($prompt, $images, $strip_tags, $promptFile)` or `$this->runSubAgent($file, $context, $module, $subDirectory)` from the base class. Return type undeclared; convention is `string`.
- **Prompts**: per-operation YAML files at `prompts/<plugin_id>/<operationName>.yml` — **NOT** `system.txt`/`task.txt`. Each YAML file is a structured prompt with placeholders the framework fills in. See `<webroot>/modules/contrib/ai_agents/prompts/field_type_agent/` for examples (e.g. `determineFieldTask.yml`, `answerQuestion.yml`). Loaded by `actionYamlPrompts()` and `runSubAgent()`.
- **Plugin manager**: `plugin.manager.ai_agents` (class `Drupal\ai_agents\PluginManager\AiAgentManager`)
- **Reference implementations**: `ai_agents` built-ins — `FieldType` (id `field_type_agent`), `ContentType` (id `node_content_type_agent`), `TaxonomyAgent` (id `taxonomy_agent`) under `<webroot>/modules/contrib/ai_agents/src/Plugin/AiAgent/`

## Assistant Action

A capability the AI Assistant API can invoke as part of a chat session — performs a Drupal action, returns context, or both. Module ships with `drupal/ai`.

- **Module name**: `ai_assistant_api` (singular — the project's machine name, despite the human-readable name "AI Assistant API")
- **Base class**: `Drupal\ai_assistant_api\Base\AiAssistantActionBase`
- **Interface**: `Drupal\ai_assistant_api\AiAssistantActionInterface` (top-level, not in `PluginInterfaces/`)
- **Attribute**: `#[AiAssistantAction(id: 'rag_action', label: new TranslatableMarkup('RAG'))]` — class `Drupal\ai_assistant_api\Attribute\AiAssistantAction`. Fields: `id`, `label`, optional `deriver`. **No `description` field.**
- **Plugin ID rule**: same group/prefix bug as `AiAgent` — use a single underscore-cased ID.
- **Path**: `src/Plugin/AiAssistantAction/RagAction.php`
- **Base constructor**: `(array $configuration, PrivateTempStoreFactory $tempStoreFactory)`. Subclasses can extend with extra services — call `parent::__construct($configuration, $tmpStore)`.
- **Required methods to override**:
  - `listActions(): array` — array of action descriptors with `id`, `label`, `description`. The LLM sees these to choose which action to invoke.
  - `listContexts(): array` — context items the action can return back to the assistant
  - `triggerAction(string $action_id, array $parameters = []): void` — actually do the work; called when the LLM picks one of `listActions()`. Read parameters, perform the action, optionally store context via `$this->setOutputContext($key, $context)` or `$this->storeActionContext($key, $data)`.
  - `provideFewShotLearningExample(): array` — examples of when to invoke; appended to the assistant's system prompt
  - **Form methods from `PluginFormInterface` / `ConfigurableInterface`** (the interface extends both, base does NOT implement): `defaultConfiguration()`, `buildConfigurationForm()`, `validateConfigurationForm()`, `submitConfigurationForm()`. Empty bodies are fine for actions without settings.
- **Optional overrides** (base provides usable defaults):
  - `listUsageInstructions(): array` — extra system-prompt hints (default `[]`)
  - `triggerRollback(): void` — undo the action if reversible (default no-op)
  - `getFunctionCallSchema(): array` — base provides default `{action, query}` schema; override to declare actual parameters
- **Plugin manager service**: `ai_assistant_api.action_plugin.manager` (NOT `plugin.manager.ai_assistant_action`)
- **Reference implementation**: `<webroot>/modules/contrib/ai/modules/ai_search/src/Plugin/AiAssistantAction/RagAction.php`

## Automator Type

Auto-populates a custom field from an LLM prompt.

- **Base class**: `Drupal\ai_automators\PluginBaseClasses\RuleBase`
- **Interface**: `Drupal\ai_automators\PluginInterfaces\AiAutomatorTypeInterface`
- **Attribute**: `#[AiAutomatorType(id: 'llm_string', label: ..., field_rule: 'string', target: '')]`
- **Path**: `src/Plugin/AiAutomatorType/LlmString.php`
- **Plugin manager**: `plugin.manager.ai_automator` (class `Drupal\ai_automators\PluginManager\AiAutomatorTypeManager` — note the service ID has no `_type` suffix and the class has no `Plugin` infix)

## Vector DB Provider

New backend for AI Search (Milvus, Pinecone, Qdrant, etc.).

- **Attribute**: `#[VdbProvider(id: 'milvus', label: ...)]`
- **Path**: `src/Plugin/VdbProvider/MilvusProvider.php`
- **Module**: `ai_search`

## API Explorer Plugin

Adds a tab to the AI API Explorer admin UI for testing a custom operation.

- **Attribute**: `#[AiApiExplorer(id: 'chat_explorer', label: ...)]`
- **Path**: `src/Plugin/AiApiExplorer/ChatExplorer.php`
- **Module**: `ai_api_explorer`

## Operation Type

A new kind of AI operation (e.g. "rerank") — **not** a classic plugin. Add it as PHP interfaces and DTOs.

- Create `Drupal\ai\OperationType\<OpName>\<OpName>Interface`
- Create `Drupal\ai\OperationType\<OpName>\<OpName>Input` and `<OpName>Output` DTOs
- Providers opt in by implementing the interface and listing the op string in `getSupportedOperationTypes()`
- No plugin manager needed; discovery is via providers implementing the interface
- An operation-type generator may exist in upstream issues; check the tracker if you need scaffolding help.

## Pseudo Operation Types

A routing layer: a "pseudo op" string like `chat_with_complex_json` resolves to a real op type plus a capability filter. Defined statically in `Drupal\ai\Utility\PseudoOperationTypes::getDefaultPseudoOperationTypes()`.

Built-in pseudo ops (all map to `chat` + a capability):

| Pseudo op ID | Actual op | Required capability |
|---|---|---|
| `chat_with_image_vision` | `chat` | `AiModelCapability::ChatWithImageVision` |
| `chat_with_complex_json` | `chat` | `AiModelCapability::ChatJsonOutput` |
| `chat_with_structured_response` | `chat` | `AiModelCapability::ChatStructuredResponse` |
| `chat_with_tools` | `chat` | `AiModelCapability::ChatTools` |

These IDs show up in two places provider authors care about:
1. **`getSetupData()`** — `default_models[<pseudo_op_id>] = <model_id>` tells the setup wizard which model to use when a caller asks for that pseudo op (see `AnthropicProvider::getSetupData()`).
2. **Capability filtering** — when something calls `$aiProvider->getConfiguredModels('chat', [AiModelCapability::ChatJsonOutput])`, your provider should filter to only models that satisfy the capability.

Capabilities themselves are NOT declared in `api_defaults.yml`. They're reported via `getSupportedCapabilities()` (provider-wide, optional override) and per-model via the filtering logic in `getConfiguredModels()` (see Anthropic's regex-on-model-id pattern).
