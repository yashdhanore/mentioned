# Create Stories

Turn a PRD or plan into small implementation stories and optionally create GitHub
Issues.

## Input

Use the user's message after invoking this command as the PRD or plan path. If no
path is provided, look in `.agents/PRDs/` and ask which PRD to use when ambiguous.

If the user includes `--create-issues`, create GitHub Issues with `gh issue create`
after writing the local story file. If the user includes `--repo owner/name`, pass
that repository to `gh` with `--repo`.

## Process

1. Read the PRD or plan.
2. Extract capabilities, acceptance criteria, dependencies, and constraints.
3. Break work into independently reviewable stories.
4. Keep each story small enough for a focused implementation pass.
5. Include technical notes grounded in this repo's structure.
6. If creating GitHub Issues, confirm `gh auth status` works and ask before creating
   issues unless the user explicitly requested creation.

## Story Categories

- Feature
- Enhancement
- Bug
- Technical
- Spike

## Output File

Save to:

```text
.agents/stories/{kebab-case-name}.stories.md
```

## GitHub Issue Creation

When requested, create one GitHub Issue per story:

```bash
gh issue create \
  --title "{Story title}" \
  --body-file "{temporary-story-body-file}" \
  --label "{label}"
```

Use labels such as `feature`, `bug`, `technical`, `spike`, `backend`, `mobile`,
`extraction`, `supabase`, or `deployment` only if they already exist or the user
asks to create/manage labels. Prefer issue bodies that include acceptance criteria,
technical notes, dependencies, and validation commands.

After creation, update the local story file with created issue URLs.

## Story Template

```markdown
# Stories: {Name}

## Story 1: {Title}

**Type**: Feature / Enhancement / Bug / Technical / Spike
**Priority**: High / Medium / Low
**Complexity**: Small / Medium / Large
**Depends On**: {story ids or None}

### User Story

As a {user}, I want {action}, so that {benefit}.

### Acceptance Criteria

- [ ] Given {context}, when {action}, then {result}

### Technical Notes

- Likely files:
- Patterns to follow:
- Tests:

### Validation

```bash
python -m pytest {target tests}
```
```

## Final Response

Report story count, output path, dependencies, any created GitHub Issue URLs, and
the recommended first story.
