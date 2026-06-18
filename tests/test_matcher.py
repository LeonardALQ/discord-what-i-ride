"""
Checks for the matcher against the real merged dataset.
Run: python -m tests.test_matcher
"""
from src.dataset import load_records
from src.matcher import BikeMatcher

records = load_records()
matcher = BikeMatcher(records)


def top(make="", model="", badge="", year=None):
    res = matcher.match(make=make, model=model, badge=badge, year=year, limit=3)
    assert res, "no results returned"
    return res[0]


def test_make_resolves_and_scopes():
    r = top("Honda", "CBR1000RR", year=2015)
    assert r.record.make == "Honda", r.record.display_name
    assert "CBR1000RR" in r.record.model.upper(), r.record.display_name
    assert r.score >= 80, r.score


def test_typos():
    r = top("Hona", "CBR 1000 RR")
    assert r.record.make == "Honda", r.record.display_name
    assert "1000" in r.record.model


def test_partial_model():
    r = top("Yamaha", "MT07")
    assert r.record.make == "Yamaha", r.record.display_name
    assert "07" in r.record.model, r.record.display_name


def test_cbr300r_now_found():
    # The original bug report: CBR300R must match itself, not CB300R.
    r = top("Honda", "CBR300R")
    assert r.record.make == "Honda"
    assert "CBR300R" in r.record.model.upper().replace(" ", ""), r.record.display_name


def test_cross_make_not_leaking():
    r = top("Ducati", "Panigale V4", "S", 2022)
    assert r.record.make == "Ducati", r.record.display_name
    assert "PANIGALE" in r.record.model.upper(), r.record.display_name


def test_niche_supplement_kraemer():
    r = top("Kraemer", "890RR")
    assert r.record.make == "Kraemer", r.record.display_name
    assert "890" in r.record.model


def test_niche_supplement_stark():
    r = top("Stark", "Varg")
    assert r.record.make == "Stark Future", r.record.display_name
    assert "Varg" in r.record.model


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
