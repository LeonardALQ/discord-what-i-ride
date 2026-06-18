"""
dataset.py
==========
Loads the motorcycle dataset and collapses per-year rows into unique
(make, model, badge) records with a year range and full spec set.

Two sources are merged:
  - data/imported.csv   the comprehensive base (~38k rows, from Kaggle bikez)
  - data/supplement.csv  a small curated set of niche bikes the base misses

Records present only in the supplement are added; the base wins on overlap.
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
IMPORTED_PATH = os.path.join(_DATA_DIR, "imported.csv")
SUPPLEMENT_PATH = os.path.join(_DATA_DIR, "supplement.csv")

# Extra spec fields carried from the source (all optional, may be blank).
SPEC_FIELDS = (
    "power_hp", "engine", "cooling", "gearbox", "transmission",
    "dry_weight_kg", "seat_height_mm", "fuel_capacity_l", "wheelbase_mm",
)


@dataclass
class BikeRecord:
    make: str
    model: str
    badge: str
    category: str
    displacement_cc: int
    year_min: int
    year_max: int
    specs: dict[str, str] = field(default_factory=dict, repr=False)
    _years: set[int] = field(default_factory=set, repr=False)

    @property
    def display_name(self) -> str:
        parts = [self.make, self.model]
        if self.badge:
            parts.append(self.badge)
        return " ".join(p for p in parts if p)

    @property
    def search_blob(self) -> str:
        return f"{self.make} {self.model} {self.badge}".strip()

    @property
    def year_label(self) -> str:
        if not self.year_max:
            return "—"
        if self.year_min == self.year_max:
            return str(self.year_min)
        return f"{self.year_min}-{self.year_max}"

    def covers_year(self, year: int) -> bool:
        return self.year_min <= year <= self.year_max

    def spec(self, key: str) -> str:
        return (self.specs.get(key) or "").strip()


def _to_int(raw: str) -> int:
    raw = (raw or "").strip()
    if not raw:
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _ingest(path: str, grouped: dict[tuple, BikeRecord]) -> None:
    if not os.path.exists(path):
        return
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            make = (row.get("make") or "").strip()
            model = (row.get("model") or "").strip()
            if not make or not model:
                continue
            badge = (row.get("badge") or "").strip()
            category = (row.get("category") or "").strip()
            cc = _to_int(row.get("displacement_cc"))
            year = _to_int(row.get("year"))

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
            # Fill any missing spec fields from this row.
            for f in SPEC_FIELDS:
                val = (row.get(f) or "").strip()
                if val and not rec.specs.get(f):
                    rec.specs[f] = val


def load_records(imported: str | None = None,
                 supplement: str | None = None) -> list[BikeRecord]:
    imported = imported or IMPORTED_PATH
    supplement = supplement or SUPPLEMENT_PATH
    if not os.path.exists(imported) and not os.path.exists(supplement):
        raise FileNotFoundError(
            f"No dataset found. Expected {imported} (run data/import_kaggle.py) "
            f"and/or {supplement} (run data/build_supplement.py)."
        )

    grouped: dict[tuple, BikeRecord] = {}
    _ingest(imported, grouped)     # base first (wins on overlap)
    _ingest(supplement, grouped)   # niche extras fill gaps

    records = list(grouped.values())
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
