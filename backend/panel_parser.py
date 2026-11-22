"""
Turns raw OCR text (or pasted label text) into structured nutrition values.

This is the highest-risk component of the pipeline, so it is deliberately
lenient: it extracts whatever it can and reports what is missing, rather than
guessing. The UI should always offer a manual-entry fallback.
"""
from __future__ import annotations

import re
from typing import Dict, Optional

from backend.utils import normalize_whitespace

# Only extract nutrients that the dataset / rules care about.
_TARGET_NUTRIENTS = (
    "energy_kcal",
    "protein_g",
    "carbohydrates_g",
    "total_sugars_g",
    "added_sugars_g",
    "dietary_fibre_g",
    "total_fat_g",
    "saturated_fat_g",
    "sodium_mg",
)


def _num(value: str) -> Optional[float]:
    """Convert a captured numeric string to float, tolerating '1,2' style."""
    try:
        return float(value.replace(",", "."))
    except (TypeError, ValueError):
        return None


# OCR engines routinely confuse digits with lookalike letters: "0" is read as
# "O", "1" as "l"/"I". This matters here because the flagship "No Added Sugar"
# check hinges on an added_sugars_g value of 0 - a misread "O" would otherwise
# drop the whole verdict to INSUFFICIENT_DATA.
#
# We only rewrite ISOLATED single-character tokens (plus a misread digit glued
# to its unit), so ordinary words and units ("Sodium", "ml", "g", "kcal") are
# never touched.
_OCR_DIGIT_LOOKALIKES = {
    "O": "0",
    "o": "0",
    "l": "1",
    "L": "1",
    "I": "1",
    "S": "5",
    "B": "8",
    "Z": "2",
    "z": "2",
}

# OCR also glues a misread value to its unit, so "0 g" arrives as the single
# token "og" (observed on a real RapidOCR run). Splitting it recovers the
# number. Only a lookalike letter is accepted, so genuine tokens such as "mg"
# (milligrams) and "Mg" (magnesium) are left alone.
_MERGED_VALUE_UNIT = re.compile(r"(?<![\w.])([OolLISBZz])(g|mg|kg|ml|kcal)\b")


def _repair_ocr_digits(text: str) -> str:
    """Rewrite letters that OCR substituted for digits."""
    repaired = re.sub(
        r"(?<![\w.,])([A-Za-z])(?![\w])",
        lambda match: _OCR_DIGIT_LOOKALIKES.get(match.group(1), match.group(1)),
        text,
    )
    return _MERGED_VALUE_UNIT.sub(
        lambda match: (
            f"{_OCR_DIGIT_LOOKALIKES.get(match.group(1), match.group(1))} "
            f"{match.group(2)}"
        ),
        repaired,
    )


def _search(patterns, text: str) -> Optional[float]:
    """Return the first numeric match across a list of regex patterns."""
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = _num(match.group(1))
            if value is not None:
                return value
    return None


# Label -> regex patterns. Kept lenient: the number may sit right after the
# label, and the unit may appear BEFORE the value ("Protein (g) 11.5" - the
# common Indian FSSAI layout), AFTER it ("Protein 11.5 g"), or be dropped by
# OCR entirely.
#
# The trailing unit is therefore NOT required. Requiring "g" after the digits
# used to discard every row whose unit was printed inside the label, so only
# protein (the one nutrient with a unit-less fallback) survived - that was the
# cause of "only protein was extracted". The label anchor plus the short
# [^0-9] window is what keeps a row's number with its own nutrient.
_PATTERNS: Dict[str, list] = {
    "energy_kcal": [
        r"energy[^0-9]{0,25}([\d.,]+)\s*kcal\b",           # "Energy 390 kcal"
        r"energy\s*\(?\s*kcal\s*\)?[^0-9]{0,25}([\d.,]+)",  # "Energy (kcal) 390"
        # No-unit fallback. The tempered gap refuses to cross a "kJ" sitting
        # BEFORE the value ("Energy (kJ) 1630"), and (?!\s*kj) refuses one
        # AFTER it ("Energy 1630 kJ"); (?![0-9.,]) then stops the greedy digits
        # backtracking to a partial number once those guards reject the full one.
        r"energy(?:(?!kj)[^0-9]){0,25}([\d.,]+)(?![0-9.,])(?!\s*kj)",
        r"([\d.,]+)\s*kcal\b",                              # "390 kcal" (standalone)
    ],
    "protein_g": [r"protein[^0-9]{0,25}([\d.,]+)"],
    "carbohydrates_g": [r"carbohydrate[s]?[^0-9]{0,25}([\d.,]+)"],
    "total_sugars_g": [
        r"total\s*sugar[s]?[^0-9]{0,25}([\d.,]+)",
        r"of\s*which\s*sugar[s]?[^0-9]{0,25}([\d.,]+)",
        # The generic fallback must not match "Added Sugars", or both fields
        # would report the same number. The lookbehind is fixed-width, which
        # Python's re requires.
        r"(?<!added\s)sugar[s]?[^0-9]{0,25}([\d.,]+)",
    ],
    "added_sugars_g": [r"added\s*sugar[s]?[^0-9]{0,25}([\d.,]+)"],
    "dietary_fibre_g": [r"(?:dietary\s*)?fib(?:re|er)[^0-9]{0,25}([\d.,]+)"],
    "total_fat_g": [
        r"total\s*fat[^0-9]{0,25}([\d.,]+)",
        # The generic fallback must not swallow a sub-row. Without the
        # lookbehinds, "of which Saturated Fat 1.1 g", "Polyunsaturated Fat"
        # and "Trans Fat 0 g" would all populate total_fat_g. Reporting
        # nothing is better than reporting a different fat. Both lookbehinds
        # are fixed-width, which Python's re requires.
        r"(?<!saturated\s)(?<!trans\s)fat[^0-9]{0,25}([\d.,]+)",
    ],
    "saturated_fat_g": [r"saturat[a-z]*\s*fat[^0-9]{0,25}([\d.,]+)"],
    "sodium_mg": [r"sodium[^0-9]{0,25}([\d.,]+)", r"salt[^0-9]{0,25}([\d.,]+)"],
}


