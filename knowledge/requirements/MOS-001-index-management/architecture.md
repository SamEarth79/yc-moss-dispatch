# Architecture: Index Management Screen

> `design-security` review was explicitly skipped for this pass per user
> instruction (quick pass, no security review needed). This document has
> **not** received a security sign-off.

## Approach

Add a small set of REST endpoints to `server.py` that thinly wrap existing
`MossClient` calls (`list_indexes`, `get_docs`, `add_docs`, `delete_docs`),
plus a reload step for the app's two live-loaded indexes. Add a second
static page (`backend/static/manage.html` + `manage.js`, linked from
`index.html`'s header) that lets the user pick an index, view its chunks
grouped into a documents view, and add/edit/delete chunks inline. No new
data model or SDK abstraction — the UI operates directly on
`DocumentInfo`-shaped chunks.

Grouping key is **not** uniformly `metadata.sourceDoc`: only
`protocol-index` populates that field. For indexes without it, the UI
groups by `metadata.type` instead (confirmed: `facility-index` and
`live-data-index` both carry `type: "facility"`/`"incident"`). Per-index
grouping key resolution: prefer `sourceDoc` if any chunk in the index has
it, otherwise fall back to `type`, otherwise fall back to a single
"Ungrouped" bucket.

The one design decision this pass resolves is reload-on-mutation: since
`add_docs`/`delete_docs` mutate only the cloud-side copy and live queries
run against the separately-loaded in-memory copy, every mutation to
`PROTOCOL_INDEX_NAME` or `LIVE_DATA_INDEX_NAME` is followed server-side by
`moss_client.load_index(name)` before the endpoint responds, so the
dispatch demo never serves stale results after an edit made here.

## Components touched

- **Frontend**: new `backend/static/manage.html`, `backend/static/manage.js`,
  styles extended in `backend/static/style.css` (or a new `manage.css`)
  using only `DESIGN.md` tokens. A nav link added to `index.html`'s
  `<header>` ("Manage Indexes").
- **Backend**: new routes added directly to `server.py` (small enough not
  to warrant a router module — five endpoints), reusing the module-level
  `moss_client`.
- **Infrastructure**: none — no new services, env vars, or dependencies.

## Data flow

1. **List indexes** — page load → `GET /api/indexes` →
   `moss_client.list_indexes()` → `[{name, docCount, status, model,
   updatedAt}]` → populate index selector.
2. **View chunks, grouped** — user selects an index → `GET
   /api/indexes/{name}/docs` → `moss_client.get_docs(name)` (load-all) →
   `[{id, text, metadata}]` → client resolves the grouping key for this
   index (`sourceDoc` → `type` → "Ungrouped") and groups accordingly →
   renders document-group cards, each listing its member chunks.
3. **Add chunk** — user fills id/text/metadata (including the grouping
   field to join an existing or new group) → `POST
   /api/indexes/{name}/docs` `{id, text, metadata}` → server calls
   `add_docs(name, [DocumentInfo(...)])`; if `name` is live-loaded, server
   then calls `load_index(name)` before responding → client inserts the
   chunk into its local grouped view and shows a success indicator.
4. **Edit chunk** — user edits text/metadata (including adding/removing
   arbitrary metadata keys, or changing the grouping field to move the
   chunk to a different group) → `PUT
   /api/indexes/{name}/docs/{docId}` with the full `{text, metadata}` →
   server builds `DocumentInfo(id=docId, text, metadata)`, calls
   `add_docs` (upsert-by-id) → same live-index reload as step 3.
5. **Delete chunk** — user deletes a chunk (no confirm dialog, per
   explicit decision) → `DELETE /api/indexes/{name}/docs/{docId}` →
   server calls `delete_docs(name, [docId])` → same live-index reload as
   step 3 → client removes it from the rendered group (only after the
   call succeeds — never optimistically) and shows a toast naming what
   was deleted.

## Data model changes

None. Reuses `DocumentInfo` (`id`, `text`, `metadata`) exactly as the SDK
defines it. The "document" grouping is a derived, client-side-only view
over `metadata.sourceDoc` or `metadata.type` — no new field, table, or
schema, and no change to how `build_*_index.py` scripts populate data.

## API surface

```
GET  /api/indexes
  -> 200: [{ "name": str, "docCount": int, "status": str, "model": str, "updatedAt": str }]

GET  /api/indexes/{name}/docs
  -> 200: [{ "id": str, "text": str, "metadata": dict }]
  -> 404 if index doesn't exist

POST /api/indexes/{name}/docs
  body: { "id": str, "text": str, "metadata": dict }
  -> 200: { "id": str }
  -> reloads index in-memory if name in {PROTOCOL_INDEX_NAME, LIVE_DATA_INDEX_NAME}

PUT  /api/indexes/{name}/docs/{doc_id}
  body: { "text": str, "metadata": dict }
  -> 200: { "id": str }
  -> same reload rule as POST

DELETE /api/indexes/{name}/docs/{doc_id}
  -> 204
  -> same reload rule as POST
```

All request bodies validated at the boundary (non-empty `id`/`text`,
`metadata` constrained to a JSON object) per `rules/coding-style.md` §7
and `rules/security.md` §6.

## Wireframe

**Page regions (top to bottom):**

1. **Header bar** (reuse `index.html`'s `<header>` pattern) — left: page
   title "Index Management" + nav link back to "Dispatch Copilot"; right:
   index-load status dot + label.
2. **Index selector bar** — full-width `.panel` strip: "Index" label +
   `<select>` (styled as `.caller-select`) listing all indexes + a neutral
   `.badge` showing document/chunk counts + right-aligned acid-lime
   "+ New Document" button (the screen's one primary CTA).
3. **Main content area** (max-width 1200px, single column) — a list of
   document-group cards (`.panel`, accordion-style, first expanded by
   default, rest collapsed). Each header: chevron + group name (grouping
   value, or "Ungrouped") + chunk-count badge + ghost "+ Add chunk"
   button. Expanded body: vertical list of chunk rows (subtle nested
   card), each showing: monospace chunk id, text (clamped to 3 lines with
   "Show more"), metadata rendered as wrapped `key: value` chips, and
   ghost "Edit"/"Delete" actions (Delete muted by default, coral-red only
   on hover — the only concession to safety given no confirm dialog).
4. **Add/Edit chunk form** — inline expansion within the document card
   (no modal component exists in this app), with fields for id (disabled
   when editing), text (textarea), and a dynamic metadata key/value list
   (add-field / remove-field controls), ending in acid-lime "Save" +
   ghost "Cancel".

**Visual states covered**: zero indexes, index/chunk loading, empty
index (with CTA), populated, many-chunks-in-a-group (internal scroll),
long chunk text (clamp + expand), ungrouped bucket, add/edit forms open,
load error (banner, non-destructive — existing data stays visible),
mutation error (form stays populated, nothing removed optimistically),
add/edit/delete success (toast or inline confirmation, screen-reader
announced via `aria-live`).

Full detail (exact classes, tokens, and per-state layout) captured for
`draft.md` to turn into story acceptance criteria.

## Key decisions

- **Decision**: Group chunks by `sourceDoc` when present, else `type`,
  else "Ungrouped" — not a single universal grouping key.
  **Rationale**: verified `sourceDoc` only exists in `protocol_chunks.py`
  (10/10 chunks); `facility_chunks.py` (~220 chunks) and
  `incident_chunks.py` have none and would otherwise collapse into one
  meaningless "ungrouped" bucket, defeating the documents view for two
  of the three indexes. Resolved directly with the user.
- **Decision**: mutation endpoints synchronously reload the in-memory
  index copy for `PROTOCOL_INDEX_NAME`/`LIVE_DATA_INDEX_NAME` after a
  successful `add_docs`/`delete_docs`. **Rationale**: confirmed by code
  inspection that the SDK's cloud-mutation path and local-query path are
  fully decoupled; without this, edits would silently not appear in the
  live dispatch demo. Synchronous (not fire-and-forget) so there's no
  window where a query can race a just-made edit; acceptable given
  demo-scale index sizes.
- **Decision**: no optimistic UI updates on delete — wait for the server
  response before removing a chunk from the view. **Rationale**: with no
  confirm dialog, an optimistic removal that later fails would leave the
  user believing a delete succeeded when it didn't, with no way to tell.
- **Decision**: inline add/edit forms, not a modal. **Rationale**: no
  modal/overlay component exists anywhere in the current app; inline
  keeps the interaction consistent with the existing "everything lives in
  a panel" structure and avoids inventing a new interaction pattern for
  one screen.
- **Decision**: full CRUD ships at chunk (not bulk/document) granularity
  in this pass, even though `design-outside-the-box` noted that bulk
  "replace all chunks for a document" better matches how content is
  actually regenerated today. **Rationale**: matches the explicit scope
  confirmed in `gather.md`; bulk replace is recorded as a deferred
  follow-up in `analysis.md`, not built now.
