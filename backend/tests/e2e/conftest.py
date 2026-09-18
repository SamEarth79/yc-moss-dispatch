"""E2E test harness for the manage.html page.

The real FastAPI app (server.py) requires live MOSS_PROJECT_ID/MOSS_PROJECT_KEY
credentials and a network call to Moss at startup (see server.lifespan), which
aren't available in this environment. This harness instead spins up a small
stub FastAPI app that serves the SAME static files (manage.html/manage.js/
style.css, unchanged) and exposes the SAME two routes MOS-STORY-001-001
already built and feature-tested against a real Moss client contract
(backend/test_server.py) — but backed by fixture data instead of a real Moss
client. This exercises the frontend's consumption of an already-verified API
contract, not a claim about Moss's real behavior.
"""

import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"


class StubState:
    """Mutable per-test response configuration for the two stubbed routes."""

    def __init__(self):
        self.indexes = []
        self.indexes_status = 200
        self.docs_by_index = {}
        self.docs_status = 200


def build_stub_app(state: StubState) -> FastAPI:
    app = FastAPI()

    @app.get("/api/indexes")
    async def list_indexes():
        if state.indexes_status != 200:
            raise HTTPException(status_code=state.indexes_status, detail="stub failure")
        return state.indexes

    @app.get("/api/indexes/{name}/docs")
    async def get_index_docs(name: str):
        if state.docs_status != 200:
            raise HTTPException(status_code=state.docs_status, detail="stub failure")
        if name not in state.docs_by_index:
            raise HTTPException(status_code=404, detail=f"Index '{name}' not found")
        return state.docs_by_index[name]

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def stub_state():
    return StubState()


@pytest.fixture
def live_server_url(stub_state):
    port = _free_port()
    app = build_stub_app(stub_state)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("stub server failed to start within timeout")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)
