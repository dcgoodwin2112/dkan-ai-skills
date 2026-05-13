# Drupal AI Module — Common Pitfalls

Failure modes when extending the Drupal AI module, with symptoms and fixes. Targets `drupal/ai ^1.3` (verified against 1.3.3 + `ai_agents` 1.2.3 + `ai_provider_anthropic` 1.2.2). Order is rough frequency.

## 1. Forgot to rebuild cache

- **Symptom**: New provider/tool/agent doesn't appear at `/admin/config/ai/...` or in plugin discovery.
- **Cause**: Plugin attribute discovery is cached. New plugins aren't picked up until cache rebuild.
- **Fix**: `drush cr`. The scaffold commands do this automatically; if writing by hand, run it after every new plugin file.

## 2. Key module not enabled

- **Symptom**: Provider's `setAuthentication()` silently fails. All API calls return empty.
- **Cause**: `\Drupal::service('key.repository')->getKey($id)` returns null when the Key module is missing.
- **Fix**: `drush en key`. Add `key:key` to the module's `*.info.yml` dependencies.

## 3. supportedOperationTypes ↔ implemented interface mismatch

- **Symptom**: Provider visible in the list, but `hasProvidersForOperationType('chat')` returns false. Provider is invisible to the framework.
- **Cause**: Implementing `ChatInterface` without listing `'chat'` in `getSupportedOperationTypes()` — or the reverse.
- **Fix**: Make sure every operation interface implemented is also listed in `getSupportedOperationTypes()`, and every operation listed is backed by an implemented interface (or by the `OpenAiBasedProviderClientBase` which declares all six).

## 4. API keys leaking via config export

- **Symptom**: Secrets in `config/install/*.settings.yml` get committed to git.
- **Cause**: Storing raw key values in default config.
- **Fix**: Use Key entity references only — `api_key: my_anthropic_key` (the ID of a Key entity), not `api_key: sk-ant-...`. Document that the user must create the Key entity post-install.

## 5. Plugin directory casing

- **Symptom**: FunctionCall tool exists but isn't discovered.
- **Cause**: Directory named `src/Plugin/AiFunctionCalls/` (plural) instead of `src/Plugin/AiFunctionCall/` (singular).
- **Fix**: Use the exact PascalCase singular name. Discovery is case-sensitive on case-sensitive filesystems and silent on failure.

## 6. Capabilities are an enum, not YAML metadata

- **Symptom**: Setting `capabilities: { chat_with_image_vision: true }` somewhere in `definitions/api_defaults.yml` has no effect; vision calls don't route to your provider.
- **Cause**: Capabilities aren't declared in `api_defaults.yml` at all. The real mechanism is the `Drupal\ai\Enum\AiModelCapability` enum (cases like `ChatWithImageVision`, `ChatWithAudio`, `ChatJsonOutput`, `ChatTools`, `ChatStructuredResponse`) plus three provider methods: `getSupportedCapabilities()` (provider-wide), `getConfiguredModels(?op, $capabilities)` (filter by per-model capability — see Anthropic's regex pattern), and `modelSupportsCapabilities($op, $model_id, $caps)` (per-model check).
- **Fix**: Override `getConfiguredModels()` to filter the model list by the `$capabilities` arg, the way `AnthropicProvider` does (`web/modules/contrib/ai_provider_anthropic/src/Plugin/AiProvider/AnthropicProvider.php`). For provider-wide capabilities, override `getSupportedCapabilities()`.

## 7. Streaming response consumed mid-flight

- **Symptom**: Streamed chat output is truncated or empty on the consumer side.
- **Cause**: When `streamedOutput(TRUE)` is set, `ChatOutput::getNormalized()` returns a `StreamedChatMessageIteratorInterface` (an `IteratorAggregate`). Iterating it once consumes the stream.
- **Fix**: Decide up front whether the consumer handles iterators. For non-streaming consumers, leave `streamedOutput()` off and call `getNormalized()` once after the call returns. For streaming consumers, foreach the iterator in the consumer code, not in the provider.

## 8. `OverridableFunctionCallInterface` redeclared on subclass

- **Symptom**: phpcs warning or developer confusion; no functional impact.
- **Cause**: `FunctionCallBase` already implements `OverridableFunctionCallInterface` (verified at line 22 of `web/modules/contrib/ai/src/Base/FunctionCallBase.php`). Subclasses that redeclare it are redundant.
- **Fix**: Only declare `ExecutableFunctionCallInterface` on FunctionCall plugins. The override interface is inherited.

## 9. Agent prompts in wrong format or directory

- **Symptom**: Agent runs but `runSubAgent('foo.yml', ...)` errors with "file not found", or the agent skips a YAML prompt step.
- **Cause**: ai_agents uses **per-operation YAML files** in `prompts/<plugin_id>/`, not `system.txt` + `task.txt`. Each call to `runSubAgent($file, $context, $module, $subDirectory)` loads a single `.yml` file from `<module>/prompts/<subDirectory>/<file>`. Misnamed dirs (`MyAgent/` instead of `my_agent/`) or wrong extensions (`.txt` instead of `.yml`) cause silent fallback or hard errors.
- **Fix**: Verify against `web/modules/contrib/ai_agents/prompts/field_type_agent/` (e.g. `determineFieldTask.yml`, `answerQuestion.yml`). Plugin ID and directory name must match exactly, lowercased and underscored. File extension is `.yml`.

## 10. 1.x vs 2.x branch confusion

