# AI Layer Agent Guide

`.agents/` is the canonical source for reusable agent commands, repo-specific skills, Cursor rules, plans, reports, reviews, PRDs, and stories.

## Source Of Truth

- Edit commands in `.agents/commands/`.
- Edit skills in `.agents/skills/`.
- Edit Cursor rules in `.agents/rules/`.
- Do not edit adapter symlinks under `.claude/commands/`, `.claude/skills/`, `.cursor/commands/`, or `.cursor/rules/` directly.

## Workflow

- Shared commands are plain Markdown for Claude/Cursor command compatibility and are referenceable playbooks for Codex.
- Codex's active reusable workflows live in `.agents/skills/`.
- For larger work, use the command loop: `prime`, `plan`, `implement`, `validate`, `review` or `security-review`, then `system-review` after messy runs to improve the AI layer.
- Avoid agent-specific argument syntax in shared commands unless a separate adapter is intentionally created.
