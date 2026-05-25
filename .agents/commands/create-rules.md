# Create Rules

Create or update persistent project rules for agents.

## Input

Use the user's message after invoking this command as guidance for what rules to
create or update. If blank, analyze the codebase and improve `AGENTS.md` only where
there is clear value.

## Rules

- Keep `AGENTS.md` concise and durable.
- Do not duplicate full docs already available elsewhere.
- Add rules only for recurring conventions, important safety constraints, and
  commands agents must know.
- Prefer directory-specific rules only when a subdirectory truly needs different
  guidance.

## Process

1. Read `AGENTS.md`, `README.md`, `pyproject.toml`, and relevant docs.
2. Identify gaps that would affect future agent work.
3. Check whether the gap belongs in:
   - `AGENTS.md` for always-on repo rules
   - `.agents/commands/` for repeatable workflows
   - `.agents/skills/` for richer procedures
   - `.agents/rules/*.mdc` for Cursor-specific rule behavior
   - docs for human-facing long-form guidance
4. Propose or apply a focused update.

## Output

Report:

- Files changed
- Rules added or updated
- Why each rule belongs there
- Any rules intentionally left out
