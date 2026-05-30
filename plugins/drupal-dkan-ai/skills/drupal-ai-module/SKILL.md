---
name: drupal-ai-module
description: Reference and decision support for writing custom modules that extend the Drupal AI module (drupal/ai, drupal/ai_agents, drupal/ai_assistant_api). Loads when the user is writing Provider, FunctionCall (Tool), AiAgent, AiAssistantAction, or AiAutomatorType plugins, or when working with the AI module's plugin discovery, services, or extension points. Targets drupal/ai 1.3.x; refuses 2.0.x as unstable.
---

# Drupal AI Module — Plugin Author's Reference

This skill loads when you're extending the Drupal AI module. It covers what plugin types exist, when to reach for each one, the always-true rules, and the most common pitfalls. Detail lives in [reference/plugin-types.md](reference/plugin-types.md), [reference/pitfalls.md](reference/pitfalls.md), [reference/services.md](reference/services.md), [reference/testing-ai-plugins.md](reference/testing-ai-plugins.md), and [reference/ai-search-rag.md](reference/ai-search-rag.md).

For scaffolding boilerplate, use the slash commands: `/ai-scaffold-provider`, `/ai-scaffold-tool`, `/ai-scaffold-agent`, `/ai-scaffold-action`.

> **Path convention**: example paths are written as `<webroot>/modules/...`, relative to the project's Drupal web root (`docroot/` in DKAN's recommended-project, `web/` in many other builds). Substitute your project's actual root; confirm with `ls` if unsure.

> **Version floor**: `drupal/ai 1.3.x` requires Drupal `^10.5 || ^11.2`; `ai_agents 1.2.x` requires `^10.3 || ^11`. This is a higher core floor than DKAN itself (`^10.2`) — a module combining DKAN + AI must satisfy the AI floor. Verify with `composer show drupal/ai | grep drupal/core` before assuming a core version.

## When to use which plugin type

