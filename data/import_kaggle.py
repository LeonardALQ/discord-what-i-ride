"""
import_kaggle.py
================
Builds the comprehensive base dataset (data/imported.csv) from the Kaggle
"all_bikez_curated" dataset (~38k models from the bikez.com catalog).

It carries through the full spec set the source provides (power, engine,
cooling, gearbox, transmission, dry weight, seat height, fuel capacity,
wheelbase) in addition to make/model/category/displacement/year.

Auth: uses ~/.kaggle/kaggle.json (username + key). Set up once with your
Kaggle credentials. The generated data/imported.csv is committed, so the
deployed bot never needs Kaggle access.

Run:
    python data/import_kaggle.py
"""
from __future__ import annotations

import csv
import glob
import os
import tempfile

# Extended schema shared with build_supplement.py and src/dataset.py.
FIELDNAMES = [
    "make", "model", "badge", "category", "displacement_cc", "year",
    "power_hp", "engine", "cooling", "gearbox", "transmission",
    "dry_weight_kg", "seat_height_mm", "fuel_capacity_l", "wheelbase_mm",
]

OUT_PATH = os.path.join(os.path.dirname(__file__), "imported.csv")

CURATED_DATASET = "mahmoudshogaa/all-bikez-curated-data-cleaning"
BRANDS_DATASET = "dtahuy02/bikez-motorcycle-dataset"
BRANDS_FILE = "bikez_brands.csv"

# Source column -> our field.
COLMAP = {
    "Category": "category",
    "Power (hp)": "power_hp",
    "Engine cylinder": "engine",
    "Gearbox": "gearbox",
    "Transmission type": "transmission",
    "Dry weight (kg)": "dry_weight_kg",
    "Seat height (mm)": "seat_height_mm",
    "Fuel capacity (lts)": "fuel_capacity_l",
    "Wheelbase (mm)": "wheelbase_mm",
    "Cooling system": "cooling",
}

# Casing fallbacks for brands not found in the canonical brands list.
ACRONYMS = {
    "bmw", "ktm", "mv", "mz", "ncr", "tvs", "sym", "swm", "ajp", "ajs",
    "nsu", "dkw", "bsa", "apc", "atk", "um", "izh", "fb", "cf", "cfmoto",
    "gas", "kre", "uk", "usa",
}


def _to_int(raw: str) -> int:
    if not raw:
        return 0
    num = ""
    for ch in str(raw):
        if ch.isdigit() or ch == ".":
            num += ch
        elif num:
            break
    try:
        return int(float(num))
    except ValueError:
        return 0


def _title(brand: str) -> str:
    parts = []
    for w in brand.split():
        parts.append(w.upper() if w.lower() in ACRONYMS else w.capitalize())
    return " ".join(parts)


def smart_case(text: str) -> str:
    """Display-case a lowercase model string.

    Uppercases model codes (anything with a digit) and short tokens (<=3 chars,
    e.g. CBR, GS, RR, SP); title-cases real words (Africa -> Africa). Handles
    spaces, hyphens and slashes: "v-strom 1050" -> "V-Strom 1050",
    "cbr1000rr" -> "CBR1000RR", "africa twin" -> "Africa Twin".
    """
    import re

    def case_piece(p: str) -> str:
        if not p:
            return p
        if any(c.isdigit() for c in p) or len(p) <= 3:
            return p.upper()
        return p[0].upper() + p[1:]

    tokens = re.split(r"([ /-])", text)
    return "".join(t if t in " /-" else case_piece(t) for t in tokens)


def _authenticate():
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    return api


def _load_brand_casing(api, tmp: str) -> dict[str, str]:
    """lowercase brand -> canonical-cased brand, from bikez_brands.csv."""
    casing: dict[str, str] = {}
    try:
        api.dataset_download_file(BRANDS_DATASET, BRANDS_FILE, path=tmp)
        # File may arrive as bikez_brands.csv or bikez_brands.csv.zip.
        path = os.path.join(tmp, BRANDS_FILE)
        if not os.path.exists(path):
            import zipfile
            zp = path + ".zip"
            if os.path.exists(zp):
                with zipfile.ZipFile(zp) as z:
                    z.extractall(tmp)
        if os.path.exists(path):
            with open(path, newline="", encoding="utf-8") as fh:
                for row in csv.reader(fh):
                    if row and row[0] and row[0] != "Brand":
                        casing[row[0].strip().lower()] = row[0].strip()
    except Exception as exc:  # noqa: BLE001
        print(f"  (brand casing unavailable, using title-case fallback: {exc})")
    return casing


def _find_curated_csv(tmp: str) -> str:
    matches = glob.glob(os.path.join(tmp, "*.csv"))
    if not matches:
        raise FileNotFoundError("Curated CSV not found after download.")
    # Prefer the curated file if multiple.
    for m in matches:
        if "curated" in os.path.basename(m).lower():
            return m
    return matches[0]


def main() -> None:
    api = _authenticate()
    with tempfile.TemporaryDirectory() as tmp:
        print(f"Downloading {CURATED_DATASET} ...")
        api.dataset_download_files(CURATED_DATASET, path=tmp, unzip=True)
        casing = _load_brand_casing(api, tmp)
        csv_path = _find_curated_csv(tmp)
        print(f"Reading {os.path.basename(csv_path)} ...")

        seen: set[tuple] = set()
        rows: list[dict] = []
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for src in reader:
                brand = (src.get("Brand") or "").strip()
                model = (src.get("Model") or "").strip()
                if not brand or not model:
                    continue
                make = casing.get(brand.lower(), _title(brand))
                model = smart_case(model)
                year = _to_int(src.get("Year"))
                dedup = (make.lower(), model.lower(), year)
                if dedup in seen:
                    continue
                seen.add(dedup)

                row = {f: "" for f in FIELDNAMES}
                row["make"] = make
                row["model"] = model
                row["badge"] = ""
                row["displacement_cc"] = _to_int(src.get("Displacement (ccm)"))
                row["year"] = year
                for src_col, our in COLMAP.items():
                    val = (src.get(src_col) or "").strip()
                    if our in ("dry_weight_kg", "seat_height_mm",
                               "fuel_capacity_l", "wheelbase_mm"):
                        row[our] = val  # keep raw (may include units/blank)
                    else:
                        row[our] = val
                rows.append(row)

        rows.sort(key=lambda r: (r["make"].lower(), r["model"].lower(),
                                 str(r["year"])))
        with open(OUT_PATH, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

    makes = len({r["make"] for r in rows})
    print(f"\nWrote {len(rows)} rows across {makes} makes to {OUT_PATH}")


if __name__ == "__main__":
    main()
