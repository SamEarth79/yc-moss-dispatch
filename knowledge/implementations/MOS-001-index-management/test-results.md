# Test Results — MOS-001-index-management

## MOS-STORY-001-001

Command: `cd backend && .venv/bin/python -m pytest test_server.py -v`

Result: 5 passed, 0 failed, 1 warning (unrelated `anyio.abc.BlockingPortal`
deprecation warning from Starlette's TestClient, not from this story's code).

### Layers

- **Unit tests: none written.** This story is a thin route/mapping layer
  over an already-tested Moss SDK (`list_indexes`, `get_index`, `get_docs`).
  A unit test would isolate the same dict-comprehension mapping that the
  feature tests below already exercise through the real route (request →
  handler → response body), so a separate unit layer would just re-assert
  the same logic through a narrower lens. Per `rules/testing.md`'s carve-out
  ("not required for trivial pass-through code"), feature-level tests are
  the right and sufficient layer here.
- **Feature tests: 5 written, 5 passed**, in `backend/test_server.py`, using
  Starlette's `TestClient` against the real FastAPI app and routes, with
  `server.moss_client` monkeypatched to a `SimpleNamespace` carrying
  `AsyncMock` methods. No real Moss credentials or network calls are used.
  - `test_list_indexes_returns_mapped_shape` — AC1
  - `test_get_index_docs_returns_mapped_shape_when_index_exists` — AC2
  - `test_get_index_docs_returns_404_when_index_missing` — AC3 (also
    confirms `get_docs` is never called)
  - `test_list_indexes_returns_500_without_leaking_details_on_unexpected_error`
    — AC5
  - `test_get_index_docs_returns_500_when_get_docs_fails_after_index_found`
    — AC5
- **E2E tests: none written.** Backend-only story, no user-facing UI change
  yet — the frontend consuming these endpoints is a separate story.

### AC4 confirmation

Confirmed implicitly: tests monkeypatch the module-level `server.moss_client`
global itself, and the route handlers pick up the patched fake object at
call time — confirming they read the shared global rather than holding a
private/captured reference.

### Framework setup

No test framework existed in this repo before this story. Added `pytest`
and `httpx` as dev dependencies via `uv add --dev pytest httpx` in
`backend/pyproject.toml` / `uv.lock`.

**Verdict: PASS.**

## MOS-STORY-001-003

Commands:
- `cd backend && uv run pytest test_server.py -v` (existing suite, regression check)
- `cd backend && uv add --dev pytest-playwright && uv run playwright install chromium`
- `cd backend && uv run pytest tests/e2e/test_manage_page.py -v --browser chromium`

Result: existing `test_server.py` suite still 5 passed, 0 failed (no
regression). New E2E suite: **3 passed, 2 failed**. Combined:
`uv run pytest test_server.py tests/e2e/test_manage_page.py -v --browser
chromium` → **8 passed, 2 failed, 1 warning** (the same pre-existing
`anyio.abc.BlockingPortal` deprecation warning noted in
MOS-STORY-001-001).

### Layers