- **Symptom**: Code references methods/events that don't exist (e.g. `ProviderSetupEvent`, `ProviderDisabledEvent`).
- **Cause**: Following a 2.0.x guide while installed on stable 1.3.x. 2.0.x has breaking provider lifecycle changes (per upstream issue tracker).
- **Fix**: Pin to `^1.3` in module info. Use the 1.3.x docs at https://project.pages.drupalcode.org/ai/1.3.x/. Do not use `^2.0` until it stabilizes.

## 11. 1.2.x → 1.3.x API key revalidation

- **Symptom**: After upgrading from 1.2.x to 1.3.0, providers fail authentication despite saved keys.
- **Cause**: API key validation was rewritten between 1.2.x and 1.3.x — saved keys may need re-saving.
- **Fix**: Re-save API keys in the provider's settings form post-upgrade. Verify against the upstream issue tracker if symptoms persist.

## 12. `logger.channel.ai` does not exist as a registered service

- **Symptom**: `Symfony\...\ServiceNotFoundException: You have requested a non-existent service "logger.channel.ai"` when injecting it into a custom service.
- **Cause**: `drupal/ai 1.3.3` does not declare a `logger.channel.ai` service. Provider classes use `$this->loggerFactory->get('<module_name>')` (e.g. Anthropic uses `$this->loggerFactory->get('ai_provider_anthropic')`), where `$this->loggerFactory` is the `LoggerChannelFactoryInterface` injected by `AiProviderClientBase`'s constructor.
- **Fix**: Inject `logger.factory` (`LoggerChannelFactoryInterface`) and call `->get('<your_channel>')` to get a per-module channel. For provider/agent/action classes that extend an AI base class, use the inherited factory via `$this->loggerFactory->get(...)` (provider) or a similar pattern.

## 13. Provider in installer-paths but not enabled

- **Symptom**: Module is in `web/modules/contrib/ai_provider_foo/` but `\Drupal::service('ai.provider')->createInstance('foo')` fails with `PluginNotFoundException`.
- **Cause**: Module not enabled. `composer require` installs it; `drush en` enables it.
- **Fix**: `drush en ai_provider_foo`. Then `drush cr`.

## 14. `AiProviderClientBase::__construct()` is final

- **Symptom**: PHP fatal: `Cannot override final method Drupal\ai\Base\AiProviderClientBase::__construct()`.
- **Cause**: The base constructor is declared `final`. Subclasses cannot define their own constructor.
- **Fix**: To add custom services, override `create()` only and assign to public/protected properties on the parent instance after `parent::create()`. The 8 services the base injects are accessible via `$this->httpClient`, `$this->configFactory`, `$this->loggerFactory`, `$this->cacheBackend`, `$this->keyRepository`, `$this->moduleHandler`, `$this->eventDispatcher`, `$this->fileSystem`.

## 15. AiAgentBase missing-method fatals

- **Symptom**: `Class … contains 1 abstract method and must therefore be declared abstract or implement the remaining methods (Drupal\ai_agents\PluginInterfaces\AiAgentInterface::answerQuestion)`.
- **Cause**: `AiAgentBase` does NOT implement `agentsNames()` and `answerQuestion()` even though it declares `implements AiAgentInterface`. Both are abstract — the base class lies about its completeness.
- **Fix**: Always implement `agentsNames()` and `answerQuestion()` on custom agent classes. Empty/placeholder bodies are fine if the agent isn't interactive.

## 16. AiAssistantActionBase missing form-method fatals

- **Symptom**: `Class … contains 4 abstract methods … (PluginFormInterface::buildConfigurationForm, validateConfigurationForm, submitConfigurationForm, …)`.
- **Cause**: `AiAssistantActionInterface` extends `PluginFormInterface, ConfigurableInterface`. `AiAssistantActionBase` implements only some of those — the four form methods (plus `defaultConfiguration()`) remain abstract.
- **Fix**: Always implement `defaultConfiguration()`, `buildConfigurationForm()`, `validateConfigurationForm()`, `submitConfigurationForm()` on custom AI Assistant Action classes. Empty bodies are fine for actions without configurable settings.

## 17. Trusting LLM YAML output without validation

- **Symptom**: Agent's `solve()` runs but takes the wrong branch, throws on `null` array access, or swallows errors silently. Symptom is intermittent — appears once a request goes through a different model or with a longer prompt.
- **Cause**: `AiAgentBase::runSubAgent($file, $context, $module, $subDir)` returns the LLM's JSON response, decoded. The YAML's `output_schema` block is **not enforced at runtime in 1.3.x** — it's documentation for the LLM, not a validator. The model can return missing keys, wrong types, an empty string when an array is expected, or an entirely different shape.
- **Fix**: Treat the return value as untrusted input. Default every key, type-check before use, and have a fallback action when keys are missing. Pattern:
  ```php
  $plan = $this->runSubAgent('determineTask.yml', $context, '<module>', '<plugin_id>');
  $action = is_array($plan) && isset($plan['action']) ? (string) $plan['action'] : 'fallback';
  $keyword = is_string($plan['keyword'] ?? NULL) ? $plan['keyword'] : '';
  switch ($action) {
    // ...
    default:
      return sprintf('Unrecognized plan action %s. Raw: %s', $action, json_encode($plan));
  }
  ```
  For higher confidence, validate the decoded array against the YAML's `output_schema` manually — `JsonSchema\Validator` from `justinrainbow/json-schema` is already in core's vendor tree via `getdkan/dkan` if installed.
