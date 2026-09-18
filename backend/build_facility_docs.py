import asyncio
import os

from dotenv import load_dotenv
from moss import DocumentInfo, MossClient

from facility_chunks import FACILITY_CHUNKS

LIVE_DATA_INDEX_NAME = "live-data-index"


async def main():
    load_dotenv()
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")

    if not project_id or not project_key:
        raise RuntimeError("Missing MOSS_PROJECT_ID / MOSS_PROJECT_KEY in .env")

    client = MossClient(project_id, project_key)

    docs = [
        DocumentInfo(id=chunk["id"], text=chunk["text"], metadata=chunk["metadata"])
        for chunk in FACILITY_CHUNKS
    ]

    print(f'Adding {len(docs)} facility records to "{LIVE_DATA_INDEX_NAME}" (upsert, incidents untouched)...')
    result = await client.add_docs(LIVE_DATA_INDEX_NAME, docs)
    print(f"Done: job_id={result.job_id} index_name={result.index_name} doc_count={result.doc_count}")


asyncio.run(main())
