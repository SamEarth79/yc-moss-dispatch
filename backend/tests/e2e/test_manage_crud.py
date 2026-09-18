"""E2E tests for the add/edit/delete chunk UI (MOS-STORY-001-004).

Runs a real Chromium browser (Playwright) against the actual static files
(backend/static/manage.html + manage.js, unchanged), served by the same stub
FastAPI app used by test_manage_page.py (see conftest.py) — but here the
stub's POST/PUT/DELETE routes are stateful (an in-memory dict keyed by chunk
id), so an add/edit/delete is verified end-to-end through the real page: the
frontend's own fetch + re-render is what proves the change happened, nothing
is mocked at the JS layer.
"""

PROTOCOL_DOCS = [
    {
        "id": "chunk-1",
        "text": "First protocol chunk about airway management and initial assessment steps.",
        "metadata": {"sourceDoc": "airway-protocol.md", "priority": "high"},
    },
    {
        "id": "chunk-2",
        "text": "Second protocol chunk continuing airway management guidance.",
        "metadata": {"sourceDoc": "airway-protocol.md", "priority": "high"},
    },
    {
        "id": "chunk-3",
        "text": "A chunk from a different source document about cardiac arrest response.",
        "metadata": {"sourceDoc": "cardiac-protocol.md", "priority": "critical"},
    },
]


def _seed(stub_state):
    stub_state.indexes = [
        {
            "name": "protocol-index",
            "docCount": 3,
            "status": "ready",
            "model": "moss-minilm",
            "updatedAt": "2026-01-01T00:00:00Z",
        }
    ]
    stub_state.docs_by_index = {"protocol-index": [dict(d, metadata=dict(d["metadata"])) for d in PROTOCOL_DOCS]}


def _airway_group(page):
    groups = page.locator(".doc-group")
    for i in range(groups.count()):
        group = groups.nth(i)
        if "airway-protocol.md" in group.locator(".doc-group-name").inner_text():
            return group
    raise AssertionError("airway-protocol.md group not found")


def test_add_chunk_golden_path_appears_in_group_with_success_toast(page, live_server_url, stub_state):
    _seed(stub_state)
    page.goto(f"{live_server_url}/manage.html")

    group = _airway_group(page)
    group.locator(".add-chunk-button").click()

    form = page.locator(".chunk-form")
    form.locator("#chunkId-1").fill("chunk-new")
    form.locator("textarea").fill("A brand new chunk of dispatch guidance.")

    form.locator(".action-button", has_text="Save").click()

    new_row = group.locator(".chunk-row", has=page.locator(".chunk-id", has_text="chunk-new"))
    new_row.wait_for(state="visible")
    assert "A brand new chunk of dispatch guidance." in new_row.locator(".chunk-text").inner_text()

    toast = page.locator(".toast")
    expect_text = 'Added new chunk "chunk-new"'
    toast.filter(has_text=expect_text).first.wait_for(state="visible")


def test_add_chunk_with_existing_id_reports_updated_not_added(page, live_server_url, stub_state):
    _seed(stub_state)
    page.goto(f"{live_server_url}/manage.html")

    group = _airway_group(page)
    group.locator(".add-chunk-button").click()

    form = page.locator(".chunk-form")
    form.locator("#chunkId-1").fill("chunk-1")
    form.locator("textarea").fill("Replaced text for an existing chunk id.")
    form.locator(".action-button", has_text="Save").click()

    toast = page.locator(".toast")
    toast.filter(has_text='Updated existing chunk "chunk-1"').first.wait_for(state="visible")
    assert toast.filter(has_text='Added new chunk "chunk-1"').count() == 0


