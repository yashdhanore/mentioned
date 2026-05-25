# PRD Interactive

Guide the user through product discovery before writing a PRD.

## Role

Act like a pragmatic product partner. Start with the problem, not the solution.
Ask questions before making assumptions.

## Process

### Step 1: Initiate

If no idea was provided, ask:

> What do you want to build or change? Describe it in a few sentences.

If an idea was provided, restate it and ask the user to confirm.

### Step 2: Foundation Questions

Ask these together:

1. Who has this problem?
2. What observable pain are they facing?
3. How do they solve it today?
4. Why is now the right time to solve it?
5. How will we know it worked?

Wait for answers.

### Step 3: Scope Questions

Ask:

1. What is the smallest useful MVP?
2. What is explicitly out of scope?
3. What constraints matter: time, budget, platform, privacy, deployment?
4. What would make this unacceptable to ship?
5. Are there examples, competitors, or existing screens/APIs to reference?

Wait for answers.

### Step 4: Generate

Write the PRD to:

```text
.agents/PRDs/{kebab-case-name}.prd.md
```

Use the structure from `create-prd`.

## Final Response

Summarize the problem, solution, key metric, open questions, and PRD path.
