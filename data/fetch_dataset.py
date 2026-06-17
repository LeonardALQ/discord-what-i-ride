"""
fetch_dataset.py
================
OPTIONAL dataset enrichment. Pulls motorcycle records from the free
API Ninjas Motorcycles API (https://api-ninjas.com/api/motorcycles) and merges
them into data/bikes.csv so coverage grows beyond the curated seed.

The bot works fine WITHOUT running this — data/bikes.csv already ships with a
curated, offline dataset (see build_seed.py). Use this only to expand coverage.

Setup:
    1. Get a free key at https://api-ninjas.com (free tier).
    2. export API_NINJAS_KEY=your_key
    3. python data/fetch_dataset.py

The API is queried per make with offset pagination (30 results/page). We query
a list of well-known makes; add more to MAKES as needed.
"""
from __future__ import annotations

import csv
import os
import sys
import time
import urllib.parse
import urllib.request

API_URL = "https://api.api-ninjas.com/v1/motorcycles"
SEED_PATH = os.path.join(os.path.dirname(__file__), "bikes.csv")

MAKES = [
    "Honda", "Yamaha", "Kawasaki", "Suzuki", "Ducati", "BMW", "KTM",
    "Harley-Davidson", "Triumph", "Aprilia", "Royal Enfield", "Husqvarna",
    "Indian", "Moto Guzzi", "MV Agusta", "Benelli", "CFMoto", "Zero",
    "Kymco", "Piaggio", "Vespa", "Gas Gas", "Beta", "Sherco", "Bajaj",
    "Hero", "TVS", "Norton", "Bimota", "Can-Am",
]

FIELDNAMES = ["make", "model", "badge", "category", "displacement_cc", "year"]


def _request(make: str, offset: int, key: str) -> list[dict]:
    qs = urllib.parse.urlencode({"make": make, "offset": offset})
    req = urllib.request.Request(
        f"{API_URL}?{qs}", headers={"X-Api-Key": key}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        import json

        return json.loads(resp.read().decode("utf-8"))


def _displacement_cc(raw: str) -> int:
    # API returns e.g. "999.0 ccm" — extract leading number.
    if not raw:
        return 0
    num = ""
    for ch in raw:
        if ch.isdigit() or ch == ".":
            num += ch
        elif num:
            break
    try:
        return int(float(num))
    except ValueError:
        return 0


def fetch_make(make: str, key: str, max_pages: int = 10) -> list[dict]:
    rows: list[dict] = []
    for page in range(max_pages):
        offset = page * 30
        try:
            batch = _request(make, offset, key)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {make} offset {offset}: {exc}")
            break
        if not batch:
            break
        for item in batch:
            rows.append(
                {
                    "make": item.get("make", make).strip(),
                    "model": item.get("model", "").strip(),
                    "badge": "",
                    "category": item.get("type", "").strip(),
                    "displacement_cc": _displacement_cc(item.get("displacement", "")),
                    "year": (item.get("year", "") or "").strip(),
                }
            )
        time.sleep(0.3)  # be polite to the API
    return rows


def load_existing() -> tuple[list[dict], set[tuple]]:
    rows: list[dict] = []
    seen: set[tuple] = set()
    if not os.path.exists(SEED_PATH):
        return rows, seen
    with open(SEED_PATH, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)
            seen.add((row["make"].lower(), row["model"].lower(),
                      row.get("badge", "").lower(), str(row.get("year", ""))))
    return rows, seen


def main() -> None:
    key = os.environ.get("API_NINJAS_KEY")
    if not key:
        print("API_NINJAS_KEY not set. Get a free key at https://api-ninjas.com")
        sys.exit(1)

    rows, seen = load_existing()
    print(f"Loaded {len(rows)} existing rows.")
    added = 0
    for make in MAKES:
        print(f"Fetching {make} ...")
        for row in fetch_make(make, key):
            if not row["model"]:
                continue
            dedup = (row["make"].lower(), row["model"].lower(),
                     row["badge"].lower(), str(row["year"]))
            if dedup in seen:
                continue
            seen.add(dedup)
            rows.append(row)
            added += 1

    with open(SEED_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Added {added} new rows. Total now {len(rows)}.")


if __name__ == "__main__":
    main()
