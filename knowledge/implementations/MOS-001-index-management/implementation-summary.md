# Implementation Summary — MOS-001-index-management

## MOS-STORY-001-001: Index list + chunk read endpoints

Added two read-only endpoints to the backend server: one that lists all
Moss indexes with their name, chunk count, status, embedding model, and
last-updated time, and one that returns every chunk (id, text, metadata)
in a given index. Both reuse the server's existing shared Moss client
rather than creating a new connection. Errors are handled so that a
missing index returns a clear "not found" response and any unexpected
failure returns a generic server error without leaking internal details.
Tested with a fake stand-in for the Moss client so the tests don't depend
on real cloud credentials or network access. This is the foundation the
next stories build on: the mutation endpoints (add/update/delete) and the
frontend screen that displays this data.

## MOS-STORY-001-003: Index selector + grouped documents view

QA pass over the new `backend/static/manage.html` + `manage.js` screen.
Established Playwright-based E2E test infrastructure for this project
(none existed before): `backend/tests/e2e/conftest.py` runs a stub FastAPI
app in a background thread that serves the real static files and mirrors
the two endpoints from MOS-STORY-001-001 with fixture data instead of a
real Moss client, so Playwright can drive the actual page over HTTP
without needing MOSS_PROJECT_ID/MOSS_PROJECT_KEY or network access.
`pytest-playwright` was added as a dev dependency (Python bindings, kept
consistent with the existing pytest setup — no separate Node/npm
toolchain introduced) and the Chromium browser binary was installed.

Five E2E tests were written in `backend/tests/e2e/test_manage_page.py`
covering the golden path (index selection, grouping by `sourceDoc`,
expand/collapse state, chunk id/text/metadata rendering), the `type`
grouping fallback, an empty-chunks index, an empty index list, and an
`/api/indexes` failure with retry. Three passed; two failed.

The two failures are not test-authoring issues — they exposed a real
frontend bug: `style.css`'s `.error-banner { display: flex; }` rule has
no `[hidden]` override, and an author CSS rule always overrides the
browser's default `[hidden] { display: none }` behavior. As a result the
error banner never actually hides — it's present in the DOM with
`display: flex` regardless of the `hidden` attribute `manage.js` sets and
clears. This was confirmed directly (`getComputedStyle` reports `flex`
while `hasAttribute('hidden')` is `true`) and affects both the
empty-index-list state and the retry-after-failure flow (AC3/AC4). This
was not fixed by QA — it's surfaced for `frontend` to address (e.g. add
`.error-banner[hidden] { display: none; }`).

The pure "Ungrouped" branch of AC6's grouping precedence (no
`sourceDoc`/`type` on any chunk) is implemented but not covered by any
test — flagged as a gap to close once the CSS bug above is fixed and this
story is re-tested.

The bug was fixed by adding an explicit `[hidden]` override for the error
banner in `style.css`. Re-running the full suite afterward showed all 10
tests passing, with no regression to the MOS-STORY-001-001 endpoint tests.

Full detail, command output, and per-test AC mapping are in
`test-results.md`'s `MOS-STORY-001-003` section. Overall verdict: PASS.

## MOS-STORY-001-002: Chunk mutation endpoints + live-reload

QA pass over the new `POST`/`PUT`/`DELETE /api/indexes/{name}/docs[/...]`
endpoints and the shared `_reload_if_live` helper in `backend/server.py`.
15 feature tests were appended to `backend/test_server.py` (no new unit
or E2E layer required — see rationale below), covering all 7 acceptance
criteria: successful add/update/delete and their response shapes;
reload-on-mutation firing exactly once for both live-loaded index names
across all three verbs, and explicitly *not* firing for any other index
name; boundary validation (empty `id`, empty `text`, `metadata` as an
array, `metadata` as a string, each rejected with 422 before `add_docs`
is ever called); a mutation failure returning a safe 500 with the reload
step skipped; and upsert-by-id semantics.

The upsert-by-id test (AC7) needed more than the `SimpleNamespace` +
`AsyncMock` pattern used everywhere else in this file, since proving
"still only one chunk exists, now with updated text" requires the fake
client to actually remember state across two calls. A small stateful fake
(`_StatefulFakeMossClient`, a dict keyed by doc id backing `add_docs`/
`get_docs`) was added for that one test so the assertion goes through the
real `GET /api/indexes/{name}/docs` route rather than inspecting mock
call arguments.

No unit-test layer was added, for the same reason as
MOS-STORY-001-001: these are thin route/orchestration handlers over the
Moss SDK, and a unit test would just re-isolate the same conditional and
object-construction logic the feature tests already exercise through the
real routes. No new E2E layer was added either — this story has no new
UI surface — but the existing MOS-STORY-001-003 E2E suite
(`tests/e2e/test_manage_page.py`) was re-run in full as a regression
check, since it drives `server.py`'s static/read routes in the same
process this story's new mutation routes live in.

All tests pass: `test_server.py` 20/20 (5 pre-existing + 15 new),
`tests/e2e/test_manage_page.py` 5/5, no regressions. No implementation
bugs were found in this story's code; nothing was surfaced back to
`backend`.

Full detail, exact commands, and per-test AC mapping are in
`test-results.md`'s `MOS-STORY-001-002` section. Overall verdict: PASS.