| The user wants… | Plugin type | Path | Detail |
|---|---|---|---|
| Add a new LLM backend (Anthropic, OpenAI, Ollama, internal API) | **AI Provider** | `src/Plugin/AiProvider/` | [plugin-types.md#ai-provider](reference/plugin-types.md#ai-provider) |
| Give an AI agent a custom action (CRUD an entity, hit an internal API) | **FunctionCall (Tool)** | `src/Plugin/AiFunctionCall/` | [plugin-types.md#functioncall-tool](reference/plugin-types.md#functioncall-tool) |
| An autonomous worker that drives LLM-backed YAML prompts to fulfill a goal | **AI Agent** | `src/Plugin/AiAgent/` | [plugin-types.md#ai-agent](reference/plugin-types.md#ai-agent) |
| A chatbot that can perform Drupal actions (create node, assign role, RAG search) | **AI Assistant Action** | `src/Plugin/AiAssistantAction/` | [plugin-types.md#assistant-action](reference/plugin-types.md#assistant-action) |
| Auto-populate a custom field type from a prompt | **AI Automator Type** | `src/Plugin/AiAutomatorType/` | [plugin-types.md#automator-type](reference/plugin-types.md#automator-type) |
| New embedding/vector-DB backend for AI Search | **Vector DB Provider** | `src/Plugin/VdbProvider/` | [plugin-types.md#vector-db-provider](reference/plugin-types.md#vector-db-provider) + [ai-search-rag.md](reference/ai-search-rag.md) |
| Semantic search / RAG over a corpus (e.g. dataset descriptions) | ai_search + VdbProvider + embeddings | — | [ai-search-rag.md](reference/ai-search-rag.md) |
| Testing providers/tools/agents (unit + LLM eval) | — | `tests/` | [testing-ai-plugins.md](reference/testing-ai-plugins.md) |
| New "operation type" (rerank, structured-output, etc.) | Operation Type — **interfaces + DTOs**, not plugins | `src/OperationType/<Name>/` | [plugin-types.md#operation-type](reference/plugin-types.md#operation-type) |

If the user just wants to *use* AI from existing code (call chat, generate embeddings), they don't need a plugin — inject `ai.provider` and call it. Save the plugin types for *extending* the framework.

## Always-true rules

1. **Key module is required.** Every provider resolves API keys via `\Drupal::service('key.repository')`. Add `key:key` to the module's `*.info.yml` dependencies. Never store raw secrets in `config/install/*.yml` — use Key entity references only.
2. **Run `drush cr` after adding a plugin.** Plugin attribute discovery is cached. New providers/tools/agents won't appear until cache rebuild. The scaffold commands run this automatically.
3. **Target `^1.3`, not `^2.0`.** As of April 2026, `2.0.x` is dev with breaking provider lifecycle changes per the upstream issue tracker. The 1.3.x line is stable.
4. **Plugin directory casing matters.** `src/Plugin/AiFunctionCall/` (singular `Call`, PascalCase) — `AiFunctionCalls/` is silently ignored.
5. **Operation-type interface ↔ supportedOperationTypes() must agree.** A provider implementing `ChatInterface` must also list `'chat'` in `getSupportedOperationTypes()`, or `hasProvidersForOperationType('chat')` returns false and the provider is invisible.

## Top pitfalls (read [reference/pitfalls.md](reference/pitfalls.md) for the full list)

1. **Forgot `drush cr`** — symptom: new plugin doesn't appear at `/admin/config/ai/...`. Fix: cache rebuild.
2. **Key module not enabled** — symptom: provider's `setAuthentication()` silently fails, all calls return empty. Fix: `drush en key`.
3. **`getSupportedOperationTypes()` mismatch** — symptom: provider visible in the list but `hasProvidersForOperationType('chat')` returns false. Fix: align declared ops with implemented interfaces.
4. **API keys in config exports** — symptom: secrets leaked to git. Fix: only Key entity references in `config/install/*.yml`.
5. **Agent prompts in wrong format** — symptom: `runSubAgent('foo.yml', ...)` errors with "file not found", or agent ignores intended prompt. Cause: ai_agents uses **per-operation YAML files** at `prompts/<plugin_id>/<name>.yml`, not `system.txt` + `task.txt`. Fix: place prompts at `prompts/<plugin_id>/<operationName>.yml` (lowercase, snake-case dir matching plugin ID).

## Service IDs to inject

| Service ID | Class | Use for |
|---|---|---|
| `ai.provider` | `Drupal\ai\AiProviderPluginManager` | Load provider instances; check operation availability |
| `plugin.manager.ai.function_calls` | `FunctionCallPluginManager` | Discover/instantiate FunctionCall tools |
| `plugin.manager.ai_agents` | `Drupal\ai_agents\PluginManager\AiAgentManager` | Load agents (`createInstance` → `setChatInput` → `solve`) |
| `ai_assistant_api.action_plugin.manager` | `Drupal\ai_assistant_api\AiAssistantActionPluginManager` | Discover Assistant Actions |
| `ai.form_helper` | `AiProviderFormHelper` | Standardized provider/model selectors in config forms |
| `key.repository` | (Key module) | Always inject when a plugin uses an API key |
| `logger.factory` | `LoggerChannelFactoryInterface` | Call `->get('<channel>')` to obtain a logger. `logger.channel.ai` is **not** a registered service. |

Full table with method signatures: [reference/services.md](reference/services.md).

## Version detection

Before scaffolding 1.3-only features, detect installed version:

```bash
composer show drupal/ai | grep ^versions
```

If the major is `2`, the commands refuse to scaffold and direct the user to pin to `^1.3` first. The 1.2.x → 1.3.x change is mostly internal; scaffolds target both.

## Reference

- [reference/plugin-types.md](reference/plugin-types.md) — base classes, attributes, required methods, paths for each plugin type
- [reference/pitfalls.md](reference/pitfalls.md) — full pitfall list with symptoms, causes, fixes
- [reference/services.md](reference/services.md) — service IDs, classes, key methods for DI
- [reference/testing-ai-plugins.md](reference/testing-ai-plugins.md) — unit-testing tools, asserting tool dispatch, golden-case eval, mocking `ai.provider`
- [reference/ai-search-rag.md](reference/ai-search-rag.md) — RAG, embeddings, VdbProvider authoring, ai_search Search API backend
- Upstream docs: https://project.pages.drupalcode.org/ai/1.3.x/
- Canonical provider example: https://www.drupal.org/project/ai_provider_openai
- Canonical agent + tool examples: `ai_agents` built-in `FieldType`/`ContentType`/`TaxonomyAgent` (in `<webroot>/modules/contrib/ai_agents/src/Plugin/AiAgent/`) and the tools in `<webroot>/modules/contrib/ai_agents/src/Plugin/AiFunctionCall/`
