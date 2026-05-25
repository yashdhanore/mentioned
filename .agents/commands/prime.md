# Prime

Load project context before planning or implementing.

## Input

Use the user's message after invoking this command as the target issue, feature,
bug, or question. If no explicit input exists, use the current conversation.

If the input is a GitHub issue reference such as `#123`, `123`, or a GitHub issue
URL, fetch the issue with `gh issue view` when the GitHub CLI is available.

## Process

1. Read `AGENTS.md`, `README.md`, and any relevant docs under `docs/`.
2. If a GitHub issue was provided, inspect it:

   ```bash
   gh issue view {issue-number} --json number,title,body,labels,comments,state,url,author
   ```

   Use the issue title, body, labels, and comments as task context. If `gh` is not
   authenticated or available, fall back to the visible issue text or ask the user
   for the missing details.

3. Inspect the current git state:

   ```bash
   git status --short
   git log --oneline -5
   ```

4. Map the relevant code areas:
   - FastAPI app entrypoint and routers under `src/`
   - Auth, jobs, mentions, books, push, and storage modules
   - Extraction pipeline under `src/extraction/`
   - Worker entrypoints under `src/worker.py` and configured scripts
   - Database models and migrations
   - Tests under `tests/`
   - Deployment docs, Render config, and Supabase docs when relevant
   - Mobile client only when the task touches mobile behavior

5. If the task is about hosted backend failures, use Render evidence before drawing
   conclusions from local code.
6. If the task is about schema, migration, seed, RLS, or Supabase config, plan to
   use the Supabase CLI directly and follow `AGENTS.md`.
7. Identify existing patterns to follow, with file references.

## Output

Write a concise context summary to `.agents/reports/prime.md` when useful, then
answer with:

- Project purpose
- Relevant code areas
- Current state
- GitHub issue context, if used
- Patterns to follow
- Risks or unknowns
- Recommended next command, usually `plan`
