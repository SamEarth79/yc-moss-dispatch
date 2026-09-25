import pytest

import deviation_judge
import server


@pytest.fixture(autouse=True)
def jev_unavailable_by_default(monkeypatch):
    async def no_verdict(*args, **kwargs):
        return None

    monkeypatch.setattr(deviation_judge, "decide_follows", no_verdict)


@pytest.fixture(autouse=True)
def jev_extraction_unavailable_by_default(monkeypatch):
    async def no_answers(*args, **kwargs):
        return None

    monkeypatch.setattr(server, "decide_extraction", no_answers)


@pytest.fixture(autouse=True)
def jev_applies_to_summary_in_tests(monkeypatch):
    monkeypatch.setenv("JEV_AFFECTS_SUMMARY", "true")
