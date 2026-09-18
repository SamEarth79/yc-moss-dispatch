from moss import MossClient
from dotenv import load_dotenv
import asyncio
import os

async def main():
    load_dotenv()
    print("creating MossClient...")
    client = MossClient(os.getenv("MOSS_PROJECT_ID"), os.getenv("MOSS_PROJECT_KEY"))
    print("MossClient created:", client)

    print("calling load_index('protocol-index')...")
    load_result = await client.load_index("protocol-index")
    print("load_index returned:", load_result)

    print("calling query('protocol-index', 'breathe')...")
    results = await client.query("protocol-index", "breathe")
    print("query returned:", results)

    print(f"docs in result: {len(results.docs)}")
    for i, doc in enumerate(results.docs):
        print(f"  [{i}] id={doc.id} score={doc.score:.4f}")
        print(f"      metadata={doc.metadata}")
        print(f"      text={doc.text[:100]!r}")

print("starting asyncio.run(main())...")
asyncio.run(main())
print("asyncio.run(main()) finished")
