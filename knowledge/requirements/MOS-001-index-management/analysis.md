# Analysis: Index Management Screen

## Summary

A new admin screen (second page, vanilla JS/HTML/CSS, no auth) for full CRUD
on Moss vector-index chunks (`DocumentInfo`: id, text, metadata), grouped
into a "documents" view, reached from the existing dispatch simulator UI.

## Relevant existing code

- `backend/server.py` — the only FastAPI app in the project. Builds one
  global `MossClient` in `lifespan()` and calls
  `load_indexes([PROTOCOL_INDEX_NAME, LIVE_DATA_INDEX_NAME])` at startup;
  mounts `backend/static` at `/`. New routes belong here, reusing the
  module-level `moss_client` — never construct a second client.
- `backend/build_protocol_index.py`, `build_facility_docs.py`,
  `build_live_data_index.py` — the only existing way to populate index
  content today: hand-edit a Python dict, rerun a script that deletes and
  recreates the whole index via `create_index`. This screen replaces that
  workflow for incremental edits.
- `backend/protocol_chunks.py`, `facility_chunks.py`, `incident_chunks.py`
  — actual chunk data. **`sourceDoc` is only present in
  `protocol_chunks.py` (10/10 chunks)** — `facility_chunks.py` and
  `incident_chunks.py` have zero `sourceDoc` usage and instead carry a
  `type` field (`facility`/`incident`). Confirmed by direct grep, not
  inferred.
- `backend/static/index.html`, `app.js`, `style.css` — existing frontend
  conventions: no framework, one script per page, WebSocket for the live
  panel, no existing fetch/REST pattern (this feature introduces the
  first one), no modal/form/accordion/key-value-editor components yet.
  `DESIGN.md`-derived classes to reuse directly: `.panel`, `.panel h2/h3`,
  `.caller-select`, `.transcript-input`, `.action-button` /
  `.action-button.none`, `.badge`/`.badge.p1-3`, `.status`/`.dot`.
- `backend/.venv/.../moss/client/moss_client.py` — `MossClient` wraps two
  independent objects: `self._manage` (cloud-side `ManageClient` — used by
  `add_docs`, `delete_docs`, `get_docs`, `list_indexes`, `get_index`) and
  `self._manager` (local `IndexManager` — used by `query`, `load_index`,
  `has_index`). No code path connects them.
- `moss_core.GetDocumentsOptions` has no pagination field (`doc_ids`,
  `filter`, `sort_by`, `ascending`, `group_by` only) — `get_docs` is
  load-all, no paging primitive exists.
- `moss_core.IndexInfo` exposes `doc_count` — the index selector can show
  a chunk count without a full `get_docs` call.
- `moss_core.MutationOptions(upsert=None)` / `DocumentInfo(id, text,
  metadata=None, embedding=None, payload=None)` — confirmed shapes.

## Constraints and risks

- **Confirmed: mutations don't reach the in-memory query copy.**
  `add_docs`/`delete_docs` only touch the cloud-side `ManageClient`; the
  `IndexManager` copy loaded at startup for `PROTOCOL_INDEX_NAME` and
  `LIVE_DATA_INDEX_NAME` is untouched until `load_index` runs again.
  Without a fix, edits made in this screen would not appear in the live
  dispatch demo's query results. **Decision**: every mutation endpoint
  calls `load_index(name)` synchronously (before responding) when `name`
  is one of the app's live-loaded indexes, so the demo never serves stale
  results after an edit. Indexes are demo-scale, so the added latency is
  acceptable.
- **No partial metadata patch** — `add_docs` is a full-document upsert.
  Editing one metadata field means resending the whole chunk (fetch,
  merge client-side or require full submission, then upsert).
- **`sourceDoc` grouping only works for one of three indexes** (resolved
  live with the user — see Key decisions below).
- No pagination on `get_docs`: fine at current index sizes (tens to a
  few hundred chunks); would need revisiting if any index grows into the
  thousands. Not blocking for this pass.
- No existing modal/form/accordion/destructive-action visual pattern in
  `style.css` — all net-new, constrained to `DESIGN.md`'s existing
  radius/spacing/color tokens rather than inventing new ones (see
  `architecture.md` for the concrete wireframe).
- No user attribution possible on chunk mutations (no auth) — acceptable
  for a single-operator demo tool per `design-business`'s finding; not a
  gap worth addressing in this pass.
- Content entered through this screen is free-form (unlike the existing
  build scripts, which only ever write pre-vetted source text). The
  indexed content today is public-sourced (MedlinePlus-derived protocol
  text, NY DOH facility directory) with no PII. `design-business` flagged
  as non-blocking: since `live-data-index` is earmarked for
  incident/caller-adjacent data per `Plan.md`, free-text entry there
  could introduce PII later if misused — no gate needed now, just noted.
- Accessibility, error-recovery, and interaction-feedback requirements
  (from `design-ux-designer`) are concrete enough to fold directly into
  story acceptance criteria — see `architecture.md` and the story list.

## How this relates to prior features

None — this is the first feature designed in this repo (`knowledge/`
created for this `/design` run). No `strategy.md` exists yet either;
`design-business` confirmed its absence rather than inferring direction.

## Open questions (non-blocking, resolved pragmatically for this pass)

- Whether a lighter-weight tool (CLI/script-based editing) would serve
  this audience (the app's own developers) better than a full web UI —
  raised by `design-outside-the-box`. Not pursued: the demo context
  favors a visible, in-app "index management" screen, and the user
  confirmed the direction in `gather.md`. Worth remembering if this
  screen sees little real use.
- Whether bulk "replace all chunks for a document" belongs alongside
  one-chunk-at-a-time CRUD, matching how indexes are actually
  regenerated today (whole source file → whole rebuild). Deferred to a
  future iteration; this pass ships per-chunk CRUD only, per `gather.md`.
- Whether a short-lived "undo" affordance after delete is worth adding
  given there's no confirm dialog — flagged by `design-ux-designer` as a
  cheap risk-reducer, not required for this pass.
- Whether a "reset index to source-file state" action is needed so the
  Python files and live index content don't silently drift apart —
  flagged by `design-outside-the-box`, out of scope for this pass.
