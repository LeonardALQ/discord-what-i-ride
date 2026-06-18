"""
build_supplement.py
====================
Generates data/supplement.csv: a small, curated set of niche bikes that the
imported bikez base (data/imported.csv) is missing or under-covers.

This is NOT the main dataset — the ~38k-row imported.csv is. Keep this list
tight: only add makes/models the base genuinely lacks (verified against
imported.csv). The loader merges both and de-dupes.

Run:
    python data/build_supplement.py
"""
from __future__ import annotations

import csv
import os

CURRENT_YEAR = 2025

# Same extended schema as data/imported.csv (extras left blank here).
FIELDNAMES = [
    "make", "model", "badge", "category", "displacement_cc", "year",
    "power_hp", "engine", "cooling", "gearbox", "transmission",
    "dry_weight_kg", "seat_height_mm", "fuel_capacity_l", "wheelbase_mm",
]

# make -> (model, badge, category, displacement_cc, year_start, year_end)
SPEC: dict[str, list[tuple]] = {
    # Not in bikez at all:
    "Kraemer": [
        ("GP2 690", "", "Track", 693, 2018, CURRENT_YEAR),
        ("GP2 690", "R", "Track", 693, 2020, CURRENT_YEAR),
        ("APR690", "", "Track", 693, 2021, CURRENT_YEAR),
        ("APR690", "RR", "Track", 693, 2022, CURRENT_YEAR),
        ("890RR", "", "Track", 889, 2022, CURRENT_YEAR),
    ],
    "Stark Future": [
        ("Varg", "", "Motocross", 0, 2022, CURRENT_YEAR),
        ("Varg", "EX", "Motocross", 0, 2024, CURRENT_YEAR),
        ("Varg", "Alpha", "Motocross", 0, 2022, CURRENT_YEAR),
    ],
    "Sur-Ron": [
        ("Light Bee", "X", "Off-road", 0, 2019, CURRENT_YEAR),
        ("Storm Bee", "", "Off-road", 0, 2021, CURRENT_YEAR),
        ("Ultra Bee", "", "Off-road", 0, 2023, CURRENT_YEAR),
    ],
    "Talaria": [
        ("Sting", "", "Off-road", 0, 2021, CURRENT_YEAR),
        ("Sting", "R MX4", "Off-road", 0, 2022, CURRENT_YEAR),
        ("XXX", "", "Off-road", 0, 2022, CURRENT_YEAR),
    ],
    # Under-covered in bikez (adds detailed mini-GP variants):
    "Ohvale": [
        ("GP-0", "110", "Mini GP", 110, 2016, CURRENT_YEAR),
        ("GP-0", "160", "Mini GP", 160, 2016, CURRENT_YEAR),
        ("GP-0", "190 Daytona", "Mini GP", 187, 2018, CURRENT_YEAR),
        ("GP-0", "212 Daytona", "Mini GP", 212, 2019, CURRENT_YEAR),
        ("GP-2", "190 Daytona", "Mini GP", 187, 2020, CURRENT_YEAR),
        ("GP-2", "212 Daytona", "Mini GP", 212, 2020, CURRENT_YEAR),
    ],
}


def build_rows() -> list[dict]:
    rows: list[dict] = []
    for make, entries in SPEC.items():
        for model, badge, category, cc, y_start, y_end in entries:
            for year in range(y_start, y_end + 1):
                row = {f: "" for f in FIELDNAMES}
                row.update({
                    "make": make, "model": model, "badge": badge,
                    "category": category, "displacement_cc": cc, "year": year,
                })
                rows.append(row)
    return rows


def main() -> None:
    out_path = os.path.join(os.path.dirname(__file__), "supplement.csv")
    rows = build_rows()
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} supplement rows across {len(SPEC)} makes to {out_path}")


if __name__ == "__main__":
    main()
