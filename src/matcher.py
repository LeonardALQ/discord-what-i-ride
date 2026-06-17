"""
matcher.py
==========
Fuzzy-matches a user's described bike (make / model / badge / year) against the
loaded BikeRecord set and returns the closest matches with a confidence score.

Scoring blends:
  - make similarity      (helps disambiguate brand)
  - model similarity      (primary signal)
  - full-name similarity  (make + model + badge, token-based)
  - badge similarity      (only when the user supplies a badge)
  - year proximity        (only when the user supplies a year)

Uses rapidfuzz for fast, typo-tolerant string similarity.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from .dataset import BikeRecord, all_makes


def _norm(text: str) -> str:
    """Lowercase, strip punctuation that varies between sources, collapse spaces.

    Also inserts spaces at letter<->digit boundaries so inputs like "MT07" and
    "MT-07" both normalize to "mt 07", and "CBR1000RR" to "cbr 1000 rr".
    """
    text = (text or "").lower().strip()
    text = text.replace("-", " ").replace("/", " ").replace("_", " ")
    text = re.sub(r"[^a-z0-9 ]", "", text)
    # Separate letter/digit runs: "mt07" -> "mt 07", "1000rr" -> "1000 rr".
    text = re.sub(r"(?<=[a-z])(?=[0-9])", " ", text)
    text = re.sub(r"(?<=[0-9])(?=[a-z])", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@dataclass
class MatchResult:
    record: BikeRecord
    score: float          # 0-100 overall confidence
    requested_year: int | None = None

    @property
    def matched_year_text(self) -> str:
        if self.requested_year and self.record.covers_year(self.requested_year):
            return str(self.requested_year)
        return self.record.year_label


class BikeMatcher:
    # Relative weights; normalized at scoring time based on which fields exist.
    W_MAKE = 0.25
    W_MODEL = 0.40
    W_FULL = 0.25
    W_BADGE = 0.10
    YEAR_WINDOW = 6  # years of tolerance before the year bonus decays to ~0

    def __init__(self, records: list[BikeRecord]):
        self.records = records
        self._makes = all_makes(records)
        self._makes_norm = {_norm(m): m for m in self._makes}

    def resolve_make(self, raw_make: str) -> str | None:
        """Return the canonical make best matching the user's input, or None."""
        nm = _norm(raw_make)
        if not nm:
            return None
        if nm in self._makes_norm:
            return self._makes_norm[nm]
        choice = process.extractOne(
            nm, list(self._makes_norm.keys()), scorer=fuzz.WRatio
        )
        if choice and choice[1] >= 80:
            return self._makes_norm[choice[0]]
        return None

    def match(
        self,
        make: str = "",
        model: str = "",
        badge: str = "",
        year: int | None = None,
        limit: int = 3,
    ) -> list[MatchResult]:
        nm_make = _norm(make)
        nm_model = _norm(model)
        nm_badge = _norm(badge)
        nm_query_full = " ".join(p for p in (nm_make, nm_model, nm_badge) if p)

        canonical_make = self.resolve_make(make) if make else None

        # If we confidently resolved the make, restrict candidates to it for
        # precision; otherwise score across everything.
        if canonical_make:
            candidates = [r for r in self.records if r.make == canonical_make]
        else:
            candidates = self.records

        results: list[MatchResult] = []
        for rec in candidates:
            score = self._score(rec, nm_make, nm_model, nm_badge,
                                 nm_query_full, year)
            results.append(MatchResult(rec, score, year))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def _score(self, rec: BikeRecord, nm_make: str, nm_model: str,
               nm_badge: str, nm_query_full: str, year: int | None) -> float:
        rec_make = _norm(rec.make)
        rec_model = _norm(rec.model)
        rec_badge = _norm(rec.badge)
        rec_full = _norm(rec.search_blob)

        components: list[tuple[float, float]] = []  # (weight, score)

        if nm_make:
            components.append((self.W_MAKE, fuzz.WRatio(nm_make, rec_make)))
        if nm_model:
            # token_set_ratio handles word-order and partial model names well.
            model_score = max(
                fuzz.token_set_ratio(nm_model, rec_model),
                fuzz.partial_ratio(nm_model, rec_model),
            )
            components.append((self.W_MODEL, model_score))
        if nm_query_full:
            components.append((self.W_FULL,
                               fuzz.token_set_ratio(nm_query_full, rec_full)))
        if nm_badge:
            badge_score = fuzz.WRatio(nm_badge, rec_badge) if rec_badge else 0
            components.append((self.W_BADGE, badge_score))

        if not components:
            return 0.0

        total_weight = sum(w for w, _ in components)
        base = sum(w * s for w, s in components) / total_weight

        # Year proximity: small bonus/penalty, only when both sides have a year.
        if year and rec.year_max:
            if rec.covers_year(year):
                year_factor = 1.0
            else:
                nearest = min(abs(year - rec.year_min), abs(year - rec.year_max))
                year_factor = max(0.0, 1 - nearest / self.YEAR_WINDOW)
            # Scale base by up to +/-8% based on year fit.
            base = base * (0.92 + 0.08 * year_factor)

        return round(base, 2)


def match_bike(records: list[BikeRecord], make="", model="", badge="",
               year=None, limit=3) -> list[MatchResult]:
    """Convenience wrapper."""
    return BikeMatcher(records).match(make, model, badge, year, limit)
