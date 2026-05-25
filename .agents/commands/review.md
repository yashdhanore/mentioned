# Review

Perform a code review of a PR, file, folder, or local changes.

## Input

Use the user's message after invoking this command as the review scope. If blank,
review unstaged and staged local changes.

## Review Stance

Prioritize bugs, regressions, missing tests, security issues, data integrity, and
deployment risk. Keep style comments secondary.

## Scope Resolution

- PR number or URL: inspect with `gh pr view` and `gh pr diff` if available.
- File or folder: review that path.
- Blank: review `git diff` and `git diff --cached`.

## Project-Specific Checks

- FastAPI routes return stable response shapes and status codes.
- Auth behavior is explicit for dev vs Supabase modes.
- Job queue behavior is idempotent and safe for one beta worker.
- Worker code does not assume API-role privileges.
- Extraction code handles network/tool failures deterministically.
- OCR/LLM/provider code has configured-provider and fallback tests.
- Subprocess calls avoid command injection and unsafe paths.
- File writes stay under expected artifact/storage locations.
- Secrets are not logged, printed, committed, or included in artifacts.
- Supabase schema/RLS changes follow CLI migration workflow.
- Render-facing changes match `render.yaml` and deployment docs.
- Tests are deterministic and avoid real network/API calls unless explicitly
  marked as integration or smoke tests.

## Validation

Run validation when appropriate:

```bash
python -m pytest
```

## Output

Lead with findings:

```markdown
## Findings

1. [Severity] `path:line` - Issue and impact.
   Recommendation: Concrete fix.

## Open Questions

{Questions or "None"}

## Validation

{Commands run and results, or why not run}

## Summary

{Brief change summary}
```

If there are no findings, say that clearly and mention residual risk or test gaps.
