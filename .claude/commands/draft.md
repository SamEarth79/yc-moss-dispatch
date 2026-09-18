# draft.md

## Position in the framework

Step 3 of 4 in the `/design` workflow, invoked by `commands/design.md`.

- **Previous step**: `commands/analyze.md`. Its outputs are
  `knowledge/requirements/<feature-folder>/analysis.md`,
  `knowledge/requirements/<feature-folder>/architecture.md`, and a
  user-confirmed story list carried in conversation context.
- **This step**: write one story `.md` file per confirmed story, then create
  an Asana Epic task with subtasks for each story.
- **Next step**: `commands/review.md`, which presents the design to the user
  and loops on feedback.

## What this command does

### 1. Write story files

For each story in the confirmed list:

1. Read the feature's own number from the feature folder name (the `NNN` in
   `<PREFIX>-NNN-<slug>`) and `nextStoryNumber["<feature-folder>"]` from
   `knowledge/config.json`. Format each as 3 digits. Build the story code:
   `<PREFIX>-STORY-<feature-NNN>-<story-NNN>`.
2. Write `knowledge/requirements/<feature-folder>/stories/<STORY-CODE>.md`
   using `templates/story.md`:
   - Description (what this story delivers)
   - Acceptance criteria (observable, testable)
   - Which requirement areas from `gather.md` it addresses
   - Which agents it will need (frontend / backend / infrastructure)
   - `Depends on` field: list any story codes in this feature that must be
     committed before this one can start. Leave empty if independent — don't
     invent dependencies.
3. Increment `nextStoryNumber["<feature-folder>"]` in `knowledge/config.json`
   after each story is written.
4. Register each story in `knowledge/state.json`:
   `stories["<STORY-CODE>"] = { "status": "pending", "step": null, "commit": null }`.

### 2. Create Asana Epic and subtasks

After all story files are written:

**2a. Create the Epic task**

Use the `asana_create_task` MCP tool to create a task in the "Sprint backlog"
project (GID: `1216704733478132`, workspace: `slyce.store`,
workspace GID: `1216681525107044`):

- **Name**: `<FEATURE-FOLDER>: <short feature title>` (e.g.
  `LIB-001-user-auth: User Authentication`)
- **Notes**: paste the feature summary from `gather.md` (the one-paragraph
  description), followed by a blank line and the architecture approach from
  `architecture.md`'s opening section (2–3 sentences max)
- **Projects**: `["1216704733478132"]`

**2b. Create subtasks for each story**

For each story, use the `asana_create_subtask` MCP tool with the Epic task's
GID as the parent:

- **Name**: `<STORY-CODE>: <story title>` (e.g.
  `LIB-STORY-001-001: Add login form`)
- **Notes**: the full, verbatim body of the story's `.md` file (everything
  written in step 1 — description, acceptance criteria, requirement-area
  references, agents needed, `Depends on`) — not a summary. The Asana
  subtask must be a faithful mirror of the story file, since
  `/implement-epic` treats Asana as the authoritative story list and the
  subtask body may be someone's first look at the story.

**2c. Record Asana GIDs**

After creating the Epic and all subtasks, record the GIDs in
`knowledge/state.json` under the feature:

```json
"asana": {
  "epicGid": "<epic-task-gid>",
  "stories": {
    "<STORY-CODE>": "<subtask-gid>"
  }
}
```

This allows future commands (e.g. `/implement`) to update the Asana tasks
when stories are committed.

## Output

- `knowledge/requirements/<feature-folder>/stories/<STORY-CODE>.md` (one or
  more)
- `knowledge/config.json` updated with incremented story counters
- `knowledge/state.json` updated with `pending` story entries and Asana GIDs
- Asana Epic task + subtasks created in the Sprint backlog project

These are the required inputs for `review.md` — do not let `review.md` run
without all story files existing and Asana tasks created.
