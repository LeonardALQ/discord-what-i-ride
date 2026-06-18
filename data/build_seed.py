"""
build_seed.py
=============
Expands a compact, curated spec of real motorcycle model families into a
comprehensive row-per-(make, model, badge, year) CSV at data/bikes.csv.

The spec below is hand-curated from well-known model lineups. Each entry is:

    (model, badge, category, displacement_cc, year_start, year_end)

`build_seed.py` explodes every entry across its year range, producing a
dataset of several thousand rows that works fully offline. To expand coverage
further, see data/fetch_dataset.py (pulls from the API Ninjas Motorcycles API).

Run:
    python data/build_seed.py
"""
from __future__ import annotations

import csv
import os

# Cap year ranges that are still "current" so we don't invent future models.
CURRENT_YEAR = 2025

# make -> list of (model, badge, category, displacement_cc, year_start, year_end)
SPEC: dict[str, list[tuple]] = {
    "Honda": [
        ("CBR1000RR", "Fireblade", "Sport", 999, 2004, 2019),
        ("CBR1000RR-R", "Fireblade SP", "Sport", 1000, 2020, CURRENT_YEAR),
        ("CBR600RR", "", "Sport", 599, 2003, CURRENT_YEAR),
        ("CBR650R", "", "Sport", 649, 2019, CURRENT_YEAR),
        ("CBR500R", "", "Sport", 471, 2013, CURRENT_YEAR),
        ("CB1000R", "Neo Sports Cafe", "Naked", 998, 2018, CURRENT_YEAR),
        ("CB650R", "", "Naked", 649, 2019, CURRENT_YEAR),
        ("CB500F", "", "Naked", 471, 2013, CURRENT_YEAR),
        ("CB300R", "", "Naked", 286, 2018, CURRENT_YEAR),
        ("Africa Twin", "CRF1100L", "Adventure", 1084, 2020, CURRENT_YEAR),
        ("Africa Twin", "CRF1000L", "Adventure", 998, 2016, 2019),
        ("NC750X", "", "Adventure", 745, 2014, CURRENT_YEAR),
        ("Gold Wing", "Tour", "Touring", 1833, 2018, CURRENT_YEAR),
        ("Rebel 500", "CMX500", "Cruiser", 471, 2017, CURRENT_YEAR),
        ("Rebel 1100", "CMX1100", "Cruiser", 1084, 2021, CURRENT_YEAR),
        ("CRF300L", "", "Dual Sport", 286, 2021, CURRENT_YEAR),
        ("CRF450R", "", "Motocross", 449, 2002, CURRENT_YEAR),
        ("Grom", "MSX125", "Mini", 124, 2014, CURRENT_YEAR),
        ("Monkey", "", "Mini", 124, 2019, CURRENT_YEAR),
    ],
    "Yamaha": [
        ("YZF-R1", "", "Sport", 998, 2004, CURRENT_YEAR),
        ("YZF-R1", "M", "Sport", 998, 2015, CURRENT_YEAR),
        ("YZF-R6", "", "Sport", 599, 2003, 2020),
        ("YZF-R7", "", "Sport", 689, 2022, CURRENT_YEAR),
        ("YZF-R3", "", "Sport", 321, 2015, CURRENT_YEAR),
        ("MT-10", "", "Naked", 998, 2016, CURRENT_YEAR),
        ("MT-09", "", "Naked", 889, 2014, CURRENT_YEAR),
        ("MT-07", "", "Naked", 689, 2014, CURRENT_YEAR),
        ("MT-03", "", "Naked", 321, 2016, CURRENT_YEAR),
        ("Tenere 700", "T7", "Adventure", 689, 2019, CURRENT_YEAR),
        ("Super Tenere", "XT1200Z", "Adventure", 1199, 2010, 2021),
        ("Tracer 9", "GT", "Sport Touring", 889, 2021, CURRENT_YEAR),
        ("XSR900", "", "Retro", 889, 2016, CURRENT_YEAR),
        ("XSR700", "", "Retro", 689, 2018, CURRENT_YEAR),
        ("Bolt", "XV950", "Cruiser", 942, 2014, CURRENT_YEAR),
        ("WR450F", "", "Enduro", 449, 2003, CURRENT_YEAR),
        ("YZ450F", "", "Motocross", 449, 2003, CURRENT_YEAR),
        ("TMAX", "", "Scooter", 562, 2001, CURRENT_YEAR),
    ],
    "Kawasaki": [
        ("Ninja ZX-10R", "", "Sport", 998, 2004, CURRENT_YEAR),
        ("Ninja ZX-6R", "", "Sport", 636, 2003, CURRENT_YEAR),
        ("Ninja H2", "", "Hypersport", 998, 2015, CURRENT_YEAR),
        ("Ninja 1000SX", "", "Sport Touring", 1043, 2020, CURRENT_YEAR),
        ("Ninja 650", "", "Sport", 649, 2017, CURRENT_YEAR),
        ("Ninja 400", "", "Sport", 399, 2018, CURRENT_YEAR),
        ("Z900", "", "Naked", 948, 2017, CURRENT_YEAR),
        ("Z650", "", "Naked", 649, 2017, CURRENT_YEAR),
        ("Z H2", "", "Naked", 998, 2020, CURRENT_YEAR),
        ("Versys 1000", "", "Adventure", 1043, 2012, CURRENT_YEAR),
        ("Versys 650", "", "Adventure", 649, 2010, CURRENT_YEAR),
        ("KLR650", "", "Dual Sport", 652, 1987, CURRENT_YEAR),
        ("Vulcan S", "", "Cruiser", 649, 2015, CURRENT_YEAR),
        ("W800", "", "Retro", 773, 2011, CURRENT_YEAR),
        ("KX450", "", "Motocross", 449, 2006, CURRENT_YEAR),
    ],
    "Suzuki": [
        ("GSX-R1000", "", "Sport", 999, 2001, CURRENT_YEAR),
        ("GSX-R750", "", "Sport", 749, 2000, CURRENT_YEAR),
        ("GSX-R600", "", "Sport", 599, 2001, CURRENT_YEAR),
        ("GSX-S1000", "", "Naked", 999, 2015, CURRENT_YEAR),
        ("GSX-8S", "", "Naked", 776, 2023, CURRENT_YEAR),
        ("SV650", "", "Naked", 645, 1999, CURRENT_YEAR),
        ("Hayabusa", "GSX1300R", "Hypersport", 1340, 1999, CURRENT_YEAR),
        ("V-Strom 1050", "", "Adventure", 1037, 2020, CURRENT_YEAR),
        ("V-Strom 650", "", "Adventure", 645, 2004, CURRENT_YEAR),
        ("DR-Z400", "S", "Dual Sport", 398, 2000, CURRENT_YEAR),
        ("Boulevard M109R", "", "Cruiser", 1783, 2006, CURRENT_YEAR),
        ("RM-Z450", "", "Motocross", 449, 2005, CURRENT_YEAR),
    ],
    "Ducati": [
        ("Panigale V4", "", "Sport", 1103, 2018, CURRENT_YEAR),
        ("Panigale V4", "S", "Sport", 1103, 2018, CURRENT_YEAR),
        ("Panigale V2", "", "Sport", 955, 2020, CURRENT_YEAR),
        ("1299 Panigale", "", "Sport", 1285, 2015, 2019),
        ("Monster", "", "Naked", 937, 2021, CURRENT_YEAR),
        ("Monster 821", "", "Naked", 821, 2014, 2020),
        ("Streetfighter V4", "", "Naked", 1103, 2020, CURRENT_YEAR),
        ("Multistrada V4", "", "Adventure", 1158, 2021, CURRENT_YEAR),
        ("Multistrada 1260", "", "Adventure", 1262, 2018, 2020),
        ("Diavel V4", "", "Cruiser", 1158, 2023, CURRENT_YEAR),
        ("Scrambler", "Icon", "Retro", 803, 2015, CURRENT_YEAR),
        ("Hypermotard 950", "", "Supermoto", 937, 2019, CURRENT_YEAR),
        ("DesertX", "", "Adventure", 937, 2022, CURRENT_YEAR),
    ],
    "BMW": [
        ("S 1000 RR", "", "Sport", 999, 2009, CURRENT_YEAR),
        ("S 1000 R", "", "Naked", 999, 2014, CURRENT_YEAR),
        ("S 1000 XR", "", "Sport Touring", 999, 2015, CURRENT_YEAR),
        ("R 1250 GS", "", "Adventure", 1254, 2019, CURRENT_YEAR),
        ("R 1250 GS", "Adventure", "Adventure", 1254, 2019, CURRENT_YEAR),
        ("R 1200 GS", "", "Adventure", 1170, 2013, 2018),
        ("F 900 R", "", "Naked", 895, 2020, CURRENT_YEAR),
        ("F 850 GS", "", "Adventure", 853, 2018, CURRENT_YEAR),
        ("F 750 GS", "", "Adventure", 853, 2018, CURRENT_YEAR),
        ("R nineT", "", "Retro", 1170, 2014, CURRENT_YEAR),
        ("R 1250 RT", "", "Touring", 1254, 2019, CURRENT_YEAR),
        ("G 310 GS", "", "Adventure", 313, 2017, CURRENT_YEAR),
        ("G 310 R", "", "Naked", 313, 2016, CURRENT_YEAR),
    ],
    "KTM": [
        ("1290 Super Duke R", "", "Naked", 1301, 2014, CURRENT_YEAR),
        ("890 Duke", "R", "Naked", 889, 2020, CURRENT_YEAR),
        ("790 Duke", "", "Naked", 799, 2018, CURRENT_YEAR),
        ("390 Duke", "", "Naked", 373, 2013, CURRENT_YEAR),
        ("250 Duke", "", "Naked", 249, 2015, CURRENT_YEAR),
        ("1290 Super Adventure", "S", "Adventure", 1301, 2015, CURRENT_YEAR),
        ("890 Adventure", "R", "Adventure", 889, 2021, CURRENT_YEAR),
        ("790 Adventure", "", "Adventure", 799, 2019, CURRENT_YEAR),
        ("390 Adventure", "", "Adventure", 373, 2020, CURRENT_YEAR),
        ("RC 390", "", "Sport", 373, 2014, CURRENT_YEAR),
        ("450 SX-F", "", "Motocross", 450, 2007, CURRENT_YEAR),
        ("500 EXC-F", "", "Enduro", 510, 2012, CURRENT_YEAR),
    ],
    "Harley-Davidson": [
        ("Street Glide", "", "Touring", 1868, 2017, CURRENT_YEAR),
        ("Road Glide", "", "Touring", 1868, 2017, CURRENT_YEAR),
        ("Road King", "", "Touring", 1746, 2017, CURRENT_YEAR),
        ("Fat Boy", "", "Cruiser", 1868, 2018, CURRENT_YEAR),
        ("Heritage Classic", "", "Cruiser", 1746, 2018, CURRENT_YEAR),
        ("Iron 883", "Sportster", "Cruiser", 883, 2009, 2022),
        ("Forty-Eight", "Sportster", "Cruiser", 1202, 2010, 2022),
        ("Sportster S", "", "Cruiser", 1252, 2021, CURRENT_YEAR),
        ("Nightster", "", "Cruiser", 975, 2022, CURRENT_YEAR),
        ("Pan America", "1250", "Adventure", 1252, 2021, CURRENT_YEAR),
        ("Fat Bob", "", "Cruiser", 1868, 2018, CURRENT_YEAR),
        ("LiveWire", "", "Electric", 0, 2019, 2021),
    ],
    "Triumph": [
        ("Street Triple", "RS", "Naked", 765, 2017, CURRENT_YEAR),
        ("Speed Triple", "1200 RS", "Naked", 1160, 2021, CURRENT_YEAR),
        ("Trident 660", "", "Naked", 660, 2021, CURRENT_YEAR),
        ("Daytona 675", "", "Sport", 675, 2006, 2017),
        ("Daytona Moto2 765", "", "Sport", 765, 2020, CURRENT_YEAR),
        ("Tiger 900", "Rally Pro", "Adventure", 888, 2020, CURRENT_YEAR),
        ("Tiger 1200", "GT", "Adventure", 1160, 2022, CURRENT_YEAR),
        ("Bonneville T120", "", "Retro", 1200, 2016, CURRENT_YEAR),
        ("Bonneville T100", "", "Retro", 900, 2017, CURRENT_YEAR),
        ("Scrambler 1200", "XE", "Scrambler", 1200, 2019, CURRENT_YEAR),
        ("Speed Twin", "1200", "Retro", 1200, 2019, CURRENT_YEAR),
        ("Rocket 3", "R", "Cruiser", 2458, 2020, CURRENT_YEAR),
    ],
    "Aprilia": [
        ("RSV4", "Factory", "Sport", 1099, 2009, CURRENT_YEAR),
        ("RS 660", "", "Sport", 659, 2020, CURRENT_YEAR),
        ("RS 125", "", "Sport", 125, 2006, CURRENT_YEAR),
        ("Tuono V4", "Factory", "Naked", 1077, 2011, CURRENT_YEAR),
        ("Tuono 660", "", "Naked", 659, 2021, CURRENT_YEAR),
        ("Tuareg 660", "", "Adventure", 659, 2022, CURRENT_YEAR),
    ],
    "Royal Enfield": [
        ("Classic 350", "", "Cruiser", 349, 2021, CURRENT_YEAR),
        ("Meteor 350", "", "Cruiser", 349, 2020, CURRENT_YEAR),
        ("Hunter 350", "", "Roadster", 349, 2022, CURRENT_YEAR),
        ("Continental GT 650", "", "Cafe Racer", 648, 2018, CURRENT_YEAR),
        ("Interceptor 650", "INT650", "Retro", 648, 2018, CURRENT_YEAR),
        ("Himalayan", "", "Adventure", 411, 2016, 2023),
        ("Himalayan 450", "", "Adventure", 452, 2024, CURRENT_YEAR),
    ],
    "Husqvarna": [
        ("Svartpilen 401", "", "Naked", 373, 2018, CURRENT_YEAR),
        ("Vitpilen 401", "", "Naked", 373, 2018, CURRENT_YEAR),
        ("Norden 901", "", "Adventure", 889, 2022, CURRENT_YEAR),
        ("FE 350", "", "Enduro", 350, 2014, CURRENT_YEAR),
        ("FC 450", "", "Motocross", 450, 2014, CURRENT_YEAR),
    ],
    "Indian": [
        ("Scout", "", "Cruiser", 1133, 2015, CURRENT_YEAR),
        ("Scout Bobber", "", "Cruiser", 1133, 2018, CURRENT_YEAR),
        ("Chief", "Dark Horse", "Cruiser", 1890, 2022, CURRENT_YEAR),
        ("Chieftain", "", "Touring", 1890, 2014, CURRENT_YEAR),
        ("FTR 1200", "", "Naked", 1203, 2019, CURRENT_YEAR),
        ("Roadmaster", "", "Touring", 1890, 2015, CURRENT_YEAR),
    ],
    "Moto Guzzi": [
        ("V7", "Stone", "Retro", 853, 2021, CURRENT_YEAR),
        ("V85 TT", "", "Adventure", 853, 2019, CURRENT_YEAR),
        ("V100 Mandello", "", "Sport Touring", 1042, 2022, CURRENT_YEAR),
    ],
    "MV Agusta": [
        ("F3", "800", "Sport", 798, 2013, CURRENT_YEAR),
        ("Brutale", "800", "Naked", 798, 2013, CURRENT_YEAR),
        ("Dragster", "800", "Naked", 798, 2014, CURRENT_YEAR),
        ("Turismo Veloce", "800", "Sport Touring", 798, 2015, CURRENT_YEAR),
    ],
    "CFMoto": [
        ("450SS", "", "Sport", 449, 2023, CURRENT_YEAR),
        ("700CL-X", "", "Retro", 693, 2021, CURRENT_YEAR),
        ("800MT", "", "Adventure", 799, 2021, CURRENT_YEAR),
        ("450NK", "", "Naked", 449, 2024, CURRENT_YEAR),
    ],
    "Zero": [
        ("SR/F", "", "Electric", 0, 2019, CURRENT_YEAR),
        ("SR/S", "", "Electric", 0, 2020, CURRENT_YEAR),
        ("DSR/X", "", "Electric", 0, 2022, CURRENT_YEAR),
        ("FX", "", "Electric", 0, 2013, CURRENT_YEAR),
    ],
    # Niche track-only manufacturers.
    "Kraemer": [
        # US-built, KTM 690 LC4 single-cylinder track bikes.
        ("GP2 690", "", "Track", 693, 2018, CURRENT_YEAR),
        ("GP2 690", "R", "Track", 693, 2020, CURRENT_YEAR),
        ("APR690", "", "Track", 693, 2021, CURRENT_YEAR),
        ("APR690", "RR", "Track", 693, 2022, CURRENT_YEAR),
        # KTM 890 parallel-twin track bike.
        ("890RR", "", "Track", 889, 2022, CURRENT_YEAR),
    ],
    "Ohvale": [
        # Italian mini-GP / minimoto track bikes.
        ("GP-0", "110", "Mini GP", 110, 2016, CURRENT_YEAR),
        ("GP-0", "160", "Mini GP", 160, 2016, CURRENT_YEAR),
        ("GP-0", "190 Daytona", "Mini GP", 187, 2018, CURRENT_YEAR),
        ("GP-0", "212 Daytona", "Mini GP", 212, 2019, CURRENT_YEAR),
        ("GP-2", "190 Daytona", "Mini GP", 187, 2020, CURRENT_YEAR),
        ("GP-2", "212 Daytona", "Mini GP", 212, 2020, CURRENT_YEAR),
    ],
}

FIELDNAMES = ["make", "model", "badge", "category", "displacement_cc", "year"]


def build_rows() -> list[dict]:
    rows: list[dict] = []
    for make, entries in SPEC.items():
        for model, badge, category, cc, y_start, y_end in entries:
            for year in range(y_start, y_end + 1):
                rows.append(
                    {
                        "make": make,
                        "model": model,
                        "badge": badge,
                        "category": category,
                        "displacement_cc": cc,
                        "year": year,
                    }
                )
    return rows


def main() -> None:
    out_path = os.path.join(os.path.dirname(__file__), "bikes.csv")
    rows = build_rows()
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    makes = len(SPEC)
    print(f"Wrote {len(rows)} rows across {makes} makes to {out_path}")


if __name__ == "__main__":
    main()
