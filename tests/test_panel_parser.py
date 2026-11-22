"""Tests for OCR-text -> structured values parsing."""
from backend.panel_parser import (
    detect_serving_basis,
    extract_ingredients,
    ingredient_text_fallback,
    parse_nutrition_panel,
)

SAMPLE = """
Nutrition Information (per 100 g)
Energy 390 kcal
Protein 11.5 g
Carbohydrate 71 g
Total Sugars 14.5 g
Added Sugars 0 g
Dietary Fibre 10.2 g
Total Fat 6.5 g
Saturated Fat 1.1 g
Sodium 35 mg
Ingredients: Multigrain (85.2%), Apple Juice Concentrate, Antioxidant (INS 306)
"""


def test_parses_all_key_nutrients():
    panel = parse_nutrition_panel(SAMPLE)
    assert panel["protein_g"] == 11.5
    assert panel["total_sugars_g"] == 14.5
    assert panel["dietary_fibre_g"] == 10.2
    assert panel["sodium_mg"] == 35.0


def test_detects_per_100_basis():
    assert detect_serving_basis(SAMPLE) == "per_100"


def test_detects_per_serving_basis():
    assert detect_serving_basis("Per Serving (30 g): Protein 4 g") == "per_serving"


def test_extracts_ingredients():
    ingredients = extract_ingredients(SAMPLE)
    assert "Apple Juice Concentrate" in ingredients
    assert "Nutrition" not in ingredients


# --- ingredient photo with the heading cropped off -------------------------
# A phone photo of the ingredient panel often misses the word "Ingredients".
# The list itself is still fully readable, so leaving the UI field empty made
# the scan look broken.

def test_ingredient_fallback_keeps_the_list_when_heading_is_missing():
    ocr = (
        "Nutrition Information (per 100 g)\n"
        "Energy 390 kcal\n"
        "Protein 11.5 g\n"
        "Multigrain (85.2%), Apple Juice Concentrate, Antioxidant (INS 306)"
    )
    assert (
        ingredient_text_fallback(ocr)
        == "Multigrain (85.2%), Apple Juice Concentrate, Antioxidant (INS 306)"
    )


def test_ingredient_fallback_is_empty_when_photo_is_only_the_panel():
    ocr = "Nutrition Information\nEnergy 390 kcal\nProtein 11.5 g\n35"
    assert ingredient_text_fallback(ocr) == ""


def test_ingredient_fallback_does_not_drop_ingredients_that_look_like_labels():
    # "Sodium Caseinate" is an ingredient, not the Sodium nutrition row.
    ocr = "Sodium Caseinate (milk), Salt, Permitted Flavours"
    assert ingredient_text_fallback(ocr) == ocr


# --- OCR digit/letter confusion -------------------------------------------
# Real RapidOCR output for "Added Sugars 0 g" is "Added Sugars O g" (letter O).
# Without repair the flagship "No Added Sugar" case degrades to INSUFFICIENT_DATA.

def test_repairs_zero_read_as_letter_o():
    panel = parse_nutrition_panel("Added Sugars O g\nTotal Sugars 14.5 g")
    assert panel["added_sugars_g"] == 0.0


def test_repairs_one_read_as_letter_l():
    panel = parse_nutrition_panel("Saturated Fat l.1 g")
    assert panel["saturated_fat_g"] == 1.1


def test_digit_repair_does_not_break_units_or_words():
    # "g", "mg", "kcal" and real words must survive untouched.
    panel = parse_nutrition_panel("Protein 11.5 g\nSodium 35 mg\nEnergy 390 kcal")
    assert panel["protein_g"] == 11.5
    assert panel["sodium_mg"] == 35.0
    assert panel["energy_kcal"] == 390.0


def test_digit_repair_leaves_normal_words_alone():
    # "Iron" contains no isolated single letters, so it must not be mangled.
    panel = parse_nutrition_panel("Ingredients: Iron Rich Oats, Vitamin B")
    assert panel == {}


# --- per-line parsing ------------------------------------------------------
# The panel is one nutrient per row. Parsing line by line stops a label from
# picking up the number belonging to the neighbouring row.

def test_value_detected_on_its_own_line_is_still_found():
    panel = parse_nutrition_panel("Dietary Fibre\n10.2 g")
    assert panel["dietary_fibre_g"] == 10.2


def test_label_only_line_does_not_steal_the_next_rows_value():
    # The real cross-row failure: "Added Sugars" had no number of its own and
    # the pattern reached forward into Dietary Fibre's 10.2 g.
    panel = parse_nutrition_panel("Added Sugars\nDietary Fibre 10.2 g")
    assert "added_sugars_g" not in panel
    assert panel["dietary_fibre_g"] == 10.2


