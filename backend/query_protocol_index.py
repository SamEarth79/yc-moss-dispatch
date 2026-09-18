import asyncio
import os

from dotenv import load_dotenv
from moss import MossClient, QueryOptions

PROTOCOL_INDEX_NAME = "protocol-index"

# Simulates a streaming partial-transcript sequence (a real ASR integration would
# replace this list with live partials) to prove the retrieval loop can keep up
# with a query fired on every tick. See Plan.md §6 build order, step 2.
SIMULATED_PARTIAL_TRANSCRIPT = [
    "my",
    "my dad",
    "my dad is choking",
    "my dad is choking on food",
    "my dad is choking on food he can't breathe",
    "my dad is choking on food he can't breathe he's turning blue",
    "my dad is choking on food he can't breathe he's turning blue and now he's collapsed",
]


async def main():
    load_dotenv()
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")

    if not project_id or not project_key:
        raise RuntimeError("Missing MOSS_PROJECT_ID / MOSS_PROJECT_KEY in .env")

    client = MossClient(project_id, project_key)

    print(f'Loading "{PROTOCOL_INDEX_NAME}" into memory for local queries...')
    await client.load_index(PROTOCOL_INDEX_NAME)
    print("Loaded. Querying locally (in-memory).\n")

    for partial in SIMULATED_PARTIAL_TRANSCRIPT:
        result = await client.query(PROTOCOL_INDEX_NAME, partial, QueryOptions(top_k=1))
        top = result.docs[0]

        print(f'> "{partial}"')
        print(f"  [{result.time_taken_ms}ms] {top.id} (score {top.score:.3f})")
        print(f"  priority: {top.metadata.get('priority')}  suggestedAction: {top.metadata.get('suggestedAction')}")
        print(f"  \"{top.text[:100]}...\"\n")


asyncio.run(main())
