# Create GitHub Issues

Create GitHub Issues from a PRD, plan, story file, or conversation context.

## Input

Use the user's message after invoking this command as the source path or issue
brief. Supported inputs:

- `.agents/PRDs/*.prd.md`
- `.agents/plans/*.plan.md`
- `.agents/stories/*.stories.md`
- free-form feature or bug description

If the input includes `--repo owner/name`, pass that repository to `gh`.

## Rules

- Use GitHub Issues, not Jira.
- Create small independently actionable issues.
- Ask before creating issues unless the user explicitly says to create them.
- Do not create duplicate issues; search existing issues first when the topic is
  likely to already exist.
- Keep implementation details grounded in this repo.

## Process

1. Load the input source.
2. If needed, inspect existing issues:

   ```bash
   gh issue list --search "{keywords}" --state open
   ```

3. Break work into issues with:
   - Title
   - Type label suggestion
   - Problem/context
   - Acceptance criteria
   - Technical notes
   - Validation commands
   - Dependencies

4. Save the issue manifest to:

   ```text
   .agents/stories/{kebab-case-name}.github-issues.md
   ```

5. If creation is approved, create issues:

   ```bash
   gh issue create --title "{title}" --body-file "{body-file}"
   ```

6. Update the manifest with issue numbers and URLs.

## Issue Body Template

```markdown
## Summary

{What needs to change and why}

## Acceptance Criteria

- [ ] {criterion}

## Technical Notes

- Likely files:
- Patterns to follow:
- Dependencies:

## Validation

```bash
python -m pytest {target}
```
```

## Output

Report:

- Manifest path
- Issues proposed
- Issues created, with URLs
- Any duplicates or blockers found
