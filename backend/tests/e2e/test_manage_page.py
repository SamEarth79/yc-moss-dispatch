"""E2E tests for backend/static/manage.html + manage.js (MOS-STORY-001-003).

Runs a real Chromium browser (Playwright) against the actual static files,
served by a stub FastAPI app (see conftest.py) that returns fixture data
instead of calling a real Moss client. The frontend code under test
(manage.html/manage.js) is exactly what ships — nothing about it is mocked.
"""

from playwright.sync_api import expect

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


def test_golden_path_selects_index_and_shows_grouped_chunks(page, live_server_url, stub_state):
    stub_state.indexes = [
        {
            "name": "protocol-index",
            "docCount": 3,
            "status": "ready",
            "model": "moss-minilm",
            "updatedAt": "2026-01-01T00:00:00Z",
        },
        {
            "name": "facility-index",
            "docCount": 0,
            "status": "ready",
            "model": "moss-minilm",
            "updatedAt": "2026-01-01T00:00:00Z",
        },
    ]
    stub_state.docs_by_index = {"protocol-index": PROTOCOL_DOCS, "facility-index": []}

    page.goto(f"{live_server_url}/manage.html")

    select = page.locator("#indexSelect")
    assert select.is_enabled()
    options = select.locator("option").all_text_contents()
    assert options == ["protocol-index", "facility-index"]
    assert select.input_value() == "protocol-index"

    groups = page.locator(".doc-group")
    assert groups.count() == 2

    first_group = groups.nth(0)
    assert "airway-protocol.md" in first_group.locator(".doc-group-name").inner_text()
    assert "expanded" in (first_group.get_attribute("class") or "")
    assert first_group.locator(".doc-group-header").get_attribute("aria-expanded") == "true"
    assert "2 chunks" in first_group.locator(".doc-group-header .badge").inner_text()

    second_group = groups.nth(1)
    assert "cardiac-protocol.md" in second_group.locator(".doc-group-name").inner_text()
    assert "expanded" not in (second_group.get_attribute("class") or "")
    assert second_group.locator(".doc-group-header").get_attribute("aria-expanded") == "false"

    first_chunk = first_group.locator(".chunk-row").first
    assert first_chunk.locator(".chunk-id").inner_text() == "chunk-1"
    assert "airway management" in first_chunk.locator(".chunk-text").inner_text()
    chip_text = first_chunk.locator(".metadata-chips .badge").all_text_contents()
    assert "sourceDoc: airway-protocol.md" in chip_text
    assert "priority: high" in chip_text


def test_switching_to_index_with_no_chunks_shows_empty_state(page, live_server_url, stub_state):
    stub_state.indexes = [
        {"name": "protocol-index", "docCount": 3, "status": "ready", "model": "m", "updatedAt": "t"},
        {"name": "facility-index", "docCount": 0, "status": "ready", "model": "m", "updatedAt": "t"},
    ]
    stub_state.docs_by_index = {"protocol-index": PROTOCOL_DOCS, "facility-index": []}

    page.goto(f"{live_server_url}/manage.html")
    page.locator("#indexSelect").select_option("facility-index")

    empty_state = page.locator("#docsArea .empty-state")
    assert empty_state.inner_text() == "No documents in this index yet"
    assert page.locator(".doc-group").count() == 0


def test_type_grouping_used_when_no_chunk_has_source_doc(page, live_server_url, stub_state):
    stub_state.indexes = [{"name": "facility-index", "docCount": 2, "status": "ready", "model": "m", "updatedAt": "t"}]
    stub_state.docs_by_index = {
        "facility-index": [
            {"id": "f-1", "text": "Hospital A details.", "metadata": {"type": "hospital"}},
            {"id": "f-2", "text": "Clinic B details.", "metadata": {"type": "clinic"}},
        ]
    }

    page.goto(f"{live_server_url}/manage.html")

    groups = page.locator(".doc-group")
    assert groups.count() == 2
    names = [groups.nth(i).locator(".doc-group-name").inner_text() for i in range(2)]
    assert names == ["hospital", "clinic"]


def test_empty_index_list_disables_selector_and_shows_message(page, live_server_url, stub_state):
    stub_state.indexes = []

    page.goto(f"{live_server_url}/manage.html")

    select = page.locator("#indexSelect")
    assert select.is_disabled()
    assert select.locator("option").inner_text() == "No indexes available"
    assert page.locator("#docsArea .empty-state").inner_text() == "No indexes available"
    assert page.locator("#errorBanner").is_hidden()


def test_index_list_failure_shows_error_banner_with_retry(page, live_server_url, stub_state):
    stub_state.indexes_status = 500

    page.goto(f"{live_server_url}/manage.html")

    banner = page.locator("#errorBanner")
    assert banner.is_visible()
    assert banner.locator("#errorBannerText").inner_text() == "Failed to load indexes."
    retry_button = banner.locator("#retryButton")
    assert retry_button.is_visible()

    stub_state.indexes_status = 200
    stub_state.indexes = [{"name": "protocol-index", "docCount": 3, "status": "ready", "model": "m", "updatedAt": "t"}]
    stub_state.docs_by_index = {"protocol-index": PROTOCOL_DOCS}

    retry_button.click()

    expect(banner).to_be_hidden()
    select = page.locator("#indexSelect")
    expect(select).to_be_enabled()
    expect(select.locator("option")).to_have_text("protocol-index")
