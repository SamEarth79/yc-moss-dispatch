import asyncio
import os

from dotenv import load_dotenv
from moss import DocumentInfo, MossClient

from deviation_seed import DEVIATION_SEEDS
from live_panel import DEVIATION_INDEX_NAME


async def main():
    load_dotenv()
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")

    if not project_id or not project_key:
        raise RuntimeError("Missing MOSS_PROJECT_ID / MOSS_PROJECT_KEY in .env")

    client = MossClient(project_id, project_key)

    docs = [
        DocumentInfo(id=seed["id"], text=seed["text"], metadata=seed["metadata"])
        for seed in DEVIATION_SEEDS
    ]

    existing = await client.list_indexes()
    if any(index.name == DEVIATION_INDEX_NAME for index in existing):
        print(f'Index "{DEVIATION_INDEX_NAME}" already exists — deleting before rebuild...')
        await client.delete_index(DEVIATION_INDEX_NAME)

    print(f'Creating index "{DEVIATION_INDEX_NAME}" with {len(docs)} deviations...')
    result = await client.create_index(DEVIATION_INDEX_NAME, docs)
    print(f"Done: job_id={result.job_id} index_name={result.index_name} doc_count={result.doc_count}")


asyncio.run(main())
