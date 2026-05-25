# Shared Agent Commands

This directory is the source of truth for project agent commands.

Edit files here first. The files under `.claude/commands/` and `.cursor/commands/`
are symlinks/adapters and should not be edited directly.

These commands are written as plain Markdown so they can be reused by Claude and
Cursor. Codex does not load project slash-command files in this format; use these
commands as referenceable playbooks in Codex, and put active Codex workflows in
`.agents/skills/`.

Keep command names in kebab-case and keep command bodies tool-neutral. Avoid
Claude-only placeholders such as `$ARGUMENTS` in shared command files.

This project uses GitHub Issues, not Jira. Commands that need issue context should
use the GitHub CLI (`gh`) when available and should write local artifacts under
`.agents/`.