def test_label_only_line_does_not_reach_past_one_row():
    panel = parse_nutrition_panel("Added Sugars\nDietary Fibre\n10.2 g")
    assert "added_sugars_g" not in panel


def test_trans_fat_does_not_populate_total_fat():
    # Real RapidOCR emits "Trans Fat og"; without the lookbehind that row
    # satisfies the generic fat fallback and reports 0 g of total fat.
    panel = parse_nutrition_panel("Trans Fat og")
    assert panel.get("total_fat_g") is None
    assert panel == {}


def test_total_sugars_is_not_confused_with_added_sugars():
    panel = parse_nutrition_panel("Total Sugars 14.5 g\nAdded Sugars 0 g")
    assert panel["total_sugars_g"] == 14.5
    assert panel["added_sugars_g"] == 0.0


def test_added_sugars_alone_does_not_populate_total_sugars():
    # "Added Sugars" must not satisfy the generic sugars fallback.
    panel = parse_nutrition_panel("Added Sugars 0 g")
    assert panel["added_sugars_g"] == 0.0
    assert "total_sugars_g" not in panel


def test_of_which_sugars_variant_is_recognised():
    panel = parse_nutrition_panel("Carbohydrate 71 g\nof which Sugars 14.5 g")
    assert panel["total_sugars_g"] == 14.5


def test_full_ocr_style_panel_parses_every_row():
    """A realistic multi-row panel must yield all nine values."""
    panel = parse_nutrition_panel(
        "Nutrition Information (per 100 g)\n"
        "Energy 390 kcal\n"
        "Protein 11.5 g\n"
        "Carbohydrate 71 g\n"
        "of which Sugars 14.5 g\n"
        "Added Sugars 0 g\n"
        "Dietary Fibre 10.2 g\n"
        "Total Fat 6.5 g\n"
        "of which Saturated Fat 1.1 g\n"
        "Sodium 35 mg"
    )
    assert panel == {
        "energy_kcal": 390.0,
        "protein_g": 11.5,
        "carbohydrates_g": 71.0,
        "total_sugars_g": 14.5,
        "added_sugars_g": 0.0,
        "dietary_fibre_g": 10.2,
        "total_fat_g": 6.5,
        "saturated_fat_g": 1.1,
        "sodium_mg": 35.0,
    }


def test_two_read_as_letter_z_is_repaired():
    panel = parse_nutrition_panel("Saturated Fat Z g")
    assert panel["saturated_fat_g"] == 2.0


# --- unit printed BEFORE the value -----------------------------------------
# The common Indian FSSAI layout puts the unit inside the label, e.g.
# "Protein (g) 11.5". Requiring "g" AFTER the digits used to drop every such
# row, so only protein - the one nutrient with a unit-less fallback - survived.
# That regression is pinned here.

def test_unit_before_value_parses_every_nutrient():
    panel = parse_nutrition_panel(
        "Nutrition Information (Per 100 g)\n"
        "Energy (kcal) 390\n"
        "Protein (g) 11.5\n"
        "Carbohydrate (g) 71\n"
        "Total Sugars (g) 14.5\n"
        "Added Sugars (g) 0\n"
        "Dietary Fibre (g) 10.2\n"
        "Total Fat (g) 6.5\n"
        "Saturated Fat (g) 1.1\n"
        "Sodium (mg) 35"
    )
    assert panel == {
        "energy_kcal": 390.0,
        "protein_g": 11.5,
        "carbohydrates_g": 71.0,
        "total_sugars_g": 14.5,
        "added_sugars_g": 0.0,
        "dietary_fibre_g": 10.2,
        "total_fat_g": 6.5,
        "saturated_fat_g": 1.1,
        "sodium_mg": 35.0,
    }


def test_unitless_values_are_parsed():
    # OCR sometimes drops the unit entirely; the number must still be read.
    panel = parse_nutrition_panel("Protein 11.5\nSodium 35\nTotal Fat 6.5")
    assert panel["protein_g"] == 11.5
    assert panel["sodium_mg"] == 35.0
    assert panel["total_fat_g"] == 6.5


def test_energy_in_kilojoules_is_not_reported_as_kcal():
    # A kJ-only panel must not be read as kcal (a ~4x error). Reporting
    # nothing is better than reporting a wrong unit.
    panel = parse_nutrition_panel("Energy 1630 kJ\nProtein 11.5 g")
    assert "energy_kcal" not in panel
    assert panel["protein_g"] == 11.5


def test_kcal_is_preferred_when_both_units_are_shown():
    panel = parse_nutrition_panel("Energy (kJ) 1630\nEnergy (kcal) 390")
    assert panel["energy_kcal"] == 390.0
