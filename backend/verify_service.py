"""
Orchestration layer: one function that runs the full verification pipeline.

Order:
  1. (optional) OCR image -> raw text
  2. parse nutrients + ingredients from text
  3. run the rule engine
  4. find similar dataset products
  5. generate a grounded explanation (LLM, or template fallback)

Kept separate from main.py so it can be reused by a CLI, a script, or tests
without spinning up the web server.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from backend import dataset_utils, llm_utils, panel_parser
from backend.claim_mapper import map_claim
from backend.rule_engine import evaluate_claim
from backend.utils import infer_form
from config import DEFAULT_FORM


def verify(
    claim_text: str,
    panel: Optional[Dict[str, float]] = None,
    ingredients: str = "",
    raw_text: str = "",
    form: str = "auto",
    category: Optional[str] = None,
    use_llm: bool = True,
) -> Dict:
    """
    Run the full pipeline and return a plain dict matching VerifyResponse.

    This function never raises for "normal" product problems (missing nutrients,
    unknown claim, etc.) - it returns an INSUFFICIENT_DATA / UNKNOWN_CLAIM
    verdict instead.
    """
    raw_text = raw_text or ""

    # Derive panel + ingredients from raw text if not supplied explicitly.
    if raw_text:
        if not panel:
            panel = panel_parser.parse_nutrition_panel(raw_text)
        if not ingredients:
            ingredients = panel_parser.extract_ingredients(raw_text)

    panel = panel or {}
    serving_basis = panel_parser.detect_serving_basis(raw_text) if raw_text else "unknown"

    resolved_form = form if form in ("solid", "liquid") else infer_form(category)
    if resolved_form not in ("solid", "liquid"):
        resolved_form = DEFAULT_FORM

    decision = evaluate_claim(
        claim_text=claim_text,
        panel=panel,
        ingredients_text=ingredients,
        form=resolved_form,
        raw_text=raw_text,
        serving_basis=serving_basis,
    )

    similar: List[Dict] = dataset_utils.find_similar(claim_text, category=category)

    if use_llm:
        # Pass the confirmed values through as well as the raw text. The user
        # corrects OCR misreads in the UI, so `panel`/`ingredients` are the
        # authoritative figures and `raw_text` is only fallback context.
        explanation, llm_used = llm_utils.generate_explanation(
            claim_text,
            decision,
            similar,
            extracted_text=raw_text,
            panel=panel,
            ingredients=ingredients,
        )
    else:
        explanation, llm_used = (
            llm_utils.template_explanation(claim_text, decision, similar),
            False,
        )

    return {
        "claim_text": claim_text,
        "canonical_claim": decision.get("canonical_claim") or map_claim(claim_text),
        "form": resolved_form,
        "decision": decision,
        "similar_products": similar,
        "explanation": explanation,
        "llm_used": llm_used,
        "parsed_panel": panel,
        "extracted_text": raw_text or None,
    }
