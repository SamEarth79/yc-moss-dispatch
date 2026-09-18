import asyncio
import math
import os

from dotenv import load_dotenv
from moss import MossClient, QueryOptions

LIVE_DATA_INDEX_NAME = "live-data-index"


def haversine_miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def nearest_facility(client, caller_lat, caller_lon, county):
    """
    Candidate generation (Moss, fast): metadata filter to type=facility, narrowed to
    the caller's county when known. Ranking (app code): real haversine distance over
    that candidate set — this is the retrieve-then-rerank pattern from Plan.md §8/§10,
    since Moss has no $near geo operator. When county is None (e.g. a freeform geocoded
    address Nominatim couldn't resolve a county for), falls back to ranking every
    facility in the index rather than excluding candidates on an unknown field.
    """
    if county:
        query_filter = {
            "$and": [
                {"field": "type", "condition": {"$eq": "facility"}},
                {"field": "county", "condition": {"$eq": county}},
            ]
        }
        top_k = 50
    else:
        query_filter = {"field": "type", "condition": {"$eq": "facility"}}
        top_k = 250

    result = await client.query(
        LIVE_DATA_INDEX_NAME,
        "hospital",
        QueryOptions(top_k=top_k, filter=query_filter),
    )

    ranked = sorted(
        result.docs,
        key=lambda d: haversine_miles(
            caller_lat, caller_lon, float(d.metadata["lat"]), float(d.metadata["lon"])
        ),
    )
    return ranked


async def main():
    load_dotenv()
    client = MossClient(os.getenv("MOSS_PROJECT_ID"), os.getenv("MOSS_PROJECT_KEY"))

    print('Loading "live-data-index" into memory for local queries...\n')
    await client.load_index(LIVE_DATA_INDEX_NAME)

    # Simulated caller location: downtown Albany, NY.
    caller_lat, caller_lon = 42.6526, -73.7562
    county = "Albany"

    ranked = await nearest_facility(client, caller_lat, caller_lon, county)

    print(f"Candidates in {county} County: {len(ranked)}")
    print("Ranked by real distance from caller (haversine):\n")
    for d in ranked[:5]:
        dist = haversine_miles(caller_lat, caller_lon, float(d.metadata["lat"]), float(d.metadata["lon"]))
        print(f"  {dist:5.2f} mi  {d.metadata['name']}  ({d.metadata['address']}, {d.metadata['city']})")


if __name__ == "__main__":
    asyncio.run(main())
