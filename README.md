# dkan-ai-skills

A Claude Code plugin (`drupal-dkan-ai`) for [DKAN](https://github.com/GetDKAN/dkan) 4.x work: one skill of non-obvious DKAN concepts, plus two `PreToolUse` hooks. No runtime PHP.

## Layout

```
plugins/drupal-dkan-ai/
  skills/dkan/SKILL.md                 gotchas: building against DKAN, core contribution, metadata, frontend
  skills/dkan/reference/dkan-workflows.md   cross-class call chains
  hooks/                               commit-gate, dependency-gate
bin/test                               hook tests (also run in CI)
```

## Content policy

The skill holds only what the installed source will not tell an agent quickly: concepts, traps, and decisions. It does not hold version pins, signature or service tables, command lists, or code templates — those are read from the checkout (`composer show`, `grep`, `drush list`), which is never stale.

Add an entry when a real session gets something wrong that the source alone did not prevent. Verify it against the installed code first.

Generic Drupal, `drupal/ai`, and `mcp_server` guidance was removed on 2026-11-11: current models cover the generic layer, and those modules ship their own agent docs (`<webroot>/modules/contrib/ai/.agents/skills/`, `mcp_server/AGENTS.md`). Removed content is in git history before that date.

## Install

```bash
claude plugin marketplace add /path/to/dkan-ai-skills
```

```bash
claude plugin install drupal-dkan-ai@dkan-ai-skills
```

Updating: bump `version` in `plugins/drupal-dkan-ai/.claude-plugin/plugin.json`, then:

```bash
claude plugin marketplace update dkan-ai-skills
```

```bash
claude plugin update drupal-dkan-ai@dkan-ai-skills
```

Hooks load at session start; in Claude Desktop, quit and reopen.

## Hooks

Fast local gates; CI stays authoritative. Trace either with `CLAUDE_GATE_DEBUG=1`, preview with `CLAUDE_GATE_DRYRUN=1`.

### commit-gate

Before `git commit`, runs phpcs and phpunit via DDEV for each module the commit touches and blocks on failure.

- Self-scoping: no-op unless the commit is in a DDEV-backed repo and touches a module with `phpcs.xml.dist` or `phpunit.xml`.
- Runs only the `unit` testsuite when the module's `phpunit.xml` defines one.
- DDEV down: warns and allows.
- Timeout (300s): the commit proceeds ungated.
- Bypass: `CLAUDE_SKIP_COMMIT_GATE=1`.

### dependency-gate

Blocks commands that add a named package (`composer require`, `npm install <pkg>`, `yarn add`, `pip install <pkg>`, `uv add`, and equivalents) so a human vets it first. Not project-scoped.

- Lockfile-driven installs (`composer install`, `npm ci`, `pip install -r …`) are not gated.
- Bypass: `CLAUDE_SKIP_DEP_GATE=1`.

## Tests

```bash
bin/test
```
