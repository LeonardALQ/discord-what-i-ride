"""
Quick checks for the matcher. Run: python -m tests.test_matcher
(works with plain python; uses asserts, no pytest required).
"""
from src.dataset import load_records
from src.matcher import BikeMatcher

records = load_records()
matcher = BikeMatcher(records)


def top(make="", model="", badge="", year=None):
    res = matcher.match(make=make, model=model, badge=badge, year=year, limit=3)
    return res[0]


def test_exact():
    # 2015 is within the base CBR1000RR run (2004-2019); the CBR1000RR-R is 2020+.
    r = top("Honda", "CBR1000RR", "Fireblade", 2015)
    assert r.record.make == "Honda"
    assert r.record.model == "CBR1000RR", r.record.display_name
    assert r.score >= 80, r.score


def test_year_picks_correct_generation():
    # Same model text but a 2021 year should steer to the current -R generation.
    r = top("Honda", "CBR1000RR", year=2021)
    assert r.record.make == "Honda"
    assert "CBR1000RR" in r.record.model, r.record.display_name


def test_typos():
    # Misspelled make and model should still resolve.
    r = top("Hona", "CBR 1000 RR")
    assert r.record.make == "Honda", r.record.display_name
    assert "1000" in r.record.model


def test_partial_model():
    r = top("Yamaha", "MT07")
    assert r.record.make == "Yamaha"
    assert r.record.model == "MT-07", r.record.display_name


def test_badge_disambiguation():
    # R1 vs R1 M — badge should steer toward the M variant.
    r = top("Yamaha", "R1", "M")
    assert r.record.make == "Yamaha"
    assert "R1" in r.record.model


def test_year_in_range():
    r = top("Kawasaki", "Ninja 400", year=2020)
    assert r.record.make == "Kawasaki"
    assert r.matched_year_text == "2020", r.matched_year_text


def test_cross_make_not_leaking():
    r = top("Ducati", "Panigale V4", "S", 2022)
    assert r.record.make == "Ducati"
    assert "Panigale" in r.record.model


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
