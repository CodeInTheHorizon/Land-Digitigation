"""Conservative identity matching for extracted landowner names."""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

_ABBREVIATIONS = {"kr": "kumar", "k": "kumar", "sh": "shri", "smt": "smt"}

def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    tokens = [_ABBREVIATIONS.get(t, t) for t in value.split()]
    return " ".join(tokens)

@dataclass(frozen=True)
class Match:
    candidate: str
    score: float
    classification: str

def compare_names(value: str, candidates: list[str], threshold: float = 0.78) -> list[Match]:
    """Return possible matches; callers must decide whether to merge identities."""
    left = normalize_name(value)
    result = []
    for candidate in candidates:
        right = normalize_name(candidate)
        score = SequenceMatcher(None, left, right).ratio()
        classification = "exact" if left == right else "possible_match" if score >= threshold else "different"
        if classification != "different":
            result.append(Match(candidate, round(score, 4), classification))
    return sorted(result, key=lambda item: item.score, reverse=True)

__all__ = ["Match", "normalize_name", "compare_names"]
