# Gather: Index Management Screen

## Feature summary
A new admin screen for directly managing the content of Moss vector indexes
used by the dispatch-copilot demo (protocol-index, live-data-index, facility
indexes, etc.). Today the only way to populate or change index content is
running one-off build scripts (`build_protocol_index.py`,
`build_facility_docs.py`, ...). This screen gives a UI to select an index,
browse its documents/chunks, and add, edit, or delete them directly — a
second screen alongside the existing live dispatch simulator UI
(`backend/static/index.html`).

## User flows

### Primary flow
1. User opens the index management screen (new page under `backend/static`,
   linked from or alongside the existing dispatch UI).
2. User selects an index from a list of all indexes (via `list_indexes`).
3. Screen loads all chunks in that index (via `get_docs`) and groups them
   client-side by their `metadata.sourceDoc` field into a "documents" view
   — each group is a source document, its members are the chunks belonging
   to it.
4. User can:
   - Add a new chunk to an existing document group, or start a new document
     group (new `sourceDoc` value) with one or more chunks.
   - Edit an existing chunk's text and/or metadata fields.
   - Delete a chunk.
5. Mutations go through `add_docs` (create/update by `id`) and `delete_docs`
   (by `id`), matching the SDK's existing chunk-as-document model — no new
   chunking abstraction is introduced.

### Alternate/secondary flows
- Selecting an index with zero documents shows an empty state with a
  prompt to add the first chunk/document.
- Chunks with no `metadata.sourceDoc` set fall into an "ungrouped" bucket
  in the documents view rather than being hidden.

## Scope boundaries

### In scope
- Index selector (all indexes, via `list_indexes`).
- Documents view: chunks grouped by `metadata.sourceDoc`.
- Add chunk (new or into existing document group).
- Edit chunk text + metadata.
- Delete chunk.
- Empty/error states for the above.

### Out of scope
- Security/access-control review (explicitly skipped for this pass).
- Any new chunk-splitting logic — chunks stay exactly as the SDK's
  `DocumentInfo` (id, text, metadata); the UI does not auto-chunk pasted
  long text into multiple chunks.
- Web source management (`create_web_source` etc.) — separate feature.
- Index creation/deletion (only chunk-level CRUD within an existing index).
- Job status / async polling UI for `create_index_from_files`-style bulk
  operations.

## Business rules
1. A "document" in the UI is a derived grouping (by `metadata.sourceDoc`),
   not a first-class Moss SDK concept — the SDK's atomic unit is the chunk
   (`DocumentInfo`).
2. Adding a chunk with an `id` that already exists in the index updates it
   in place (per `add_docs` semantics) rather than creating a duplicate.

## Security & reliability constraints
(Not reviewed in this pass, per explicit request — flagged as an open item
below rather than silently decided.)
1. No authentication/access control on this screen for this pass.
2. No confirmation dialog before delete for this pass.

## Technical & integration constraints
1. Must match the existing stack: vanilla JS/HTML/CSS served as static
   files from `backend/static`, with new FastAPI routes in `backend/server.py`
   calling `MossClient` (`add_docs`, `get_docs`, `delete_docs`,
   `list_indexes`).
2. Must follow `DESIGN.md` (Linear-style dark UI tokens) for all new UI.
3. No new third-party frontend framework/library.

## Key decisions made
- Screen scope: full CRUD (add, update, delete, view), not read-only or
  add-only.
- Chunk granularity: chunks are exposed and directly editable (not hidden
  behind a document-only abstraction) — confirmed after inspecting
  `moss_core`'s public API, which has no separate document/chunk split;
  `DocumentInfo` (id, text, metadata) is the SDK's only atomic unit, and
  existing app code (`protocol_chunks.py`) already uses `metadata.sourceDoc`
  as the document-grouping key.
- Index scope: selectable across all indexes, not hard-coded to one.
- No security/auth work in this pass (explicit user instruction).

## Deferred / open questions
- Whether a currently loaded (in-memory) index needs an explicit reload
  (`load_index`) after a mutation (`add_docs`/`delete_docs`) for `query()`
  to see the change, or whether this needs to be surfaced/handled in the
  UI (e.g. a "changes may take a moment to reflect in live queries" notice).
  To be resolved during `analyze.md`.
- Exact layout/component structure — to be proposed as a wireframe in
  `architecture.md` and reviewed with the user before implementation.
