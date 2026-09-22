# Validate

Run project validation and report failures clearly.

## Input

Use the user's message after invoking this command to narrow validation. If blank,
run the default backend validation.

## Default Validation

Run from repo root:

```bash
python -m pytest
```

## Conditional Validation

Run these only when relevant:

- Extraction prompt, schema, or model changes (after a comparison run):

  ```bash
  python scripts/score_extraction_eval.py --results outputs/<run>/result.json
  ```

- Production release environment shape:

  ```bash
  python scripts/check_release_env.py --env-file .env --worker-replicas 1
  ```

- Database migrations:

  ```bash
  alembic upgrade head
  ```

- Supabase migrations/config/RLS:
  Use `supabase --help`, then the relevant local or dry-run commands from
  `AGENTS.md`.

## Process

1. Identify the relevant validation scope.
2. Run commands from repo root.
3. Capture exact failure files, test names, and error messages.
4. If failures are caused by the current change and the user asked for a fix,
   fix them and rerun.

## Output

Use this format:

```markdown
## Validation Results

| Check | Result | Details |
|-------|--------|---------|
| Pytest | PASS/FAIL | {summary} |
| Visual eval | PASS/FAIL/SKIPPED | {summary} |
| Other | PASS/FAIL/SKIPPED | {summary} |

### Failures

{File/test/error/fix direction, or "None"}
```
