"""
Tests for the deterministic rule engine.

These encode the expected behaviour against the real curated dataset, so they
double as a correctness check for the rules themselves.
"""
from backend.dataset_utils import load_dataset
from backend.rule_engine import (
    STATUS_COMPLIANT,
    STATUS_INSUFFICIENT_DATA,
    STATUS_NON_COMPLIANT,
    STATUS_PROHIBITED,
    STATUS_UNKNOWN_CLAIM,
    evaluate_claim,
)


def _panel_from_row(product_id: int) -> dict:
    """Build a nutrition-panel dict from a dataset row (id == product_id)."""
    df = load_dataset()
    row = df[df["id"] == product_id].iloc[0]
    return {
        k: float(row[k])
        for k in [
            "energy_kcal", "protein_g", "carbohydrates_g", "total_sugars_g",
            "added_sugars_g", "dietary_fibre_g", "total_fat_g",
            "saturated_fat_g", "sodium_mg",
        ]
        if row[k] == row[k]  # skip NaN
    }


def _ingredients_from_row(product_id: int) -> str:
    df = load_dataset()
    return str(df[df["id"] == product_id].iloc[0]["ingredients"])


def test_high_protein_passes_for_protein_bar():
    # RiteBite Max Protein Bar: 20 g protein / 100 g -> meets >= 10 g threshold.
    panel = _panel_from_row(11)
    decision = evaluate_claim("High Protein", panel, form="solid")
    assert decision["status"] == STATUS_COMPLIANT


def test_sugar_free_fails_when_sugars_high():
    # RiteBite bar has 18 g sugars -> fails Sugar Free (<= 0.5 g).
    panel = _panel_from_row(11)
    decision = evaluate_claim("Sugar Free", panel, form="solid")
    assert decision["status"] == STATUS_NON_COMPLIANT


def test_no_added_sugar_compliant_but_deceptive():
    # Bagrry's: no hard added sugar, but apple juice concentrate -> deceptive.
    panel = _panel_from_row(1)
    ingredients = _ingredients_from_row(1)
    decision = evaluate_claim("No Added Sugar", panel, ingredients, form="solid")
    assert decision["status"] == STATUS_COMPLIANT
    assert decision["is_deceptive"] is True
    assert any("juice concentrate" in f for f in decision["deceptive_flags"])


def test_no_added_sugar_hard_fail_on_glucose_syrup():
    # Power Gummies: glucose syrup present -> non-compliant.
    panel = _panel_from_row(4)
    ingredients = _ingredients_from_row(4)
    decision = evaluate_claim("No Added Sugar", panel, ingredients, form="solid")
    assert decision["status"] == STATUS_NON_COMPLIANT


def test_hundred_percent_atta_fails_with_maida():
    # Harvest Gold 100% Atta contains Maida -> non-compliant.
    panel = _panel_from_row(6)
    ingredients = _ingredients_from_row(6)
    decision = evaluate_claim("100% Atta", panel, ingredients, form="solid")
    assert decision["status"] == STATUS_NON_COMPLIANT


def test_hundred_percent_whole_wheat_passes_without_maida():
    # Mission wraps: whole wheat only -> compliant.
    panel = _panel_from_row(10)
    ingredients = _ingredients_from_row(10)
    decision = evaluate_claim("100% Whole Wheat", panel, ingredients, form="solid")
    assert decision["status"] == STATUS_COMPLIANT


def test_prohibited_term_short_circuits():
    # "100% Pure" is flagged as prohibited regardless of nutrition.
    decision = evaluate_claim("100% Pure", {}, form="solid")
    assert decision["status"] == STATUS_PROHIBITED


def test_prohibited_matching_is_whole_word_only():
    # Regression: substring matching wrongly flagged these as prohibited,
    # because "heal" hides in "healthy" and "cure" hides in "secure".
    for claim in ["Heart Healthy Oats", "Secure Snack Bar", "Obscure Berry Drink"]:
        decision = evaluate_claim(claim, {}, form="solid")
        assert decision["status"] != STATUS_PROHIBITED, claim


def test_real_disease_claim_still_flagged():
    # The whole-word fix must NOT weaken genuine prohibited detection.
    for claim in ["Cures Diabetes", "Boosts Immunity", "Atta - cures all"]:
        decision = evaluate_claim(claim, {}, form="solid")
        assert decision["status"] == STATUS_PROHIBITED, claim


def test_dataset_heart_healthy_oats_not_prohibited():
    # Saffola Masala Oats (dataset row 24) claims "Heart Healthy". It must not
    # be flagged as prohibited - it is a health-halo claim, not a drug claim.
    panel = _panel_from_row(24)
    decision = evaluate_claim("Heart Healthy", panel, form="solid")
    assert decision["status"] != STATUS_PROHIBITED



def test_missing_nutrient_is_insufficient_data():
    decision = evaluate_claim("High Protein", panel={}, form="solid")
    assert decision["status"] == STATUS_INSUFFICIENT_DATA
    assert "protein_g" in decision["missing_fields"]


def test_unknown_claim_is_reported():
    decision = evaluate_claim("Grandma's Secret Recipe", {}, form="solid")
    assert decision["status"] == STATUS_UNKNOWN_CLAIM