def test_edit_chunk_updates_text_in_place_without_duplicating(page, live_server_url, stub_state):
    _seed(stub_state)
    page.goto(f"{live_server_url}/manage.html")

    group = _airway_group(page)
    row = group.locator(".chunk-row").filter(has=page.locator(".chunk-id", has_text="chunk-1"))
    row.locator("button", has_text="Edit").click()

    form = page.locator(".chunk-form")
    textarea = form.locator("textarea")
    textarea.fill("")
    textarea.fill("Updated text after editing chunk-1.")
    form.locator(".action-button", has_text="Save").click()

    updated_row = group.locator(".chunk-row").filter(has=page.locator(".chunk-id", has_text="chunk-1"))
    updated_row.locator(".chunk-text", has_text="Updated text after editing chunk-1.").wait_for(state="visible")

    matches = group.locator(".chunk-row").filter(has=page.locator(".chunk-id", has_text="chunk-1"))
    assert matches.count() == 1


def test_cancel_discards_edit_and_leaves_original_text_and_sends_no_request(page, live_server_url, stub_state):
    _seed(stub_state)

    mutation_requests = []
    page.on(
        "request",
        lambda req: mutation_requests.append(req)
        if req.method in ("POST", "PUT", "DELETE") and "/api/indexes/" in req.url
        else None,
    )

    page.goto(f"{live_server_url}/manage.html")

    group = _airway_group(page)
    row = group.locator(".chunk-row").filter(has=page.locator(".chunk-id", has_text="chunk-1"))
    row.locator("button", has_text="Edit").click()

    form = page.locator(".chunk-form")
    form.locator("textarea").fill("This text should never be saved.")
    form.locator(".action-button", has_text="Cancel").click()

    page.locator(".chunk-form").wait_for(state="detached")

    unchanged_row = group.locator(".chunk-row").filter(has=page.locator(".chunk-id", has_text="chunk-1"))
    assert "First protocol chunk about airway management" in unchanged_row.locator(".chunk-text").inner_text()
    assert "This text should never be saved." not in unchanged_row.locator(".chunk-text").inner_text()
    assert mutation_requests == []


def test_delete_chunk_removes_it_and_shows_toast_naming_it(page, live_server_url, stub_state):
    _seed(stub_state)
    page.goto(f"{live_server_url}/manage.html")

    group = _airway_group(page)
    assert page.locator("button[aria-label='Delete chunk chunk-2']").count() == 1

    page.locator("button[aria-label='Delete chunk chunk-2']").click()

    group.locator(".chunk-id", has_text="chunk-2").wait_for(state="detached")

    toast = page.locator(".toast")
    toast.filter(has_text='Deleted chunk "chunk-2"').first.wait_for(state="visible")


def test_delete_button_has_no_confirmation_dialog(page, live_server_url, stub_state):
    _seed(stub_state)

    dialog_seen = []
    page.on("dialog", lambda dialog: (dialog_seen.append(dialog), dialog.dismiss()))

    page.goto(f"{live_server_url}/manage.html")
    group = _airway_group(page)
    page.locator("button[aria-label='Delete chunk chunk-1']").click()

    group.locator(".chunk-id", has_text="chunk-1").wait_for(state="detached")
    assert dialog_seen == []


def test_save_failure_keeps_form_open_with_input_intact_and_shows_error(page, live_server_url, stub_state):
    _seed(stub_state)
    stub_state.mutation_status = 500
    page.goto(f"{live_server_url}/manage.html")

    group = _airway_group(page)
    group.locator(".add-chunk-button").click()

    form = page.locator(".chunk-form")
    form.locator("#chunkId-1").fill("chunk-fail")
    form.locator("textarea").fill("Text that should survive a failed save.")
    form.locator(".action-button", has_text="Save").click()

    error_el = form.locator(".chunk-form-error")
    error_el.wait_for(state="visible")

    assert page.locator(".chunk-form").count() == 1
    assert form.locator("#chunkId-1").input_value() == "chunk-fail"
    assert form.locator("textarea").input_value() == "Text that should survive a failed save."
    assert group.locator(".chunk-id", has_text="chunk-fail").count() == 0