- **Unit tests: none written as a separate layer.** The one piece of real
  business logic in this story is the grouping-precedence logic in
  `manage.js` (`resolveGroupKey`/`groupChunks`, AC6: `sourceDoc` > `type` >
  "Ungrouped"). This is a Python-only backend project with no Node/npm
  toolchain anywhere in the repo; adding one solely to unit-test ~25 lines
  of vanilla JS would be a disproportionate new dependency for a single
  file, and would duplicate what the E2E layer already exercises against
  the real browser DOM. Per `rules/testing.md`'s judgment call, this logic
  is instead covered by two E2E tests that assert on its *output* through
  the real page: `test_golden_path_selects_index_and_shows_grouped_chunks`
  (fixture data forces `sourceDoc` grouping — two `sourceDoc` values
  produce two groups with the right names/counts) and
  `test_type_grouping_used_when_no_chunk_has_source_doc` (fixture data with
  only `metadata.type`, no `sourceDoc`, forces the `type` fallback branch).
  Both precedence branches (AC6's `sourceDoc` and `type` cases) are
  exercised; the pure "Ungrouped" fallback (no chunk has either field) is
  not separately covered — noted as a gap below.
- **Feature tests: none written as a separate layer.** This story has no
  new backend route — it's a pure static frontend story consuming
  MOS-STORY-001-001's already feature-tested endpoints. There is no
  "handler without a browser" layer distinct from either the backend
  contract tests (already in `test_server.py`) or the E2E tests below; a
  Playwright-free DOM test would need jsdom or similar, which (per the
  unit-test reasoning above) isn't a sane addition to a Python-only repo
  for one file. The E2E layer is the feature-test-equivalent here.
- **E2E tests: 5 written (Playwright, Python bindings via
  `pytest-playwright`), 3 passed, 2 failed**, in
  `backend/tests/e2e/test_manage_page.py`. No E2E infrastructure existed
  before this story; `backend/tests/e2e/conftest.py` now provides a
  `live_server_url` fixture that runs a stub FastAPI app (same
  `backend/static` files, same two route signatures as `server.py`, but
  fixture data instead of a real Moss client — see conftest.py's docstring
  for the reasoning) in a background thread, so Playwright can drive the
  real `manage.html`/`manage.js` unchanged. `pytest-playwright` (Python,
  not a separate Node toolchain) was added as a new dev dependency via `uv
  add --dev pytest-playwright`, matching the existing pytest setup from
  MOS-STORY-001-001; `uv run playwright install chromium` installed the
  browser binary successfully (a one-time ~276MB download, no sandbox
  failures).
  - `test_golden_path_selects_index_and_shows_grouped_chunks` — **PASSED**.
    Covers AC3 (selector populates), AC5 (fetch on selection — implicit,
    docs load), AC6 (`sourceDoc` grouping, two groups from two
    `sourceDoc` values), AC8 (first group expanded, `aria-expanded`
    reflects state, chunk-count badge), AC9 (chunk id, text, metadata
    chips visible).
  - `test_type_grouping_used_when_no_chunk_has_source_doc` — **PASSED**.
    Covers AC6's `type` fallback branch specifically.
  - `test_switching_to_index_with_no_chunks_shows_empty_state` —
    **PASSED**. Covers AC7 (empty-chunks state).
  - `test_empty_index_list_disables_selector_and_shows_message` —
    **FAILED**. Covers AC3's empty-list branch (selector disabled, "No
    indexes available" shown). The selector/select-option assertions and
    the docs-area empty-state assertion all pass; the test fails on the
    final assertion that `#errorBanner` is hidden — see bug below.
  - `test_index_list_failure_shows_error_banner_with_retry` — **FAILED**.
    Covers AC4 (error banner + Retry shown on `/api/indexes` failure).
    The banner-appears-on-failure and Retry-button-visible assertions
    pass; after clicking Retry with the stub reconfigured to succeed, the
    test fails asserting the banner is hidden again — see bug below.

### Bug found: `#errorBanner`'s `hidden` attribute is neutralized by `style.css`

`backend/static/style.css` (`.error-banner { display: flex; ... }`, around
line 699) sets `display: flex` on the `.error-banner` class with no
`[hidden]` override. An author stylesheet rule always wins over the
browser's built-in `[hidden] { display: none }` UA-stylesheet rule
regardless of selector specificity or source order (author styles beat UA
styles by cascade origin). The practical effect, confirmed directly with
Playwright (`getComputedStyle(el).display` reports `"flex"` while
`el.hasAttribute('hidden')` reports `true`): **the error banner is visible
at all times**, including on a normal page load with a healthy,
non-empty index list, and after `manage.js`'s `hideError()` sets
`errorBanner.hidden = true` following a successful retry. This is not a
self-consistency artifact of the test setup — the same fixture data and
DOM the golden-path test uses (which passes) shows the banner is always
present underneath the docs area; it's simply not visually obvious in a
manual click-through because the loading/success states repaint
`docsArea` on top of a short-lived layout, but it is a real, observable,
automatable defect against AC3 ("no crash" is satisfied, but the state
described doesn't cleanly hide the banner) and AC4 (banner must disappear
once the retry succeeds — it does not). Not fixed here per this agent's
scope — implementation is `frontend`'s to fix (e.g. add `.error-banner[hidden] { display: none; }`
or use a `.hidden` utility class instead of the native attribute).

### Known gap

The pure "Ungrouped" fallback branch of AC6 (no chunk in the index has
either `metadata.sourceDoc` or `metadata.type`) is implemented in
`resolveGroupKey`/`groupChunks` but not exercised by any test at any
layer. Given the two failures above already block this story from
passing, this gap is noted rather than expanded on now; it should be
added as a small additional E2E case (or the JS unit test, if a Node
toolchain is ever introduced) once the CSS bug is fixed and this story
comes back for a fix/retest pass.

### Fix applied

Added `.error-banner[hidden] { display: none; }` to `backend/static/style.css`
immediately after the `.error-banner` rule, so the native `hidden` attribute
`manage.js` toggles actually hides the element again (an author `display`
rule otherwise always wins over the UA `[hidden]` stylesheet rule).
Re-ran the full suite: `uv run pytest test_server.py tests/e2e/test_manage_page.py -v --browser chromium`
→ **10 passed, 0 failed, 1 warning** (same pre-existing unrelated anyio
deprecation warning).

