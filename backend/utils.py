"""
Small shared helpers used across the backend.

Kept dependency-free on purpose (no pandas / no numpy) so it can be imported
anywhere without side effects.
"""
from __future__ import annotations

import re
from typing import Optional

# Category keywords that indicate a LIQUID product (thresholds differ).
_LIQUID_KEYWORDS = (
    "beverage", "drink", "tea", "coffee", "water", "juice", "lassi",
    "milk", "shake", "smoothie", "oil", "soda", "cola", "energy",
)


def infer_form(category: Optional[str], product_name: Optional[str] = None) -> str:
    """
    Best-effort inference of physical form ("solid" or "liquid").

    FSSAI thresholds differ for solids (per 100 g) and liquids (per 100 ml),
    so this matters for correctness. Falls back to "solid".
    """
    haystack = f"{category or ''} {product_name or ''}".lower()
    if any(kw in haystack for kw in _LIQUID_KEYWORDS):
        return "liquid"
    return "solid"


def normalize_whitespace(text: Optional[str]) -> str:
    """Collapse runs of whitespace into single spaces."""
    if not text:
        return ""
    return " ".join(text.split())


def contains_any(haystack: str, needles) -> list:
    """
    Return the needles found in haystack as WHOLE WORDS (case-insensitive).

    Whole-word matching is essential here: a naive substring check made
    "heal" match inside "healthy" and "cure" inside "secure", producing false
    prohibited-claim flags (e.g. "Heart Healthy Oats").

    A trailing optional "s" is allowed so that singular keywords still catch
    their plural forms on real labels ("cure" must match "Cures Diabetes",
    "prevent" must match "Prevents cancer"). Word boundaries then reject the
    overlaps that caused the bug.
    """
    low = (haystack or "").lower()
    found = []
    for needle in needles:
        pattern = r"\b" + re.escape(needle.lower()) + r"s?\b"
        if re.search(pattern, low):
            found.append(needle)
    return found
