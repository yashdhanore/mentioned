# Plan

Create an implementation plan from a feature request, bug report, PRD, issue, or
conversation context.

## Input

Use the user's message after invoking this command as the plan input. If it points
to a file, read that file. If it is blank, use current conversation context.

If the input references a GitHub issue, fetch it with `gh issue view` when
available and include the issue number in the plan metadata.

## Rules

- Plan only. Do not edit production code.
- Explore the codebase before proposing changes.
- Prefer existing project patterns over new abstractions.
- Keep validation explicit and executable.

## Process

1. Parse the request:
   - Problem
   - User story or failure mode
   - Scope
   - Out of scope
   - Risk level
   - GitHub issue number or URL, if any

2. For GitHub issue input, inspect the issue:

   ```bash
   gh issue view {issue-number} --json number,title,body,labels,comments,state,url,author
   ```

3. Explore relevant files with `rg` and targeted reads.
4. Document patterns to mirror:
   - Router/service/schema/model patterns
   - Extraction pipeline patterns
   - Worker/job patterns
   - Tests and fixtures
   - Error handling
   - Config and environment handling

5. Design the change:
   - Files to create
   - Files to update
   - Dependency order
   - Test strategy
   - Manual or smoke verification

6. Include special workflows when applicable:
   - Supabase changes: use Supabase CLI and migrations under `supabase/migrations/`
   - Alembic changes: use migration files under `migrations/`
   - Hosted backend issues: inspect Render before guessing
   - Visual extraction changes: run the visual manifest evaluation when relevant

## Output File

Save the plan to:

```text
.agents/plans/{kebab-case-name}.plan.md
```

## Plan Template

```markdown
# Plan: {Name}

## Summary

{What will change and why}

## Scope

- In:
- Out:

## Issue

- GitHub Issue: {#number or N/A}
- URL: {url or N/A}

## Patterns To Follow

| Area | Source | Pattern |
|------|--------|---------|
| {area} | `{file}` | {pattern} |

## Files To Change

| File | Action | Purpose |
|------|--------|---------|
| `{path}` | CREATE/UPDATE | {why} |

## Tasks

1. {Task}
   - Files:
   - Details:
   - Validate:

## Validation

```bash
python -m pytest
```

Add any targeted commands, smoke tests, Render checks, Supabase CLI commands, or
visual manifest evaluation required by the change.

## Acceptance Criteria

- [ ] Tests pass
- [ ] Behavior matches request
- [ ] Generated/runtime artifacts are not staged
- [ ] Documentation updated if behavior changed
```

## Final Response

Report the plan file path, main risks, and recommended next step.