**Verdict: PASS.** All required layers green after the CSS fix. The
"Ungrouped"-fallback test gap noted above remains open as a minor,
non-blocking follow-up (both other precedence branches — `sourceDoc` and
`type` — are covered).

## MOS-STORY-001-002

Commands:
- `cd backend && uv run pytest test_server.py -v`
- `cd backend && uv run pytest tests/e2e/test_manage_page.py -v --browser chromium`

Results:
- `test_server.py`: **20 passed, 0 failed** (5 pre-existing from
  MOS-STORY-001-001 + 15 new for this story), 1 warning (the same
  pre-existing, unrelated `anyio.abc.BlockingPortal` deprecation warning
  from Starlette's `TestClient`).
- `tests/e2e/test_manage_page.py`: **5 passed, 0 failed** — re-run
  unchanged as a regression check, since this story edits `server.py`
  (the same file the manage-page E2E suite exercises through its stub
  app). No regression.

### Layers

- **Unit tests: none written.** Same rationale as MOS-STORY-001-001 —
  `add_index_doc`/`update_index_doc`/`delete_index_doc`/`_reload_if_live`
  are thin route/orchestration logic over the Moss SDK; a unit test would
  isolate the same conditional (`name in LIVE_LOADED_INDEXES`) and
  construction (`DocumentInfo(...)`) the feature tests below already
  exercise through the real route. Feature-level tests are the sufficient
  layer per `rules/testing.md`'s pass-through carve-out.
- **Feature tests: 15 written, 15 passed**, appended to
  `backend/test_server.py`, using Starlette's `TestClient` against the
  real FastAPI app/routes with `server.moss_client` monkeypatched (no
  real Moss credentials or network access). All 7 acceptance criteria are
  covered:
  - `test_add_index_doc_returns_id_and_calls_add_docs_with_matching_document`
    — AC1 (200 + `{id}`, and `add_docs` called with a `DocumentInfo` whose
    `id`/`text`/`metadata` match the request body — asserted field-by-field
    since `DocumentInfo` has no `__eq__`).
  - `test_update_index_doc_returns_id_on_success` — AC2.
  - `test_delete_index_doc_returns_204_on_success` — AC3 (also asserts
    `delete_docs` called with `(name, [doc_id])` and an empty response
    body).
  - `test_add_index_doc_reloads_live_index_when_name_is_protocol_index`,
    `test_update_index_doc_reloads_live_index_when_name_is_live_data_index`,
    `test_delete_index_doc_reloads_live_index_when_name_is_protocol_index`
    — AC4, reload-on-mutation for both live-loaded index names across all
    three verbs, using a fake `moss_client` with a `load_index` `AsyncMock`
    asserted called exactly once with the mutated index's name.
  - `test_add_index_doc_does_not_reload_when_index_is_not_live_loaded`,
    `test_update_index_doc_does_not_reload_when_index_is_not_live_loaded`,
    `test_delete_index_doc_does_not_reload_when_index_is_not_live_loaded`
    — AC4's negative case: the same three verbs against an index name
    that is neither `PROTOCOL_INDEX_NAME` nor `LIVE_DATA_INDEX_NAME` must
    never call `load_index`.
  - `test_add_index_doc_rejects_empty_id`,
    `test_add_index_doc_rejects_empty_text`,
    `test_add_index_doc_rejects_metadata_as_array`,
    `test_add_index_doc_rejects_metadata_as_string` — AC5 (422 on each,
    and `add_docs` never called).
  - `test_add_index_doc_returns_500_without_leaking_details_and_skips_reload`
    — AC6: `add_docs` raising is caught, returns 500 with a safe generic
    message (the injected secret string is asserted absent from the
    response body), and `load_index` is asserted never called — proving
    the reload step is skipped, not merely unreached by coincidence.
  - `test_add_index_doc_with_existing_id_upserts_in_place_instead_of_duplicating`
    — AC7: uses a small stateful fake Moss client
    (`_StatefulFakeMossClient`, a dict keyed by doc id, real feature-test
    style rather than a memoryless mock) so the test can prove "still only
    one chunk with this id" through the real `GET /api/indexes/{name}/docs`
    route. Adds `id="x"` with `text="first version"`, confirms via GET
    that exactly one chunk with id `x` exists with that text, then adds
    the same `id="x"` again with `text="second version"` and confirms via
    a second GET that there is still exactly one chunk with id `x`, now
    holding the updated text (not two chunks).
- **E2E tests: none newly required.** This story is backend-only — no new
  UI surface — so per `rules/testing.md`'s E2E scoping ("not required for
  purely internal/infra stories with no user-facing surface"), no new E2E
  layer applies. The existing `tests/e2e/test_manage_page.py` suite from
  MOS-STORY-001-003 was re-run in full as a regression check because it
  exercises `server.py`'s static file serving and read routes through the
  same process this story's mutation routes now also live in; all 5
  still pass with no change in behavior.

No new external-contract assumptions are introduced by this story (no new
third-party wire format); the fake `moss_client` stand-ins mirror the same
already-established pattern from MOS-STORY-001-001.

**Verdict: PASS.** All required layers (feature tests) written and
passing, full pre-existing suite (unit/feature: `test_server.py`; E2E:
`test_manage_page.py`) green with no regressions. No implementation
issues found — nothing surfaced back to `backend`.

## MOS-STORY-001-004

Commands:
- `cd backend && uv run pytest test_server.py -v`
- `cd backend && uv run pytest tests/e2e/test_manage_page.py -v --browser chromium`
- `cd backend && uv run pytest tests/e2e/test_manage_crud.py -v --browser chromium`

Results:
- `test_server.py`: **20 passed, 0 failed** (unchanged from
  MOS-STORY-001-002 — this story touches no backend route code), 1
  warning (the same pre-existing, unrelated `anyio.abc.BlockingPortal`
  deprecation warning).
- `tests/e2e/test_manage_page.py`: **4/5 passed on the representative run
  below, intermittently 5/5 on others** — see "Pre-existing flake found"
  below. This is not a regression from this story's changes.
- `tests/e2e/test_manage_crud.py` (new): **11 passed, 0 failed**, stable
  across 3 repeated full runs.

### Layers

- **Unit tests: none written.** All new logic (`buildChunkForm`,
  `createMetadataEditor`, upsert/remove-and-rerender, toast wording) is UI
  behavior driven by real DOM events and network calls, not isolable
  business logic with mockable collaborators worth testing apart from the
  rendered page. The E2E layer below drives every one of these code paths
  through the real browser, which is the more meaningful test for this
  kind of code per `rules/testing.md`'s scoping (component *unit* tests
  are for logic in isolation; this story's logic is inseparable from DOM
  state and fetch calls).
