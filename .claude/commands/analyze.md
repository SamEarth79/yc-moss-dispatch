# analyze.md

## Position in the framework

Step 2 of 4 in the `/design` workflow, invoked by `commands/design.md`.

- **Previous step**: `commands/gather.md`. Its output is
  `knowledge/requirements/<feature-folder>/gather.md`. Read that file before
  doing anything in this step.
- **This step**: analyze the codebase in light of the gathered requirements,
  produce `analysis.md` and `architecture.md`, then propose a story list to
  the user and get confirmation before proceeding. The codebase scan and
  analysis are done by six specialist agents in parallel (see step 3), not
  by this step alone — their job is to interrogate `gather.md` from
  different angles until thorough, not just summarize it.
- **Next step**: `commands/draft.md`, which reads the confirmed story list
  and writes one `.md` file per story, then creates Asana tickets.

## What this command does

### 1. Read gather.md

Read `knowledge/requirements/<feature-folder>/gather.md` in full. This is the
authoritative record of what was agreed during the gather conversation —
treat it as truth, not as a starting point to question.

### 2. Read strategy and prior architecture

- Read `knowledge/strategy.md` if it exists. Surface any conflict between
  the feature's direction and recorded strategic decisions before proceeding.
- Skim `architecture.md` of previously **implemented** features
  (`knowledge/requirements/*/architecture.md`, cross-checked against
  `knowledge/state.json`), including `## Deviations` sections — the real
  system is those documents plus their deviations.

### 3. Fan out to the six design specialists

Spawn all six agents in parallel, in a single batch (one message, six `Agent`
tool calls) so none of them see each other's output — independent lenses,
not a chain:

- `design-developer` (feasibility, reuse, data model/API surface,
  ops/scale)
- `design-ui-designer` (components, visual states, design-system fit)
- `design-ux-designer` (flow completeness, discoverability, accessibility)
- `design-security` (access control, sensitive data, abuse vectors, edge
  cases/failure modes — also holds the `architecture.md` sign-off gate, see
  step 5)
- `design-business` (business rules, monetization/tiering, compliance,
  success metrics)
- `design-outside-the-box` (assumptions, simpler alternatives, second-order
  effects)

Give each agent `gather.md`, `strategy.md`, the relevant prior
`architecture.md` files, and codebase read access — see each agent's own
file in `agents/` for what it specifically investigates and returns. Each
agent returns: a draft contribution to its section(s), and a list of
open/blocking questions.

### 4. Converge: one consolidated question round

Collect all six agents' question lists. Before asking the user anything:

- Merge/dedupe overlapping questions from different agents (e.g. if
  `design-security` and `design-business` both ask about PII retention,
  ask it once).
- Drop anything a different agent's draft already answered.
- Separate blocking questions (block finishing `analysis.md`/
  `architecture.md`) from non-blocking ones (nice to resolve, not gating).

Present the merged blocking questions to the user in one round, 3–5 at a
time in the same style as `gather.md`'s rounds — never run six separate
interrogations back to back. Route each answer back only to the agent(s)
whose question it resolves, so they can finalize their section. If an
answer opens a genuinely new blocking question, ask it before closing the
round; otherwise stop once blocking questions are resolved. Non-blocking
questions get folded into `analysis.md`'s "Open questions" section instead
of being asked live.

### 5. Fan in: write analysis.md and architecture.md

Write `knowledge/requirements/<feature-folder>/analysis.md` using
`templates/analysis.md` as the structure. Open with the verbatim feature
summary from `gather.md` so the agreed framing survives context loss.
Synthesize the six agents' contributions into one coherent document —
don't just concatenate six blocks; merge overlapping findings and cut
redundancy while keeping every genuinely distinct point. Include:
- Codebase findings from `design-developer` and `design-ui-designer`
- Constraints and risks from all six lenses (UX gaps, security/abuse,
  business/compliance, assumptions surfaced by `design-outside-the-box`)
- How this feature relates to prior features already implemented
- Remaining non-blocking open questions

Then write `knowledge/requirements/<feature-folder>/architecture.md` using
`templates/architecture.md`, based on `design-developer`'s draft
(Approach, Components touched, Data flow, Data model changes, API surface,
Key decisions). **Before writing it to disk, send the draft to
`design-security` for sign-off** (see its "Sign-off" section in
`agents/design-security.md`). If it flags something, send the specifics
back to `design-developer` for a revision and repeat until `design-security`
approves — `architecture.md` is not finalized without that approval.

### 6. Propose stories and get confirmation

Break the feature into stories based on `gather.md`'s scope and the
architecture just written — draw on all six lenses for splits (e.g. a UX
gap becomes its own story, an abuse vector `design-security` flagged
becomes a rate-limiting story, a tier-gating rule from `design-business`
becomes its own story):

- Stories must be small enough to be independently implementable and testable.
- Split "backend endpoint" and "frontend form" into separate stories if either
  can ship/test independently; keep them together only if tightly coupled.
- For each proposed story, provide:
  - Story code (will be finalized when `draft.md` writes the file)
  - Short title (one line)
  - One-sentence description of what it delivers
  - Which agents it will need (frontend / backend / infrastructure)
  - Any dependencies on other stories in this list

Present the story list clearly to the user — not a wall of text, just the
code, title, and one-sentence description per story, with dependencies noted.

Ask: "Does this story breakdown look right? Any stories to add, remove, or
split differently?"

Wait for explicit confirmation before calling `draft.md`. If the user wants
changes, update the proposal and re-present until confirmed.

## Output

- `knowledge/requirements/<feature-folder>/analysis.md`
- `knowledge/requirements/<feature-folder>/architecture.md`
- A confirmed story list in conversation context, passed to `draft.md`

These are required inputs for `draft.md` — do not let `draft.md` run without
both files existing and the user having explicitly confirmed the story list.
