# MOS-STORY-001-003: Index selector + grouped documents view

> Filled in by `draft.md` during `/design`. One file per story, inside the
> feature's `stories/` directory.

## Description

As a developer managing Moss index content, I want a new screen where I
can pick an index and see its chunks grouped into a documents view, so
that I can browse existing content before editing it.

## Acceptance criteria

1. A new page (`backend/static/manage.html` + `manage.js`) is served
   alongside the existing dispatch UI, styled per `DESIGN.md` tokens
   only (reusing `.panel`, `.caller-select`, `.badge`, `.status`/`.dot`
   classes — no new colors/spacing/radii invented).
2. `index.html`'s header gets a clearly labeled nav link ("Manage
   Indexes") to the new page; the new page's header links back
   ("Dispatch Copilot").
3. On load, the page fetches `GET /api/indexes` and populates an index
   selector; if the list is empty, the selector is disabled and shows
   "No indexes available" with no crash.
4. If `GET /api/indexes` fails, an error banner is shown with a "Retry"
   action; the page does not hang on an indefinite loading state.
5. Selecting an index fetches `GET /api/indexes/{name}/docs` and shows a
   loading state while the request is in flight.
6. Chunks are grouped client-side using this precedence per index: if
   any chunk has `metadata.sourceDoc`, group by `sourceDoc`; else if any
   chunk has `metadata.type`, group by `type`; else all chunks fall into
   a single "Ungrouped" bucket. Verified against real data:
   `protocol-index` groups by `sourceDoc`, `facility-index` and
   `live-data-index` group by `type`.
7. An index with zero chunks shows an empty state ("No documents in this
   index yet") rather than an empty blank area.
8. Document groups render as collapsible cards (first expanded by
   default, rest collapsed), each showing a chunk-count badge; a group
   with many chunks scrolls internally past a max-height rather than
   growing the page unboundedly.
9. Each chunk row shows its `id` (monospace), its text (clamped to 3
   lines with a "Show more" toggle for longer text), and its metadata
   rendered as key:value chips.
10. All interactive elements (selector, expand/collapse, "Show more")
    are keyboard-operable and properly labeled (native `<select>`,
    real `<button>` elements, no unlabeled click-only `<div>`s).

## Requirements implemented

- `gather.md` User flows — steps 1–3
- `architecture.md` Data flow steps 1–2, Wireframe, Key decisions
  (grouping-key fallback)
- UX findings: loading/empty/error states, accessibility basics for the
  read-only view

## Depends on

- MOS-STORY-001-001

## Agents likely needed

- [x] frontend
- [ ] backend
- [ ] infrastructure

## Status

- [ ] Implemented
- [ ] Tested
- [ ] Committed