- **Feature tests: not applicable as a separate layer.** This story adds
  no new backend route (MOS-STORY-001-002 already built and tested
  `POST`/`PUT`/`DELETE`); its only new surface is the frontend UI, which
  the E2E layer covers end-to-end.
- **E2E tests: 11 written, 11 passed**, in
  `backend/tests/e2e/test_manage_crud.py`, run against the real
  `manage.html`/`manage.js` (unchanged) via a stub FastAPI app whose
  `/api/indexes/{name}/docs[...]` POST/PUT/DELETE routes were extended in
  `backend/tests/e2e/conftest.py` to be genuinely stateful (an in-memory
  dict keyed by chunk id, mirroring `server.py`'s real routes' request/
  response contract) — so every add/edit/delete in these tests is proven
  by the page's own real fetch + re-render, nothing is mocked at the JS
  layer. Covering the 10 acceptance criteria:
  - `test_add_chunk_golden_path_appears_in_group_with_success_toast` —
    AC1/AC2: opens "+ Add chunk" on a group, fills id/text, saves, asserts
    the new chunk row appears in that group with the entered text and a
    toast reading `Added new chunk "chunk-new"` appears.
  - `test_add_chunk_with_existing_id_reports_updated_not_added` — AC3:
    adding a chunk with an id already in the fixture data shows
    `Updated existing chunk "chunk-1"`, and asserts the "Added new chunk"
    wording is absent.
  - `test_add_chunk_clears_text_field_but_keeps_group_context_for_next_add`
    — AC4: after a successful add, the form reopens with an empty text
    field but the metadata editor still pre-filled with the same
    `sourceDoc` group value, and a second chunk added without re-entering
    the group value lands in the same group.
  - `test_edit_chunk_updates_text_in_place_without_duplicating` — AC2/AC9
    (text portion): opens "Edit" on `chunk-1`, changes its text, saves,
    asserts the updated text appears and there is still exactly one row
    for `chunk-1` (no duplicate).
  - `test_editing_source_doc_metadata_moves_chunk_to_new_group` — AC9:
    edits `chunk-1`'s `sourceDoc` metadata value to a different existing
    group's value, saves, and asserts the chunk now renders under the
    `cardiac-protocol.md` group and no longer under `airway-protocol.md`.
  - `test_cancel_discards_edit_and_leaves_original_text_and_sends_no_request`
    — AC5: opens an edit form, types a change, clicks Cancel, asserts the
    original text is still shown, the form is removed from the DOM
    (focus-return path exercised), and — checked via a `page.on("request")`
    listener rather than just visible text — that no POST/PUT/DELETE
    request was ever sent to `/api/indexes/...`.
  - `test_delete_chunk_removes_it_and_shows_toast_naming_it` — AC6: clicks
    Delete on `chunk-2`, asserts the row is removed from the DOM and a
    toast reading `Deleted chunk "chunk-2" (...)` appears.
  - `test_delete_button_has_no_confirmation_dialog` — AC6's "no
    confirmation dialog" explicit decision: registers a `page.on("dialog")`
    listener that would catch and dismiss any native `confirm()`/`alert()`,
    clicks Delete, and asserts no dialog ever fired while the delete still
    completed.
  - `test_save_failure_keeps_form_open_with_input_intact_and_shows_error`
    — AC7: with the stub's mutation routes forced to return 500, submits
    an add form and asserts the form is still open (not removed), the
    typed id/text values are still present in the form fields, an inline
    `.chunk-form-error` becomes visible, and the chunk never appears in
    the group.
  - `test_delete_failure_keeps_chunk_visible_and_shows_error` — AC8: with
    mutations forced to 500, clicks Delete and asserts the chunk row is
    still present and a `.toast-error` appears.
  - `test_metadata_remove_button_is_keyboard_operable` — AC10 (partial):
    tab-focuses a metadata row's "×" remove button and activates it with
    `Enter`, asserting the row count drops by one. Full tab-order/focus
    coverage across every control (e.g. focus landing correctly when a
    form opens, "+ Add chunk"/"+ New Document"/Edit/Delete buttons
    themselves) was not additionally tested with raw `Tab` key sequences —
    flagged as a residual gap on AC10 beyond what the click-equivalent
    interactions above already exercise (every control used above is a
    real `<button>`, which is keyboard-activatable by default).

