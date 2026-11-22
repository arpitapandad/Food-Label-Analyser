"""
Maps free-text front-of-pack claims to a single canonical claim key.

Real labels write the same claim many ways ("No Added Sugar", "0% Added Sugar",
"Zero Added Sugar"). Normalising first is what makes the downstream rule lookup
deterministic.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from backend.rules_loader import get_claims


def _build_alias_map() -> List[Tuple[str, str]]:
    """
    Build a list of (alias, canonical) pairs sorted by alias length DESC.

    Longest-first ensures "source of protein" wins over a bare "protein".
    """
    pairs: List[Tuple[str, str]] = []
    for claim in get_claims():
        canonical = claim.get("canonical", "")
        for alias in claim.get("aliases", []):
            pairs.append((alias.lower().strip(), canonical))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def map_claim(claim_text: Optional[str]) -> Optional[str]:
    """
    Return the canonical claim key, or None if the claim is not supported.

    Matching is substring-based on a normalised, lower-cased string.
    """
    if not claim_text:
        return None
    haystack = claim_text.lower().strip()
    for alias, canonical in _build_alias_map():
        if alias and alias in haystack:
            return canonical
    return None


def get_display_name(canonical: Optional[str]) -> Optional[str]:
    """Human-readable name for a canonical claim (for UI / API responses)."""
    for claim in get_claims():
        if claim.get("canonical") == canonical:
            return claim.get("display_name", canonical)
    return None
