# Implement

Execute an approved plan end to end.

## Input

Use the user's message after invoking this command as the path to the plan or a
clear implementation request. Prefer implementing from `.agents/plans/*.plan.md`.

## Rules

- Read the plan before editing.
- Check `git status --short` before editing.
- Never revert user changes.
- Verify assumptions before each task.
- Validate after meaningful changes instead of accumulating broken state.
- Do not stage or commit secrets, `.env`, `app.db`, `data/artifacts/`, caches, or
  generated runtime outputs.

## Process

1. Load the plan and extract tasks, files, validation commands, and acceptance
   criteria. If the plan references a GitHub issue, keep that issue number for the
   report and optional issue update.
2. Inspect target and adjacent files before changing them.
3. Implement tasks in order.
4. Add or update tests near the affected behavior.
5. Run targeted tests first, then broader validation:

   ```bash
   python -m pytest
   ```

6. When relevant, run:

   ```bash
   python scripts/score_extraction_eval.py --results outputs/<run>/result.json
   ```

7. For Supabase changes, run the relevant Supabase CLI verification from
   `AGENTS.md`.
8. For hosted backend failures, include Render evidence used.
9. Write an implementation report to:

   ```text
   .agents/reports/{plan-name}-implementation.md
   ```

10. If a GitHub issue is linked and `gh` is available, add a concise progress or
    completion comment after validation:

    ```bash
    gh issue comment {issue-number} --body-file {report-path}
    ```

    Do not close the issue unless the user explicitly asks or the plan says to.

## Report Template

```markdown
# Implementation Report: {Name}

**GitHub Issue**: {#number or N/A}

## Summary

{What changed}

## Tasks Completed

| Task | Status | Notes |
|------|--------|-------|

## Validation

| Command | Result |
|---------|--------|

## Files Changed

| File | Purpose |
|------|---------|

## Deviations From Plan

{None or list}

## Follow-Ups

{None or list}
```

## Final Response

Summarize changes, validation run, report path, and any remaining risk.
