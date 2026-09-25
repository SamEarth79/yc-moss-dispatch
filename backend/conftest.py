import pytest

import deviation_judge


@pytest.fixture(autouse=True)
def jev_unavailable_by_default(monkeypatch):
    async def no_verdict(*args, **kwargs):
        return None

    monkeypatch.setattr(deviation_judge, "decide_follows", no_verdict)
