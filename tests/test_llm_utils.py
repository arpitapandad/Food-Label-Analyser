"""Tests for the grounded explanation layer.

No network and no API key: the OpenAI-compatible client is swapped for a fake,
so we can assert exactly what gets sent to the model.
"""
import json
import sys
import types

from backend import llm_utils

DECISION = {
    "status": "COMPLIANT",
    "rule_id": "R_NO_ADDED_SUGAR",
    "canonical_claim": "no_added_sugar",
    "measured_value": 0.0,
    "threshold": 0.0,
    "comparator": "lte",
    "unit": "g/100g",
    "reason": "Added sugars are 0 g per 100 g.",
    "is_technically_compliant": True,
    "is_deceptive": True,
    "deceptive_flags": ["apple juice concentrate"],
    "missing_fields": [],
    "warnings": [],
}


def _install_fake_openai(monkeypatch, *, content="Verdict: fine.", raises=None, captured=None):
    """Register a fake `openai` module for the duration of one test."""
    module = types.ModuleType("openai")

    class _Completions:
        def create(self, **kwargs):
            if captured is not None:
                captured.update(kwargs)
            message = types.SimpleNamespace(content=content)
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    class _Client:
        def __init__(self, **kwargs):
            if raises is not None:
                raise raises
            self.chat = types.SimpleNamespace(completions=_Completions())

    module.OpenAI = _Client
    monkeypatch.setitem(sys.modules, "openai", module)


# --- payload shaping -------------------------------------------------------

def test_confirmed_values_are_marked_authoritative():
    payload = llm_utils._build_payload(
        "No Added Sugar",
        DECISION,
        [],
        "Added Sugars O g",
        confirmed_panel={"added_sugars_g": 0.0},
        confirmed_ingredients="Apple Juice Concentrate",
    )

    assert payload["confirmed_nutrition_values"] == {"added_sugars_g": 0.0}
    assert payload["confirmed_ingredients"] == "Apple Juice Concentrate"
    # Raw OCR text is still supplied, but under a clearly subordinate key.
    assert payload["raw_ocr_text"] == "Added Sugars O g"
    assert "extracted_label_text" not in payload


def test_confirmed_values_default_to_empty():
    payload = llm_utils._build_payload("High Protein", DECISION, [], "Protein 11.5 g")
    assert payload["confirmed_nutrition_values"] == {}
    assert payload["confirmed_ingredients"] == ""


def test_similar_products_are_trimmed_to_exposed_fields():
    rows = [
        {
            "product_name": "Bagrry's No Added Sugar Muesli",
            "category": "Cereals & Breakfast",
            "front_claim": "No Added Sugar",
            "deceptive_mechanism": "date paste",
            "severity_level": "High",
            "internal_reviewer_note": "must not leak to the model",
        }
    ]

    payload = llm_utils._build_payload("No Added Sugar", DECISION, rows, "")

    [sent] = payload["similar_dataset_products"]
    assert sent["product_name"] == "Bagrry's No Added Sugar Muesli"
    assert "internal_reviewer_note" not in sent


# --- what actually goes over the wire --------------------------------------

def test_confirmed_values_reach_the_model(monkeypatch):
    monkeypatch.setattr(llm_utils.config, "LLM_API_KEY", "test-key")
    captured = {}
    _install_fake_openai(monkeypatch, content="Verdict: compliant.", captured=captured)

    text, used = llm_utils.generate_explanation(
        "No Added Sugar",
        DECISION,
        [],
        extracted_text="Added Sugars O g",
        panel={"added_sugars_g": 0.0},
        ingredients="Apple Juice Concentrate",
    )

    assert used is True
    assert text == "Verdict: compliant."

    sent = json.loads(captured["messages"][1]["content"])
    assert sent["confirmed_nutrition_values"] == {"added_sugars_g": 0.0}
    assert sent["confirmed_ingredients"] == "Apple Juice Concentrate"
    assert sent["raw_ocr_text"] == "Added Sugars O g"


# --- fallbacks: the app must never break -----------------------------------

def test_missing_api_key_uses_the_template(monkeypatch):
    monkeypatch.setattr(llm_utils.config, "LLM_API_KEY", "")

    text, used = llm_utils.generate_explanation("No Added Sugar", DECISION, [])

    assert used is False
    assert "meet the official rule" in text
    assert "apple juice concentrate" in text
    assert "The gist" in text


def test_llm_failure_degrades_to_the_template(monkeypatch):
    monkeypatch.setattr(llm_utils.config, "LLM_API_KEY", "test-key")
    _install_fake_openai(monkeypatch, raises=RuntimeError("quota exceeded"))

    text, used = llm_utils.generate_explanation("No Added Sugar", DECISION, [])

    # The verdict still reaches the user; only the prose is degraded.
    assert used is False
    assert "meet the official rule" in text
    assert "LLM unavailable: RuntimeError" in text


def test_template_does_not_list_similar_products():
    products = [{"product_name": "Bagrry's No Added Sugar Muesli"}]
    text = llm_utils.template_explanation("No Added Sugar", DECISION, products)
    assert "Bagrry" not in text
    assert "Watch out" in text


def test_empty_completion_degrades_to_the_template(monkeypatch):
    monkeypatch.setattr(llm_utils.config, "LLM_API_KEY", "test-key")
    _install_fake_openai(monkeypatch, content="   ")

    text, used = llm_utils.generate_explanation("No Added Sugar", DECISION, [])

    assert used is False
    assert "meet the official rule" in text
