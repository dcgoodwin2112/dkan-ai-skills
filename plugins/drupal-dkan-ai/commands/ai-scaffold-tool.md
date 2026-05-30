---
description: Scaffold a FunctionCall (AI tool) plugin for Drupal AI
argument-hint: <module_path> <ToolName> [context_args...]
---

Scaffold a new FunctionCall (AI tool) plugin for the Drupal AI module — gives an AI agent a callable action.

Read [SKILL.md](../skills/drupal-ai-module/SKILL.md), [plugin-types.md](../skills/drupal-ai-module/reference/plugin-types.md#functioncall-tool), and [pitfalls.md](../skills/drupal-ai-module/reference/pitfalls.md) before proceeding.

## Input

`$ARGUMENTS` should be: `<module_path> <ToolName> [context_args...]`

- `module_path`: Path to the target module relative to the project root, or just the machine name.
- `ToolName`: PascalCase class name (e.g., `LoadDataset`, `GetWeather`).
- `context_args`: Optional. Each is `<arg_name>:<type>` (e.g., `dataset_id:string count:integer`). Type values are Drupal TypedData plugin IDs — common ones: `string`, `integer`, `boolean`, `float`, `list` (for arrays), `map` (for keyed associative arrays), `email`, `uri`, `timestamp`. **Do NOT use `array`** — it's not a registered data type. See `<webroot>/modules/contrib/ai_agents/src/Plugin/AiFunctionCall/ListConfigEntities.php` for an example mixing `string`, `integer`, `list`. If no args provided, generate a single placeholder `input:string` context.

## Steps

### 1. Version gate

Check `composer show drupal/ai`. Refuse on `2.x`. The scaffold uses only `ExecutableFunctionCallInterface`; `FunctionCallBase` already implements `OverridableFunctionCallInterface`, so no per-version branching is needed.

### 2. Locate module and derive identifiers

- Read `<module_path>/<module_name>.info.yml`.
- Snake-case name: snake_case of `ToolName` (e.g., `LoadDataset` → `load_dataset`).
- Plugin ID: `<module_name>:<snake_case_name>` (e.g. `ai_skill_test:load_dataset`) — matches the `ai_agents` convention.
- `function_name`: the snake-case name without the module prefix — this is what the LLM sees.
- Class FQN: `Drupal\<module_name>\Plugin\AiFunctionCall\<ToolName>`.

### 3. Update `<module_name>.info.yml` dependencies

Ensure `ai:ai` is present. (FunctionCalls don't require `ai_agents` to be installed — they live in `ai` core — but agents that call them do.)

### 4. Generate the FunctionCall class

Path: `<module_path>/src/Plugin/AiFunctionCall/<ToolName>.php`. **Critical: directory is `AiFunctionCall` (singular, PascalCase)** — `AiFunctionCalls` is silently ignored.

Pattern:

```php
<?php

declare(strict_types=1);

namespace Drupal\<module_name>\Plugin\AiFunctionCall;

use Drupal\ai\Attribute\FunctionCall;
use Drupal\ai\Base\FunctionCallBase;
use Drupal\ai\Service\FunctionCalling\ExecutableFunctionCallInterface;
use Drupal\Core\Plugin\Context\ContextDefinition;
use Drupal\Core\StringTranslation\TranslatableMarkup;

#[FunctionCall(
  id: '<module_name>:<snake_case_name>',
  function_name: '<snake_case_name>',
  name: '<ToolName>',
  description: 'TODO: One-sentence description of what this tool does. The LLM reads this to decide when to call it.',
  group: 'utility',
  context_definitions: [
    // One ContextDefinition per arg from $context_args. Example:
    // 'dataset_id' => new ContextDefinition(
    //   data_type: 'string',
    //   label: new TranslatableMarkup('Dataset ID'),
    //   description: new TranslatableMarkup('UUID of the dataset to load.'),
    //   required: TRUE,
    // ),
  ],
)]
class <ToolName> extends FunctionCallBase implements ExecutableFunctionCallInterface {

  /**
   * {@inheritdoc}
   */
  public function execute() {
    // Read inputs:
    // $datasetId = $this->getContextValue('dataset_id');
    // Perform the action and write a string result with $this->setOutput().
    // The base class returns this from getReadableOutput() automatically.
    $this->setOutput('TODO: implement <ToolName>::execute()');
  }

}
```

For each entry in `context_args`, generate a `ContextDefinition` with named arguments — `data_type`, `label` (TranslatableMarkup, Title Case from snake_case), `description` (TranslatableMarkup placeholder), `required: TRUE` for the first arg, `FALSE` for subsequent ones.

**Do not** redeclare `OverridableFunctionCallInterface` — `FunctionCallBase` already implements it. Only add `ExecutableFunctionCallInterface` (declares the plugin runs server-side).

`setOutput()` accepts a `string`. For structured results, `json_encode()` first, or override `getReadableOutput()` if a custom format is needed.

### 5. Generate a unit test stub

Path: `<module_path>/tests/src/Unit/Plugin/AiFunctionCall/<ToolName>Test.php`. Tests that:

- The plugin can be instantiated (mock `ContainerInterface` if the FunctionCallBase requires services).
- `execute()` populates `getReadableOutput()` (use a stub that bypasses real action).
- Required context values throw if missing — `$this->setContextValue()` driven.

### 6. Cache rebuild

Run `ddev drush cr`.

### 7. Verify runtime discovery

Don't report done on scaffold output alone — runtime errors (wrong service ID in `create()`, malformed attribute) only surface here. Run:

```bash
ddev drush ev "\$t = \Drupal::service('plugin.manager.ai.function_calls')->createInstance('<plugin_id>'); echo get_class(\$t) . PHP_EOL;"
```

Expected: prints the FQN of the tool class. Any exception (missing service, attribute parse error, missing context definition) will surface here.

### 8. Print next steps

1. Implement `execute()` — read context values, perform the action, store result for `getReadableOutput()`.
2. Refine the `description:` string in the `#[FunctionCall(...)]` attribute — the LLM reads this to decide when to call the tool. Be precise about inputs and outputs.
3. Verify discovery: `ddev drush ev "var_dump(\Drupal::service('plugin.manager.ai.function_calls')->getDefinitions()['<plugin_id>'] ?? 'NOT FOUND');"`
4. Use the tool from agent code via `\Drupal::service('plugin.manager.ai.function_calls')->createInstance('<plugin_id>')`, then `setContextValue()` for each arg, then `execute()`. Agents that drive YAML prompts (the `ai_agents` style) typically don't auto-discover function calls — call them explicitly from `solve()`.
5. Run the unit test: `cd <module_path> && vendor/bin/phpunit tests/src/Unit/Plugin/AiFunctionCall/<ToolName>Test.php`.

## Pitfall checks before reporting done

- [ ] Directory is exactly `src/Plugin/AiFunctionCall/` (singular `Call`, PascalCase).
- [ ] `function_name` matches the snake-case portion of `id` after the colon.
- [ ] `description:` is informative — the LLM uses it for tool selection.
- [ ] Every `context_definitions` entry uses named arguments (`data_type:`, `label:`, `description:`, `required:`).
- [ ] `OverridableFunctionCallInterface` is NOT redeclared (the base implements it).
- [ ] `execute()` writes its result via `$this->setOutput($string)`.
- [ ] `drush cr` ran without error.
