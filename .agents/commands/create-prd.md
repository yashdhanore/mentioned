# Create PRD

Create a product requirements document from conversation context or a feature
brief.

## Input

Use the user's message after invoking this command as the product or feature idea.
If the user gives a filename, use it for the output name.

## Process

1. Extract explicit requirements and goals.
2. Identify missing critical information.
3. If critical information is missing, ask concise clarifying questions before
   generating.
4. Keep assumptions visible instead of hiding them in confident prose.

## Output File

Save to:

```text
.agents/PRDs/{kebab-case-name}.prd.md
```

## PRD Structure

```markdown
# {Product or Feature Name}

## Executive Summary

{2-3 paragraphs}

## Problem

{Who has what pain and why it matters}

## Target Users

{Primary users and non-users}

## Goals

- {goal}

## Non-Goals

- {explicitly out of scope}

## MVP Scope

| Priority | Capability | Rationale |
|----------|------------|-----------|

## User Stories

- As a {user}, I want {action}, so that {benefit}.

## Functional Requirements

- [ ] {requirement}

## Technical Considerations

- Backend/API:
- Worker/extraction:
- Database/Supabase:
- Mobile/client:
- Deployment:

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|

## Risks And Mitigations

| Risk | Mitigation |
|------|------------|

## Open Questions

- [ ] {question}

## Implementation Phases

| Phase | Goal | Deliverables |
|-------|------|--------------|
```

## Final Response

Report the PRD path, assumptions, open questions, and recommended next command.
