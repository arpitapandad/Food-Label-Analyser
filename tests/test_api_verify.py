"""
Tests for the multipart /verify endpoint - specifically the TWO-IMAGE contract
the front-of-pack design requires (ingredient list + nutrition table).

The OCR engine is monkeypatched out: `extract_combined_text` is replaced with a
function that simply echoes the uploaded bytes, so these tests exercise the
routing logic (which image feeds which parser) without installing OCR.
"""
import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from backend import main, ocr_utils


def _upload(content: str, name: str) -> UploadFile:
    """Build an in-memory UploadFile containing `content`."""
    return UploadFile(file=BytesIO(content.encode("utf-8")), filename=name)


def _echo_ocr(path: str) -> str:
    """Stand-in for OCR: return exactly what was uploaded."""
    return Path(path).read_text(encoding="utf-8")


def _run(**overrides):
    """Call the endpoint directly with sane defaults."""
    params = {
        "claim": "No Added Sugar",
        "ingredients_file": None,
        "panel_file": None,
        "file": None,
        "form": "solid",
        "panel_json": None,
        "ingredients": None,
        "category": None,
        "use_llm": False,
    }
    params.update(overrides)
    return asyncio.run(main.verify_image(**params))


PANEL_PHOTO = (
    "Nutrition Information (per 100 g) Energy 390 kcal Protein 11.5 g "
    "Total Sugars 14.5 g Added Sugars 0 g"
)
INGREDIENT_PHOTO = "Ingredients: Multigrain, Apple Juice Concentrate, Antioxidant (INS 306)"


def test_two_scans_feed_the_right_parsers(monkeypatch):
    monkeypatch.setattr(main, "extract_combined_text", _echo_ocr)

    result = _run(
        panel_file=_upload(PANEL_PHOTO, "panel.jpg"),
        ingredients_file=_upload(INGREDIENT_PHOTO, "ingredients.jpg"),
    )

    # Nutrition numbers came from the panel photo.
    assert result.parsed_panel["protein_g"] == 11.5
    assert result.parsed_panel["added_sugars_g"] == 0.0
    # Ingredients came from the ingredient photo -> loophole detected.
    assert "apple juice concentrate" in result.decision.deceptive_flags
    assert result.decision.is_deceptive is True
    assert result.decision.is_technically_compliant is True


def test_ingredient_photo_wins_over_stray_ingredient_text_on_panel_photo(monkeypatch):
    """The panel photo must not hijack the ingredient string."""
    monkeypatch.setattr(main, "extract_combined_text", _echo_ocr)

    panel_with_stray_ingredients = PANEL_PHOTO + " Ingredients: Cane Sugar"
    result = _run(
        panel_file=_upload(panel_with_stray_ingredients, "panel.jpg"),
        ingredients_file=_upload(INGREDIENT_PHOTO, "ingredients.jpg"),
    )

    # Only the ingredient photo's list should be evaluated.
    assert "cane sugar" not in result.decision.deceptive_flags


def test_legacy_single_file_still_works(monkeypatch):
    monkeypatch.setattr(main, "extract_combined_text", _echo_ocr)

    result = _run(file=_upload(f"{PANEL_PHOTO} {INGREDIENT_PHOTO}", "label.jpg"))

    assert result.parsed_panel["protein_g"] == 11.5
    assert "apple juice concentrate" in result.decision.deceptive_flags


def test_manual_ingredients_override_ocr(monkeypatch):
    monkeypatch.setattr(main, "extract_combined_text", _echo_ocr)

    result = _run(
        ingredients_file=_upload(INGREDIENT_PHOTO, "ingredients.jpg"),
        panel_json='{"added_sugars_g": 0.0}',
        ingredients="Wholegrain Oats, Honey",
    )

    # Manual text wins over the OCR'd ingredient photo...
    assert "apple juice concentrate" not in result.decision.deceptive_flags
    # ...and "honey" (a soft deny-list entry) is what gets flagged instead.
    assert result.decision.deceptive_flags == ["honey"]
    assert result.decision.is_deceptive is True


def test_metadata_only_request_needs_no_images():
    """No images at all -> still a valid response (manual-entry path)."""
    result = _run(panel_json='{"added_sugars_g": 0.0}', ingredients="Oats, Honey")

    assert result.parsed_panel["added_sugars_g"] == 0.0
    assert result.decision.is_technically_compliant is True


def test_ingredient_photo_without_heading_still_fills_the_field(monkeypatch):
    """A cropped photo must not leave the ingredients box empty."""
    monkeypatch.setattr(main, "extract_combined_text", _echo_ocr)

    data = asyncio.run(
        main.ocr_extract(
            ingredients_file=_upload(
                "Nutrition Information\nEnergy 390 kcal\n"
                "Multigrain, Apple Juice Concentrate, Antioxidant (INS 306)",
                "ingredients.jpg",
            ),
            panel_file=None,
            file=None,
        )
    )

    assert "Apple Juice Concentrate" in data["ingredients"]
    assert "Energy" not in data["ingredients"]


def test_ocr_unavailable_becomes_501(monkeypatch):
    def _unavailable(path):
        raise ocr_utils.OCRUnavailableError("RapidOCR is not installed.")

    monkeypatch.setattr(main, "extract_combined_text", _unavailable)

    with pytest.raises(HTTPException) as exc:
        _run(panel_file=_upload(PANEL_PHOTO, "panel.jpg"))
    assert exc.value.status_code == 501


def test_bad_panel_json_is_rejected():
    with pytest.raises(HTTPException) as exc:
        _run(panel_json="{not valid json")
    assert exc.value.status_code == 400
