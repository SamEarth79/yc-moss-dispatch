"""
The core "prove Moss is load-bearing" loop (Plan.md §6, build step 2): as a simulated
partial transcript grows tick by tick, fire a Moss query on every tick and render what
the dispatcher's live panel would show — matched instruction, priority badge, suggested
action, and per-tick retrieval latency.

Also hooks in the live data index (Plan.md §1/§10): unlike the protocol panel, address
history and facility routing are looked up once when the caller's location is known, not
on every transcript tick — see architecture diagram in Plan.md §2.
"""

import asyncio
import os
import time

from dotenv import load_dotenv
from moss import MossClient, QueryOptions

from asr_simulator import simulate_partial_transcript
from query_nearest_facility import nearest_facility

PROTOCOL_INDEX_NAME = "protocol-index"
LIVE_DATA_INDEX_NAME = "live-data-index"

CALL_SCRIPT = (
    "my dad is choking on food he can't speak and he's turning blue and now he's collapsed"
)

# Simulated caller location (#4 geocoding isn't built yet, so this stands in for it).
# Deliberately reuses one of the seeded synthetic incident addresses so the address-history
# lookup below has something real to surface.
CALLER_ADDRESS = "7 Maple Court"
CALLER_COUNTY = "Albany"
CALLER_LAT, CALLER_LON = 42.6526, -73.7562

# Query on a trailing window of the transcript, not the full accumulated string — a full
# growing transcript dilutes new signal (see Plan.md investigation): by the end, new
# critical words are a shrinking fraction of an ever-longer sentence, so the retrieval
# stays anchored to whatever topic was established early on. A sliding window keeps the
# query dominated by what the caller is saying right now.
WINDOW_WORDS = 8


def trailing_window(text: str, n: int) -> str:
    words = text.split(" ")
    return " ".join(words[-n:])


async def main():
    load_dotenv()
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")

    if not project_id or not project_key:
        raise RuntimeError("Missing MOSS_PROJECT_ID / MOSS_PROJECT_KEY in .env")

    client = MossClient(project_id, project_key)

    print("Loading protocol-index and live-data-index into memory for local queries...\n")
    await client.load_indexes([PROTOCOL_INDEX_NAME, LIVE_DATA_INDEX_NAME])

    print(f"=== Caller location resolved: {CALLER_ADDRESS}, {CALLER_COUNTY} County, NY ===\n")

    history = await client.query(
        LIVE_DATA_INDEX_NAME,
        "prior incidents",
        QueryOptions(top_k=5, filter={"field": "address", "condition": {"$eq": CALLER_ADDRESS}}),
    )
    print(f"-- Past incidents at {CALLER_ADDRESS} --")
    if history.docs:
        for d in history.docs:
            print(f"   [{d.metadata.get('date')}] {d.metadata.get('incidentType')} — {d.metadata.get('outcome')}")
            if d.metadata.get("hazardFlag") != "none":
                print(f"   ⚠ HAZARD FLAG: {d.metadata.get('hazardFlag')}")
    else:
        print("   (none on file)")
    print()

    ranked_facilities = await nearest_facility(client, CALLER_LAT, CALLER_LON, CALLER_COUNTY)
    print("-- Nearest facility --")
    if ranked_facilities:
        nearest = ranked_facilities[0]
        print(f"   {nearest.metadata['name']} ({nearest.metadata['address']}, {nearest.metadata['city']})")
    else:
        print("   (no facility found in county)")
    print()

    call_start = time.monotonic()
    last_shown_id = None

    async for partial in simulate_partial_transcript(CALL_SCRIPT, interval_seconds=0.2):
        elapsed = time.monotonic() - call_start
        query_text = trailing_window(partial, WINDOW_WORDS)
        result = await client.query(PROTOCOL_INDEX_NAME, query_text, QueryOptions(top_k=1))
        top = result.docs[0]

        changed = " <- PANEL UPDATED" if top.id != last_shown_id else ""
        last_shown_id = top.id

        print(f"[t={elapsed:5.2f}s] transcript: \"{partial}\"  (queried: \"{query_text}\")")
        print(
            f"           [{result.time_taken_ms}ms] {top.id} "
            f"(priority={top.metadata.get('priority')}, action={top.metadata.get('suggestedAction')}){changed}"
        )

    print("\nCall ended. Final panel state:", last_shown_id)


if __name__ == "__main__":
    asyncio.run(main())
