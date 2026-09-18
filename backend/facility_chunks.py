"""
Facility records for the live data index (type="facility").

Sourced verbatim from the real NY State hospital directory
(data/docs/facilities/new-york-state-hospitals-facility-directory.csv, 220 rows,
NY DOH open data). Trauma-level filtering is skipped for the MVP — that field isn't
present in this dataset (see Plan.md §8 decision). Rows missing lat/lon are dropped
since geo ranking is the whole point of this record type.
"""

import csv
from pathlib import Path

CSV_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "docs"
    / "facilities"
    / "new-york-state-hospitals-facility-directory.csv"
)


def _load_facility_chunks():
    chunks = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            lat = row["latitude"].strip()
            lon = row["longitude"].strip()
            if not lat or not lon:
                continue

            name = row["facility_name"].strip()
            address = row["address1"].strip()
            city = row["city"].strip()
            county = row["county"].strip()
            phone = row["fac_phone"].strip()
            ownership = row["ownership_type"].strip()

            text = (
                f"{name} is a hospital located at {address}, {city}, {county} County, "
                f"New York. Ownership type: {ownership}. Phone: {phone}."
            )

            chunks.append(
                {
                    "id": f"facility-{i:03d}",
                    "text": text,
                    "metadata": {
                        "type": "facility",
                        "name": name,
                        "address": address,
                        "city": city,
                        "county": county,
                        "phone": phone,
                        "lat": lat,
                        "lon": lon,
                    },
                }
            )
    return chunks


FACILITY_CHUNKS = _load_facility_chunks()
