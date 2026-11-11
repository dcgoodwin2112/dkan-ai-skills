# AGENTS.md

Claude Code plugin for DKAN 4.x work. Canonical content is under `plugins/drupal-dkan-ai/`:

- [`skills/dkan/SKILL.md`](plugins/drupal-dkan-ai/skills/dkan/SKILL.md) — non-obvious DKAN concepts and traps. Read it before writing code that touches DKAN.
- [`skills/dkan/reference/dkan-workflows.md`](plugins/drupal-dkan-ai/skills/dkan/reference/dkan-workflows.md) — cross-class call chains.
- `hooks/` — commit-gate and dependency-gate; tested by `bin/test`.

Content policy: see [README.md](README.md#content-policy). No version pins, signature tables, or code templates in the skill.

## Review guidelines

Previously declined findings — do not re-flag:

- Em dashes are accepted punctuation in prose and docs.
- Commit messages and docs are deliberately concise and hype-free; brevity is not a defect.
