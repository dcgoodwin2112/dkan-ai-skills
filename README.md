# dkan_ai_skill

Claude Code skills, slash commands, and DKAN/Drupal reference docs for writing and scaffolding custom modules that extend [DKAN](https://github.com/GetDKAN/dkan) and the [Drupal AI module](https://www.drupal.org/project/ai). The Drupal module itself ships no runtime code — it exists as a packaging surface for the [`claude-skills/`](claude-skills/) and [`claude-commands/`](claude-commands/) directories which are symlinked into `.claude/skills/` and `.claude/commands/`.

## What ships

### Skills

Two auto-loading skills under [`claude-skills/`](claude-skills/):

- **`drupal-ai-module`** (`claude-skills/drupal-ai-module/`) — auto-loads when Claude is working with `drupal/ai`, `drupal/ai_agents`, or the `ai_assistant_api` submodule of `drupal/ai`. Provides a plugin-type decision tree, top pitfalls, and pointers to the reference chunks in `claude-skills/drupal-ai-module/reference/`.
- **`dkan-module-author`** (`claude-skills/dkan-module-author/`) — auto-loads when editing files under `web/modules/custom/` or working with `Drupal\dkan\*`, `Drupal\metastore\*`, `Drupal\datastore\*`, `Drupal\harvest\*`, or `Drupal\common\*` namespaces. Surfaces the half-dozen DKAN-specific concepts that are non-obvious from the code alone, and routes to the bundled reference docs at `claude-skills/dkan-module-author/reference/` (DKAN architecture, services, REST API, workflows, testing, plus a Drupal patterns cheat sheet).

### Slash commands

#### Drupal AI scaffolding

| Command | Generates |
|---|---|
| `/ai-scaffold-provider <module> <ProviderName>` | AI Provider plugin (LLM backend) — class, settings form, route, `definitions/api_defaults.yml`, info.yml deps, schema, permissions, unit test stub |
| `/ai-scaffold-tool <module> <ToolName>` | FunctionCall plugin (AI tool) — class with attribute and `execute()` / `setOutput()` stubs, unit test stub |
| `/ai-scaffold-agent <module> <AgentName>` | AiAgent plugin — class with the real `parent::create()` pattern, `agentsCapabilities()` / `agentsNames()` / `answerQuestion()` / `determineSolvability()` / `solve()` stubs, YAML prompt directory, unit test stub |
| `/ai-scaffold-action <module> <ActionName>` | AiAssistantAction plugin — class extending `AiAssistantActionBase` with `listActions()` / `triggerAction()` / `provideFewShotLearningExample()` stubs |

All commands target Drupal AI **`^1.3`** by default and refuse to scaffold against `2.0.x` (breaking provider lifecycle changes). Tool and agent commands work against 1.2.x as well.

#### General Drupal scaffolding

| Command | Generates |
|---|---|
| `/scaffold-drupal-service <module_path> <ServiceName>` | A Drupal service class with constructor injection, `services.yml` entry, and unit test stub |
| `/add-event-subscriber <module_path> <EventName>` | An EventSubscriber class for a DKAN/Drupal event with tagged service registration |
| `/add-drupal-route <module_path> <path> [permission]` | A route + controller + permission entry (and the permission definition if needed) |
| `/validate-module <module_path>` | Runs phpcs, phpunit, permission audit, and cache rebuild against a custom module |

## Install

The skill and command files are loaded by Claude Code via symlinks; the Drupal module itself does not need to be enabled or required by Composer (it ships no runtime PHP code). A path-repo entry exists in the project's root `composer.json` so the module can be required later if it ever grows runtime code.

Symlink skills and commands into `.claude/`:

```bash
# Skills (one symlink per skill directory)
for d in web/modules/custom/dkan_ai_skill/claude-skills/*/; do
  name="$(basename "$d")"
  ln -s "../../$d" ".claude/skills/$name"
done

# Commands (one symlink per .md file)
for f in web/modules/custom/dkan_ai_skill/claude-commands/*.md; do
  ln -s "../../$f" ".claude/commands/$(basename "$f")"
done
```

## References

### Drupal AI module
- Plugin types, attributes, base classes: [claude-skills/drupal-ai-module/reference/plugin-types.md](claude-skills/drupal-ai-module/reference/plugin-types.md)
- Common pitfalls: [claude-skills/drupal-ai-module/reference/pitfalls.md](claude-skills/drupal-ai-module/reference/pitfalls.md)
- Service IDs and DI patterns: [claude-skills/drupal-ai-module/reference/services.md](claude-skills/drupal-ai-module/reference/services.md)
- Upstream docs: https://project.pages.drupalcode.org/ai/

### DKAN authoring
- Architecture overview: [claude-skills/dkan-module-author/reference/dkan-overview.md](claude-skills/dkan-module-author/reference/dkan-overview.md)
- Service IDs + method signatures: [claude-skills/dkan-module-author/reference/dkan-services.md](claude-skills/dkan-module-author/reference/dkan-services.md)
- REST API: [claude-skills/dkan-module-author/reference/dkan-api.md](claude-skills/dkan-module-author/reference/dkan-api.md)
- End-to-end workflows: [claude-skills/dkan-module-author/reference/dkan-workflows.md](claude-skills/dkan-module-author/reference/dkan-workflows.md)
- Testing patterns: [claude-skills/dkan-module-author/reference/dkan-testing.md](claude-skills/dkan-module-author/reference/dkan-testing.md)
- Drupal core conventions: [claude-skills/dkan-module-author/reference/drupal-patterns.md](claude-skills/dkan-module-author/reference/drupal-patterns.md)
