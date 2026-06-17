"""
dataset.py
==========
Loads data/bikes.csv and collapses per-year rows into unique
(make, model, badge) records, each carrying its observed year range.
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bikes.csv")


@dataclass
class BikeRecord:
    make: str
    model: str
    badge: str
    category: str
    displacement_cc: int
    year_min: int
    year_max: int
    _years: set[int] = field(default_factory=set, repr=False)

    @property
    def display_name(self) -> str:
        parts = [self.make, self.model]
        if self.badge:
            parts.append(self.badge)
        return " ".join(parts)

    @property
    def search_blob(self) -> str:
        """Normalized text used for fuzzy matching."""
        return f"{self.make} {self.model} {self.badge}".strip()

    @property
    def year_label(self) -> str:
        if self.year_min == self.year_max:
            return str(self.year_min)
        return f"{self.year_min}-{self.year_max}"

    def covers_year(self, year: int) -> bool:
        return self.year_min <= year <= self.year_max


def load_records(path: str | None = None) -> list[BikeRecord]:
    path = path or DATA_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Dataset not found at {path}. Run: python data/build_seed.py"
        )

    grouped: dict[tuple, BikeRecord] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            make = (row.get("make") or "").strip()
            model = (row.get("model") or "").strip()
            badge = (row.get("badge") or "").strip()
            if not make or not model:
                continue
            category = (row.get("category") or "").strip()
            try:
                cc = int(float(row.get("displacement_cc") or 0))
            except ValueError:
                cc = 0
            year_raw = (row.get("year") or "").strip()
            try:
                year = int(float(year_raw)) if year_raw else 0
            except ValueError:
                year = 0

            key = (make.lower(), model.lower(), badge.lower())
            rec = grouped.get(key)
            if rec is None:
                rec = BikeRecord(
                    make=make, model=model, badge=badge, category=category,
                    displacement_cc=cc, year_min=year or 9999, year_max=year or 0,
                )
                grouped[key] = rec
            if year:
                rec._years.add(year)
                rec.year_min = min(rec.year_min, year)
                rec.year_max = max(rec.year_max, year)
            if cc and not rec.displacement_cc:
                rec.displacement_cc = cc
            if category and not rec.category:
                rec.category = category

    records = list(grouped.values())
    # Fix records that never got a real year.
    for rec in records:
        if rec.year_min == 9999:
            rec.year_min = rec.year_max = 0
    return records


def all_makes(records: list[BikeRecord]) -> list[str]:
    return sorted({r.make for r in records})


if __name__ == "__main__":
    recs = load_records()
    print(f"Loaded {len(recs)} unique model records across "
          f"{len(all_makes(recs))} makes.")
