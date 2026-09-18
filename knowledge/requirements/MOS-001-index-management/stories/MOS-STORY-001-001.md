# MOS-STORY-001-001: Index list + chunk read endpoints

> Filled in by `draft.md` during `/design`. One file per story, inside the
> feature's `stories/` directory.

## Description

As a developer managing Moss index content, I want backend endpoints that
list all indexes and return all chunks in a given index, so that the
management screen has data to render.

## Acceptance criteria

1. `GET /api/indexes` returns `200` with a JSON array of
   `{name, docCount, status, model, updatedAt}` for every index returned
   by `moss_client.list_indexes()`.
2. `GET /api/indexes/{name}/docs` returns `200` with a JSON array of
   `{id, text, metadata}` for every chunk in the named index, via
   `moss_client.get_docs(name)`.
3. `GET /api/indexes/{name}/docs` returns `404` with a clear error body
   when `name` does not correspond to an existing index.
4. Both endpoints reuse the module-level `moss_client` instance already
   constructed in `server.py`'s `lifespan()` — no second `MossClient` is
   created.
5. Errors from the Moss SDK (network/timeout/unexpected) are caught at
   the route boundary and returned as a `5xx` with a safe (non-leaking)
   error message, never an unhandled exception/stack trace to the client.

## Requirements implemented

- `gather.md` User flows — steps 1–3 (select index, load its chunks)
- `gather.md` Technical & integration constraints #1 (reuse
  `MossClient`/FastAPI stack)
- `architecture.md` API surface — `GET /api/indexes`,
  `GET /api/indexes/{name}/docs`

## Depends on

-

## Agents likely needed

- [ ] frontend
- [x] backend
- [ ] infrastructure

## Status

- [ ] Implemented
- [ ] Tested
- [ ] Committed
