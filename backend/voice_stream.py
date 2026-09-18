"""
Streaming speech-to-text: relays raw 16 kHz mono PCM chunks from the browser to
Deepgram's live endpoint and reports the running transcript. Deepgram sends "interim"
results (the phrase currently being spoken, revised as more audio arrives) and "final"
results (a phrase that is locked in); the full transcript is every final phrase plus the
current interim one. Requires DEEPGRAM_API_KEY in .env.
"""

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from urllib.parse import urlencode

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

DEEPGRAM_URL = "wss://api.deepgram.com/v1/listen?" + urlencode(
    {
        "model": "nova-3",
        "encoding": "linear16",
        "sample_rate": 16000,
        "channels": 1,
        "interim_results": "true",
        "smart_format": "true",
        "endpointing": 300,
    }
)
KEEPALIVE_SECONDS = 5

TranscriptCallback = Callable[[str, bool], Awaitable[None]]


class VoiceStreamUnavailable(Exception):
    pass


class DeepgramStream:
    def __init__(self, on_transcript: TranscriptCallback):
        self._on_transcript = on_transcript
        self._committed: list[str] = []
        self._connection = None
        self._reader_task: asyncio.Task | None = None
        self._keepalive_task: asyncio.Task | None = None

    async def start(self):
        api_key = os.getenv("DEEPGRAM_API_KEY")
        if not api_key:
            raise VoiceStreamUnavailable("Speech-to-text is not configured")
        try:
            self._connection = await connect(DEEPGRAM_URL, additional_headers={"Authorization": f"Token {api_key}"})
        except OSError as exc:
            raise VoiceStreamUnavailable("Speech-to-text service unreachable") from exc
        self._reader_task = asyncio.create_task(self._read_results())
        self._keepalive_task = asyncio.create_task(self._keep_alive())

    async def send_audio(self, chunk: bytes):
        if self._connection is not None:
            await self._connection.send(chunk)

    async def stop(self):
        if self._connection is not None:
            try:
                await self._connection.send(json.dumps({"type": "CloseStream"}))
                if self._reader_task is not None:
                    await asyncio.wait_for(self._reader_task, timeout=3)
            except (asyncio.TimeoutError, ConnectionClosed):
                pass
            await self._connection.close()
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()

    async def _keep_alive(self):
        while True:
            await asyncio.sleep(KEEPALIVE_SECONDS)
            await self._connection.send(json.dumps({"type": "KeepAlive"}))

    async def _read_results(self):
        async for raw in self._connection:
            message = json.loads(raw)
            if message.get("type") != "Results":
                continue
            text = message["channel"]["alternatives"][0]["transcript"].strip()
            if not text:
                continue
            is_final = message.get("is_final", False)
            if is_final:
                self._committed.append(text)
                full_text = " ".join(self._committed)
            else:
                full_text = " ".join([*self._committed, text])
            await self._on_transcript(full_text, is_final)
