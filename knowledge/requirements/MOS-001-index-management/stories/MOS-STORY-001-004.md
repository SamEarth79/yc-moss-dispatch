# MOS-STORY-001-004: Add/edit/delete chunk UI

> Filled in by `draft.md` during `/design`. One file per story, inside the
> feature's `stories/` directory.

## Description

As a developer managing Moss index content, I want to add, edit, and
delete chunks directly from the documents view, so that I can change
index content without leaving the browser.

## Acceptance criteria

1. A "+ New Document" action (top bar) and a "+ Add chunk" action (per
   document group) open an inline form (no modal) with fields for chunk
   id (required for add, disabled/fixed for edit), text (textarea), and
   a dynamic metadata key/value list with add-field and remove-field
   controls. "+ New Document" additionally includes the grouping field
   (e.g. `sourceDoc`) for the new group.
2. Saving an add/edit form calls the corresponding backend endpoint
   (`POST`/`PUT` from MOS-STORY-001-002); on success the chunk appears
   in the correct group immediately and a success indicator (toast or
   inline confirmation) is shown, announced via `aria-live="polite"` for
   screen readers.
3. Adding a chunk with an `id` that already exists in the selected index
   shows an indication that this was an update, not a new addition
   (e.g. "Updated existing chunk" vs. "Added new chunk").
4. After a successful add, the form clears its text field but keeps the
   index/group context, so adding several chunks to the same document in
   a row doesn't require re-selecting anything.
5. A "Cancel" action discards in-progress add/edit input without saving
   and returns focus to the control that opened the form.
6. Deleting a chunk (ghost "Delete" action, muted by default, coral-red
   only on hover — no confirmation dialog, per explicit decision) calls
   `DELETE` from MOS-STORY-001-002; the chunk is removed from the view
   only after the server confirms success (never optimistically), and a
   toast names what was deleted (id + first words of text), announced
   via `aria-live` for screen readers.
7. If a save (add/edit) call fails, the form stays populated with the
   user's input (nothing is lost) and an inline error message explains
   the failure in plain language, with a way to retry the same submission.
8. If a delete call fails, the chunk remains visible in the list (not
   removed) and an inline/toast error is shown.
9. Editing a chunk's grouping field (`sourceDoc` or `type`) and saving
   moves it to the correct (possibly new) group in the rendered view.
10. All add/edit/delete controls and dynamically-added metadata rows are
    keyboard-operable, individually labeled (e.g. `aria-label="Metadata
    key 3"`), and manage focus correctly when a form opens/closes.

## Requirements implemented

- `gather.md` User flows — steps 4–5 (add/edit/delete), Business rules #2
- `architecture.md` Data flow steps 3–5, Key decisions (no optimistic
  delete, inline forms, arbitrary metadata editing)
- UX findings: success/error feedback, accessibility, error recovery,
  no-confirm-dialog mitigation via toast feedback

## Depends on

- MOS-STORY-001-002
- MOS-STORY-001-003

## Agents likely needed

- [x] frontend
- [ ] backend
- [ ] infrastructure

## Status

- [x] Implemented
- [x] Tested
- [x] Committed