def test_delete_failure_keeps_chunk_visible_and_shows_error(page, live_server_url, stub_state):
    _seed(stub_state)
    stub_state.mutation_status = 500
    page.goto(f"{live_server_url}/manage.html")

    group = _airway_group(page)
    page.locator("button[aria-label='Delete chunk chunk-1']").click()

    toast = page.locator(".toast-error")
    toast.first.wait_for(state="visible")

    assert group.locator(".chunk-id", has_text="chunk-1").count() == 1


def test_add_chunk_clears_text_field_but_keeps_group_context_for_next_add(page, live_server_url, stub_state):
    _seed(stub_state)
    page.goto(f"{live_server_url}/manage.html")

    group = _airway_group(page)
    group.locator(".add-chunk-button").click()

    form = page.locator(".chunk-form")
    form.locator("#chunkId-1").fill("chunk-first")
    form.locator("textarea").fill("First of two chunks added back to back.")
    form.locator(".action-button", has_text="Save").click()

    group.locator(".chunk-id", has_text="chunk-first").wait_for(state="visible")

    reopened_form = page.locator(".chunk-form")
    reopened_form.wait_for(state="visible")
    assert reopened_form.locator("textarea").input_value() == ""

    reopened_form.locator("#chunkId-1").fill("chunk-second")
    reopened_form.locator("textarea").fill("Second chunk, same document group.")
    reopened_form.locator(".action-button", has_text="Save").click()

    group.locator(".chunk-id", has_text="chunk-second").wait_for(state="visible")
    second_row = group.locator(".chunk-row").filter(has=page.locator(".chunk-id", has_text="chunk-second"))
    chip_text = second_row.locator(".metadata-chips .badge").all_text_contents()
    assert "sourceDoc: airway-protocol.md" in chip_text


def test_editing_source_doc_metadata_moves_chunk_to_new_group(page, live_server_url, stub_state):
    _seed(stub_state)
    page.goto(f"{live_server_url}/manage.html")

    airway_group = _airway_group(page)
    row = airway_group.locator(".chunk-row").filter(has=page.locator(".chunk-id", has_text="chunk-1"))
    row.locator("button", has_text="Edit").click()

    form = page.locator(".chunk-form")
    metadata_rows = form.locator(".metadata-row")
    source_doc_row = None
    for i in range(metadata_rows.count()):
        candidate = metadata_rows.nth(i)
        if candidate.locator(".metadata-key-input").input_value() == "sourceDoc":
            source_doc_row = candidate
            break
    assert source_doc_row is not None, "expected a metadata row for the sourceDoc key"
    source_doc_row.locator(".metadata-value-input").fill("cardiac-protocol.md")
    form.locator(".action-button", has_text="Save").click()

    cardiac_group = page.locator(".doc-group").filter(has=page.locator(".doc-group-name", has_text="cardiac-protocol.md"))
    if "expanded" not in (cardiac_group.get_attribute("class") or ""):
        cardiac_group.locator(".doc-group-header").click()
    cardiac_group.locator(".chunk-id", has_text="chunk-1").wait_for(state="visible")

    remaining_in_airway = page.locator(".doc-group").filter(
        has=page.locator(".doc-group-name", has_text="airway-protocol.md")
    ).locator(".chunk-id", has_text="chunk-1")
    assert remaining_in_airway.count() == 0


def test_metadata_remove_button_is_keyboard_operable(page, live_server_url, stub_state):
    _seed(stub_state)
    page.goto(f"{live_server_url}/manage.html")

    group = _airway_group(page)
    row = group.locator(".chunk-row").filter(has=page.locator(".chunk-id", has_text="chunk-1"))
    row.locator("button", has_text="Edit").click()

    form = page.locator(".chunk-form")
    initial_rows = form.locator(".metadata-row")
    initial_count = initial_rows.count()
    assert initial_count > 0

    remove_btn = initial_rows.first.locator(".metadata-remove-btn")
    remove_btn.focus()
    page.keyboard.press("Enter")

    assert form.locator(".metadata-row").count() == initial_count - 1