def _parse_text(text: str) -> Dict[str, float]:
    """Run every nutrient pattern over one chunk of text."""
    parsed: Dict[str, float] = {}
    for nutrient in _TARGET_NUTRIENTS:
        value = _search(_PATTERNS.get(nutrient, []), text)
        if value is not None:
            parsed[nutrient] = value
    return parsed


# A label and its number can still land on separate lines when OCR detects the
# value column as its own box ("Dietary Fibre" / "10.2 g"). A label-only line
# may therefore borrow the line below it - but only when that line is nothing
# but a value, so it can never reach a neighbouring nutrient's number.
_BARE_VALUE = re.compile(r"^[\d.,]+\s*(?:g|mg|kg|ml|kcal|kj)?$", flags=re.IGNORECASE)


def _looks_like_bare_value(line: str) -> bool:
    """True when a line holds only a number and an optional unit."""
    return bool(_BARE_VALUE.match(line.strip()))


def parse_nutrition_panel(raw_text: str) -> Dict[str, float]:
    """
    Extract nutrient -> value pairs from OCR text.

    Returns a dict containing ONLY the values that were found.
    """
    repaired = _repair_ocr_digits(raw_text or "")
    lines = [normalize_whitespace(line) for line in repaired.splitlines()]
    lines = [line for line in lines if line]

    # A nutrition table is one nutrient per row, so rows are parsed separately:
    # that stops a label from picking up a neighbour's number. Joining the whole
    # panel into one blob was actively harmful - when OCR merged "0 g" into "og"
    # the "Added Sugars" row had no number of its own and the pattern reached
    # forward into the NEXT row's "10.2 g", reporting a wrong value where none
    # was read. The only cross-line step kept is the guarded one below: a
    # label-only line may borrow an immediately following bare value.
    parsed: Dict[str, float] = {}
    for index, line in enumerate(lines):
        found = _parse_text(line)
        if not found:
            following = lines[index + 1] if index + 1 < len(lines) else ""
            if _looks_like_bare_value(following):
                found = _parse_text(f"{line} {following}")
        for nutrient, value in found.items():
            parsed.setdefault(nutrient, value)

    return parsed


def detect_serving_basis(raw_text: str) -> str:
    """
    Detect whether the panel is declared per 100 g/ml or per serving.

    Returns one of: "per_100", "per_serving", "unknown".
    """
    text = (raw_text or "").lower()
    if re.search(r"per\s*100\s*(?:g|ml|gm)", text):
        return "per_100"
    if re.search(r"per\s*(?:serving|serve|pack|piece|bottle|cup|sachet|\d+\s*(?:g|ml))", text):
        return "per_serving"
    return "unknown"


def extract_ingredients(raw_text: str) -> str:
    """
    Pull the ingredients list out of the label text.

    Everything after the word "Ingredients" (until a common stop word such as
    "Nutrition"/"Allergen") is treated as the ingredient string.
    """
    text = normalize_whitespace(raw_text)
    match = re.search(r"ingredients?\s*[:\-]?\s*(.+)", text, flags=re.IGNORECASE)
    if not match:
        return ""
    tail = match.group(1)
    stop = re.search(
        r"(nutrition|allergen|storage|best before|contains permitted|net (?:wt|weight))",
        tail,
        flags=re.IGNORECASE,
    )
    if stop:
        tail = tail[: stop.start()]
    return tail.strip(" .;-")
