"""E2E tests for backend/static/deviations.html + deviations.js (MOS-STORY-002-007).

Real Chromium against the shipped static files, served by the stub app in
conftest.py. The stub returns records already in the order the real
GET /api/deviations produces (newest first, covered by test_deviations_list.py).
"""

from playwright.sync_api import expect

LONG_TEXT = "The caller described a long sequence of events. " * 10


def _record(record_id, timestamp, **overrides):
    record = {
        "id": record_id,
        "timestamp": timestamp,
        "callerTranscript": "my dad is choking",
        "callerSummary": {"whatHappened": "adult choking"},
        "protocolChunkId": "choking-1",
        "protocolChunkText": "Give five back blows.",
        "dispatcherTranscript": "give him water",
        "deviationSummary": f"Summary {record_id}",
        "reason": "he seemed thirsty",
        "seed": False,
    }
    record.update(overrides)
    return record


def test_populated_list_renders_newest_first_with_count_and_fields(page, live_server_url, stub_state):
    stub_state.deviations = [
        _record("newest", "2026-03-01T00:00:00Z"),
        _record("older", "2026-01-01T00:00:00Z", reason=""),
    ]

    page.goto(f"{live_server_url}/deviations.html")

    cards = page.locator("article.panel.deviation-record")
    expect(cards).to_have_count(2)
    expect(page.locator("#deviationCountBadge")).to_have_text("2 deviations")
    assert cards.locator("h2.deviation-title").all_text_contents() == ["Summary newest", "Summary older"]
    assert cards.first.locator("time.deviation-time").get_attribute("datetime") == "2026-03-01T00:00:00Z"

    first_keys = cards.first.locator(".kv-row.deviation-row .kv-key").all_text_contents()
    assert first_keys == ["Caller", "Protocol chunk", "Dispatcher said", "Reason"]
    second_keys = cards.nth(1).locator(".kv-row.deviation-row .kv-key").all_text_contents()
    assert second_keys == ["Caller", "Protocol chunk", "Dispatcher said"]
    assert "give him water" in cards.first.inner_text()
    assert "adult choking" in cards.first.inner_text()
    assert page.locator("#errorBanner").is_hidden()


def test_single_record_count_is_singular(page, live_server_url, stub_state):
    stub_state.deviations = [_record("only", "2026-01-01T00:00:00Z")]
    page.goto(f"{live_server_url}/deviations.html")
    expect(page.locator("#deviationCountBadge")).to_have_text("1 deviation")


def test_sample_tag_appears_only_on_seeded_records(page, live_server_url, stub_state):
    stub_state.deviations = [
        _record("seeded", "2026-02-01T00:00:00Z", seed=True),
        _record("live", "2026-01-01T00:00:00Z", seed=False),
    ]
    page.goto(f"{live_server_url}/deviations.html")

    cards = page.locator("article.deviation-record")
    expect(cards).to_have_count(2)
    expect(cards.first.locator("span.deviation-sample-tag")).to_have_text("sample")
    expect(cards.nth(1).locator("span.deviation-sample-tag")).to_have_count(0)


def test_empty_state_when_no_deviations(page, live_server_url, stub_state):
    stub_state.deviations = []
    page.goto(f"{live_server_url}/deviations.html")

    expect(page.locator("#deviationsArea .empty-state")).to_be_visible()
    expect(page.locator("#deviationCountBadge")).to_have_text("0 deviations")
    expect(page.locator("article.deviation-record")).to_have_count(0)
    assert page.locator("#errorBanner").is_hidden()


