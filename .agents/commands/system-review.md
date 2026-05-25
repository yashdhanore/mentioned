# System Review

Review a completed or messy agent run and improve the AI layer.

## Input

Use the user's message after invoking this command as the run, branch, report, or
problem to review. If blank, inspect recent `.agents/reports/`, current git diff,
and conversation context.

## Purpose

Find where the AI layer failed to give enough context, routing, validation, or
constraints. Propose small changes that make future runs better.

## Process

1. Load relevant artifacts:
   - `.agents/plans/`
   - `.agents/reports/`
   - `.agents/reviews/`
   - current git diff
2. Identify friction:
   - Wrong assumptions
   - Repeated user corrections
   - Missed validation
   - Missing tests
   - Unclear repo structure
   - Deployment, Supabase, Render, or artifact handling mistakes
3. Map each issue to an AI-layer fix:
   - `AGENTS.md` for always-on rules
   - `.agents/commands/` for workflow changes
   - `.agents/skills/` for reusable deep procedures
   - `.agents/rules/` for Cursor-specific behavior
   - docs for long-lived human context
4. Do not add broad rules for one-off mistakes.
5. Prefer specific, short edits.

## Output

```markdown
## System Review

### Friction Found

| Issue | Evidence | Proposed Fix |
|-------|----------|--------------|

### Recommended Edits

- `{file}`: {change}

### Apply Now?

{If user asked for implementation, apply the focused edits. Otherwise ask for approval.}
```
