# gather.md

## Position in the framework

Step 1 of 4 in the `/design` workflow, invoked by `commands/design.md`.

- **Previous step**: none — this is the first step. Input is the user's
  initial description of the feature from the `/design` invocation.
- **This step**: have a thorough, structured conversation to reach a deep,
  unambiguous understanding of the feature before any analysis or drafting
  begins. Produces `knowledge/requirements/<feature-folder>/gather.md`.
- **Next step**: `commands/analyze.md`, which reads `gather.md` to write
  `analysis.md` and `architecture.md`.

## Goal of this step

This step exists so implementation never starts from a vague brief. The user
is willing to spend 10–20 minutes here — that time is an investment that
prevents rework. Ask everything that needs to be asked now, not mid-sprint.

## What this command does

Conduct a structured Q&A with the user, working through four topic areas in
order. Each area is a focused round: ask the questions for that area, wait
for answers, follow up if answers raise new questions, then move on. Do not
dump all questions at once — ask 3–5 per round and surface follow-ups before
moving to the next area.

### Round 1 — Business logic & scope

Understand what the feature does and why it exists:
- What problem does this feature solve, and who has that problem?
- What does "done" look like? What can a user do after this ships that they
  can't do today?
- What is explicitly out of scope (what are we NOT building here)?
- Are there any edge cases or alternate flows in the happy path?
- Are there business rules that gate behavior (e.g. only paid users, only
  after X happens first)?

### Round 2 — UX & user flows

Understand how the user experiences the feature:
- Walk me through the step-by-step flow a user takes to use this feature.
- Are there multiple entry points? Multiple exit states?
- What happens in error or empty states?
- Is there any onboarding or first-time-use consideration?
- What feedback does the user see when an action succeeds or fails?

### Round 3 — Security & reliability

Surface constraints that affect how the feature must be built:
- Who can access this feature, and who must NOT be able to access it?
- Is there any sensitive data involved (PII, payment info, credentials)?
- What are the consequences of this feature failing or returning stale data?
- Are there rate limits, abuse vectors, or fraud risks to think about?
- Does this feature need to work offline or under degraded connectivity?

### Round 4 — Technical & integration constraints

Understand the technical envelope:
- Does this feature depend on or integrate with any third-party service or
  existing internal system?
- Are there hard technology constraints (must use X library, must match
  existing Y pattern, cannot change Z schema)?
- Are there performance or scale expectations beyond the obvious?
- Are there any deadlines, phasing needs, or incremental-launch requirements?

## When to continue asking

After each round, decide: is there anything in the answers that opened a new
question that belongs in this phase? If yes, ask it before closing the round.
Stop each round only when that topic area is fully clear.

If the user says "I don't know" or "doesn't matter" on a topic, record that
explicitly — it's a design decision (chosen to defer) and belongs in
`gather.md`.

## Wrapping up

After all four rounds, produce a brief plain-language summary:
- Feature name and one-sentence description
- Who it serves and the primary user flow
- What is out of scope
- Key constraints and decisions made
- Open questions or deferred decisions

Read this back to the user. Ask: "Does this capture everything, or is there
anything you want to add or correct?" Make any corrections, then write
`gather.md`.

## Output

Write `knowledge/requirements/<feature-folder>/gather.md` with the following
structure:

```markdown
# Gather: <Feature Name>

## Feature summary
<One paragraph: what it does, who it's for, why it exists>

## User flows
<Step-by-step description of the primary flow and any alternate flows>

## Scope boundaries
### In scope
- <item>
### Out of scope
- <item>

## Business rules
<Numbered list of rules that gate or constrain behavior>

## Security & reliability constraints
<Numbered list>

## Technical & integration constraints
<Numbered list>

## Key decisions made
<Decisions that were explicitly chosen during this conversation>

## Deferred / open questions
<Things the user said "doesn't matter yet" or that need follow-up later>
```

This file is the required input for `analyze.md` — do not let `analyze.md`
run without it existing and being non-empty.
