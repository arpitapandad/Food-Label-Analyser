"""Tests for claim normalisation (alias -> canonical)."""
from backend.claim_mapper import map_claim


def test_no_added_sugar_variants():
    for text in ["No Added Sugar", "0% Added Sugar", "Zero Added Sugar", "Without Added Sugar"]:
        assert map_claim(text) == "no_added_sugar"


def test_high_protein_variants():
    assert map_claim("High in Protein") == "high_protein"
    assert map_claim("Rich in Protein") == "high_protein"


def test_source_of_protein_beats_bare_protein():
    # Longest-alias-first must pick the more specific rule.
    assert map_claim("Source of Protein") == "source_of_protein"


def test_unsupported_claim_returns_none():
    assert map_claim("Grandma's Secret Recipe") is None
