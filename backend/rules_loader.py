"""
Loads and validates the machine-readable FSSAI rules file.

Kept deliberately tiny and cache-backed so the rules file is parsed once per
process. Used by both the claim mapper and the rule engine.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict, Optional

from config import RULES_PATH


@lru_cache(maxsize=1)
def load_rules() -> Dict[str, Any]:
    """Read fssai_rules.json once and cache it in memory."""
    if not RULES_PATH.exists():
        raise FileNotFoundError(f"Rules file not found: {RULES_PATH}")
    with RULES_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def get_claims() -> list:
    """Return the list of claim definitions."""
    return load_rules().get("claims", [])


def get_claim(canonical: str) -> Optional[Dict[str, Any]]:
    """Return a single claim definition by its canonical name."""
    for claim in get_claims():
        if claim.get("canonical") == canonical:
            return claim
    return None


def get_prohibited_terms() -> Dict[str, Any]:
    """Return the prohibited-terms block."""
    return load_rules().get("prohibited_terms", {})


def get_meta() -> Dict[str, Any]:
    """Return the meta block (version, RDA reference, etc.)."""
    return load_rules().get("meta", {})