### Pre-existing flake found (not from this story)

While re-running `tests/e2e/test_manage_page.py` as the required
regression check, `test_index_list_failure_shows_error_banner_with_retry`
failed intermittently (roughly 1 in 5 runs observed; 4/5 and 5/5 seen
across repeated runs) with:

```
AssertionError: assert False
 +  where False = is_enabled()
 +    where is_enabled = Locator(selector='#indexSelect').is_enabled
```

Root cause: that test calls `retry_button.click()` and then immediately
asserts `banner.is_hidden()` / `select.is_enabled()` using Playwright's
non-retrying `is_hidden()`/`is_enabled()` snapshot methods, instead of the
auto-retrying `expect(...).to_be_hidden()`/`to_be_enabled()` assertions —
so on a slow tick (retry's `fetch("/api/indexes")` not yet resolved when
the assertion runs), the check reads stale DOM state and fails. This was
confirmed to pre-exist this story's work: reproduced identically after
`git stash`-ing every change made for MOS-STORY-001-004 (frontend's
`manage.html`/`manage.js`/`style.css` diffs and this story's
`conftest.py`/`test_manage_crud.py` additions), against the unmodified
MOS-STORY-001-002 code, run in complete isolation. Per this story's scope
("keeping the read-only tests in test_manage_page.py untouched"), this
was not fixed here — it is surfaced for a follow-up fix to that test file
(swap the two non-retrying assertions for `expect(...).to_be_hidden()`
and `expect(...).to_be_enabled()`).

### Flake fixed

Swapped the two non-retrying assertions (`banner.is_hidden()`,
`select.is_enabled()`) in `test_index_list_failure_shows_error_banner_with_retry`
for `expect(banner).to_be_hidden()` / `expect(select).to_be_enabled()` /
`expect(select.locator("option")).to_have_text(...)`, so the check waits
for the DOM to settle after the retry's fetch resolves instead of reading
a snapshot immediately after the click. Re-ran the previously-flaky test
5 times in isolation (5/5 pass) and the full combined suite
(`test_server.py` + `test_manage_page.py` + `test_manage_crud.py`) once
more end to end: **36 passed, 0 failed**.

**Verdict: PASS.** All required tests for this story's acceptance criteria
(10/10 covered, 11 new tests) pass reliably, `test_server.py` regression
is clean (20/20), and the previously-flaky unrelated test now passes
deterministically too — no caveats remain. AC10 (keyboard operability) is
only partially exercised via a dedicated test, since every interactive
control here is a native `<button>` element, keyboard-operable without
extra JS.
