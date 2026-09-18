import asyncio
import os

from dotenv import load_dotenv
from moss import MossClient, QueryOptions

LIVE_DATA_INDEX_NAME = "live-data-index"


def print_docs(label, docs):
    print(f"{label}")
    for d in docs:
        print(f"   {d.score:.4f}  {d.id}  hazardFlag={d.metadata.get('hazardFlag')}")
        print(f"      \"{d.text[:100]}...\"")
    print()


async def main():
    load_dotenv()
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")

    if not project_id or not project_key:
        raise RuntimeError("Missing MOSS_PROJECT_ID / MOSS_PROJECT_KEY in .env")

    client = MossClient(project_id, project_key)

    print(f'Loading "{LIVE_DATA_INDEX_NAME}" into memory for local queries...\n')
    await client.load_index(LIVE_DATA_INDEX_NAME)

    # 1. Exact-address lookup (this is #3's "past incidents at this address" panel) —
    #    metadata filter, not semantic — we want every record at that address, not the
    #    closest-sounding one.
    result = await client.query(
        LIVE_DATA_INDEX_NAME,
        "prior incidents",
        QueryOptions(top_k=5, filter={"field": "address", "condition": {"$eq": "7 Maple Court"}}),
    )
    print_docs('> filter: address == "7 Maple Court"', result.docs)

    # 2. Semantic query with no address filter — simulates the dispatcher panel surfacing
    #    a similar past incident based on what the current caller is describing.
    result = await client.query(
        LIVE_DATA_INDEX_NAME,
        "infant choking on a toy",
        QueryOptions(top_k=2),
    )
    print_docs('> semantic: "infant choking on a toy"', result.docs)

    # 3. Hazard-flag surfacing — same address filter, checking whether an officer-safety
    #    flag would actually reach the panel alongside the medical history.
    result = await client.query(
        LIVE_DATA_INDEX_NAME,
        "prior incidents",
        QueryOptions(top_k=5, filter={"field": "address", "condition": {"$eq": "900 Cedar Boulevard"}}),
    )
    print_docs('> filter: address == "900 Cedar Boulevard"', result.docs)


asyncio.run(main())
