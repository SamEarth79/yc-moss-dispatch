# MOS-STORY-001-002: Chunk mutation endpoints + live-reload

> Filled in by `draft.md` during `/design`. One file per story, inside the
> feature's `stories/` directory.

## Description

As a developer managing Moss index content, I want endpoints to add,
update, and delete a chunk, so that I can change index content without
hand-editing a Python file and rerunning a rebuild script — and so that
changes are immediately visible to the live dispatch demo, not just the
cloud copy.

## Acceptance criteria

1. `POST /api/indexes/{name}/docs` accepts `{id, text, metadata}`, calls
   `moss_client.add_docs(name, [DocumentInfo(id, text, metadata)])`, and
   returns `200` with `{id}` on success.
2. `PUT /api/indexes/{name}/docs/{doc_id}` accepts `{text, metadata}`,
   builds a `DocumentInfo(id=doc_id, text, metadata)`, calls `add_docs`
   (upsert-by-id), and returns `200` with `{id}` on success.
3. `DELETE /api/indexes/{name}/docs/{doc_id}` calls
   `moss_client.delete_docs(name, [doc_id])` and returns `204` on
   success.
4. After any successful `add_docs`/`delete_docs` call where `name` is
   `PROTOCOL_INDEX_NAME` or `LIVE_DATA_INDEX_NAME`, the endpoint calls
   `await moss_client.load_index(name)` before responding, so the
   in-memory copy used by live queries reflects the change. This reload
   is implemented once as a shared helper, not duplicated across the
   three endpoints.
5. Request bodies are validated at the boundary: `id`/`text` non-empty
   strings, `metadata` constrained to a JSON object (reject arrays/
   scalars) — per `rules/coding-style.md` §7 and `rules/security.md` §6.
6. A failure from the Moss SDK during a mutation (network/timeout/
   unexpected) is caught and returned as a `5xx` with a safe error
   message; the in-memory reload step is skipped/not attempted if the
   mutation itself failed.
7. Adding a chunk with an `id` that already exists in the index updates
   it in place (per `add_docs` upsert semantics) rather than creating a
   duplicate — verified by a feature test that adds, then re-adds with
   the same id and different text, and confirms only one chunk exists
   with the updated text.

## Requirements implemented

- `gather.md` Business rules #2 (add with existing id updates in place)
- `gather.md` User flows — steps 4–5 (add/edit/delete)
- `architecture.md` Data flow steps 3–5, Key decisions (synchronous
  reload-on-mutation for live-loaded indexes)

## Depends on

- MOS-STORY-001-001

## Agents likely needed

- [ ] frontend
- [x] backend
- [ ] infrastructure

## Status

- [x] Implemented
- [x] Tested
- [x] Committed
