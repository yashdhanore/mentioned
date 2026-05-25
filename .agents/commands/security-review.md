# Security Review

Perform a security-focused review of local changes, a file, or a folder.

## Input

Use the user's message after invoking this command as the security review scope. If
blank, review staged changes first, then unstaged changes.

## Categories

Check only categories relevant to the changed code:

- Auth and authorization boundaries
- Supabase RLS and database role separation
- Secret handling and logging
- SQL/query safety
- Subprocess and external binary safety
- URL, path, and file upload/download handling
- SSRF or unsafe network requests
- LLM/OCR/provider prompt or data leakage
- Error messages that expose internals
- Deployment configuration on Render
- Dependency or configuration risk

## Project-Specific Rules

- Do not expose service-role keys, DB passwords, Supabase tokens, `.env`, or
  access tokens.
- API role and worker role must stay separated in production.
- Do not bypass RLS unless an explicit internal worker path requires it and the
  role boundary is documented.
- Treat Instagram/media URLs and downloaded files as untrusted input.
- Prefer deterministic tests with `tmp_path`, `monkeypatch`, and mocked
  subprocess/provider calls.

## Output

```markdown
## Security Review

**Scope**: {scope}
**Verdict**: PASS / PASS WITH NOTES / FAIL

### Findings

1. [Severity] `path:line` - {issue}
   Risk: {impact}
   Fix: {recommendation}

### What Looks Good

- {positive security controls}

### Validation

{Commands run or not run}
```