def test_error_banner_with_retry_recovers(page, live_server_url, stub_state):
    stub_state.deviations_status = 500
    page.goto(f"{live_server_url}/deviations.html")

    banner = page.locator("#errorBanner")
    expect(banner).to_be_visible()
    expect(banner.locator("#errorBannerText")).to_have_text("Failed to load deviations.")
    expect(page.locator("article.deviation-record")).to_have_count(0)

    stub_state.deviations_status = 200
    stub_state.deviations = [_record("r1", "2026-01-01T00:00:00Z")]
    page.locator("#retryButton").click()

    expect(banner).to_be_hidden()
    expect(page.locator("article.deviation-record")).to_have_count(1)
    expect(page.locator("#deviationCountBadge")).to_have_text("1 deviation")


def test_long_text_is_clamped_and_show_more_toggles(page, live_server_url, stub_state):
    stub_state.deviations = [
        _record("long", "2026-01-01T00:00:00Z", dispatcherTranscript=LONG_TEXT, reason="short reason")
    ]
    page.goto(f"{live_server_url}/deviations.html")

    card = page.locator("article.deviation-record")
    buttons = card.locator(".show-more-btn")
    expect(buttons).to_have_count(1)
    clamped = card.locator(".chunk-text.clamped")
    expect(clamped).to_have_count(1)

    buttons.click()
    expect(card.locator(".chunk-text.clamped")).to_have_count(0)
    expect(buttons).to_have_text("Show less")

    buttons.click()
    expect(card.locator(".chunk-text.clamped")).to_have_count(1)
    expect(buttons).to_have_text("Show more")


def test_short_text_has_no_clamp_or_show_more(page, live_server_url, stub_state):
    stub_state.deviations = [_record("short", "2026-01-01T00:00:00Z")]
    page.goto(f"{live_server_url}/deviations.html")
    expect(page.locator("article.deviation-record")).to_have_count(1)
    expect(page.locator(".show-more-btn")).to_have_count(0)
    expect(page.locator(".chunk-text.clamped")).to_have_count(0)


def test_page_is_read_only_with_no_edit_or_delete_controls(page, live_server_url, stub_state):
    stub_state.deviations = [_record("r1", "2026-01-01T00:00:00Z")]
    page.goto(f"{live_server_url}/deviations.html")
    expect(page.locator("article.deviation-record")).to_have_count(1)

    assert page.get_by_role("button", name="Edit").count() == 0
    assert page.get_by_role("button", name="Delete").count() == 0
    assert page.locator("article.deviation-record button:not(.show-more-btn)").count() == 0
    assert page.locator("article.deviation-record input, article.deviation-record textarea").count() == 0


def test_document_landmarks_and_title(page, live_server_url, stub_state):
    page.goto(f"{live_server_url}/deviations.html")
    expect(page.locator("main")).to_have_count(1)
    assert page.locator("html").get_attribute("lang") == "en"
    assert "Deviations" in page.title()


def test_nav_links_exist_on_index_and_manage_and_deviations_links_back(page, live_server_url, stub_state):
    for path in ("/", "/manage.html"):
        page.goto(f"{live_server_url}{path}")
        link = page.locator("header a.nav-link[href='/deviations.html']")
        expect(link).to_have_count(1)
        expect(link).to_have_text("Deviations")

    page.goto(f"{live_server_url}/manage.html")
    page.locator("header a.nav-link[href='/deviations.html']").click()
    expect(page).to_have_url(f"{live_server_url}/deviations.html")

    expect(page.locator("header a.nav-link[href='/']")).to_have_count(1)
    expect(page.locator("header a.nav-link[href='/manage.html']")).to_have_count(1)
    page.locator("header a.nav-link[href='/manage.html']").click()
    expect(page).to_have_url(f"{live_server_url}/manage.html")


def test_very_long_unbroken_text_does_not_overflow_page_width(page, live_server_url, stub_state):
    stub_state.deviations = [_record("wide", "2026-01-01T00:00:00Z", dispatcherTranscript="x" * 600)]
    page.set_viewport_size({"width": 375, "height": 800})
    page.goto(f"{live_server_url}/deviations.html")
    expect(page.locator("article.deviation-record")).to_have_count(1)

    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 0
