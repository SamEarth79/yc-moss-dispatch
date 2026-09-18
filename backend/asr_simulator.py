"""
Fakes a streaming ASR partial-transcript feed. Real streaming ASR (Deepgram/AssemblyAI/
Whisper streaming) emits a growing string every ~100-300ms as the caller speaks; this
yields the same shape (an async stream of growing partial strings on a timer) so swapping
in a real ASR source later is a source-swap, not a redesign. See Plan.md §6, build step 2.
"""

import asyncio


async def simulate_partial_transcript(full_text: str, interval_seconds: float = 0.2):
    """Yields the transcript growing one word at a time, paced like live speech."""
    words = full_text.split(" ")
    for i in range(1, len(words) + 1):
        yield " ".join(words[:i])
        await asyncio.sleep(interval_seconds)
