"""
Grounded explanation generator for the free LLM providers (Groq / OpenRouter).

Hard rules enforced by the prompt:
  * Use ONLY the OCR text, the rule-engine verdict and the listed dataset rows.
  * Never invent a product, ingredient or number.
  * If a fact is missing, say it is not available in the extracted text.

If no API key is configured (or the call fails), we fall back to a deterministic
template so the app NEVER breaks - important for a live university demo.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import config

_SYSTEM_PROMPT = """You write a precise shopper-facing summary of a food-label check.

ABSOLUTE RULES:
1. Use ONLY the JSON payload. Do not use outside knowledge.
2. Never invent a product name, ingredient, or nutrition number.
3. If a needed fact is missing, say it is not on the label.
4. Separate (a) whether the official rule is met from (b) whether the ingredients still mislead.
5. confirmed_nutrition_values and confirmed_ingredients are what the user verified. Prefer them over raw_ocr_text.
6. Do not mention similar products, the dataset, rule IDs, or status codes (COMPLIANT, etc.).
7. No markdown, bullets, numbered lists, or bold.

OUTPUT — use these headings exactly, with a blank line between sections. 180–240 words. Be specific, not vague.

The gist
3–4 sentences. State clearly whether this pack is allowed to use the claim. Explain what the claim is promising in everyday language. If the numbers pass but ingredients still mislead, say both facts so the shopper does not take this as an all-clear.

Why it landed this way
3–4 sentences. Quote the confirmed measured value, the official limit, and the unit. Say whether the figure is inside or outside that limit, and what that means for the claim. Mention a missing value or per-serving warning if the payload has one. Skip this section only if there is no number and no reason.

Watch out
Include whenever is_deceptive is true or deceptive_flags is non-empty. 3–4 sentences. Name each flagged ingredient. Explain how it can add sweetness, calories, or a health halo that the front claim does not mention. Omit this section only when there is no loophole."""


def _build_payload(
    claim_text: str,
    decision: Dict[str, Any],
    similar_products: List[Dict],
    extracted_text: str,
    confirmed_panel: Optional[Dict[str, Any]] = None,
    confirmed_ingredients: str = "",
) -> Dict[str, Any]:
    """Compact, grounded payload - keeps us inside free-tier token limits."""
    trimmed_products = [
        {
            "product_name": p.get("product_name"),
            "category": p.get("category"),
            "front_claim": p.get("front_claim"),
            "is_technically_compliant": p.get("is_technically_compliant"),
            "compliance_clause": p.get("compliance_clause"),
            "deceptive_mechanism": p.get("deceptive_mechanism"),
            "severity_level": p.get("severity_level"),
        }
        for p in similar_products
    ]
    return {
        "user_claim": claim_text,
        "rule_engine_decision": {
            "status": decision.get("status"),
            "rule_id": decision.get("rule_id"),
            "reason": decision.get("reason"),
            "measured_value": decision.get("measured_value"),
            "threshold": decision.get("threshold"),
            "unit": decision.get("unit"),
            "is_technically_compliant": decision.get("is_technically_compliant"),
            "is_deceptive": decision.get("is_deceptive"),
            "deceptive_flags": decision.get("deceptive_flags"),
            "warnings": decision.get("warnings"),
        },
        # Authoritative: what the user confirmed on screen, after correcting OCR.
        "confirmed_nutrition_values": confirmed_panel or {},
        "confirmed_ingredients": confirmed_ingredients or "",
        # Fallback context only - may still contain the OCR's misreads.
        "raw_ocr_text": (extracted_text or "")[:2000],
        "similar_dataset_products": trimmed_products,
    }


def _limit_phrase(comparator: Optional[str], threshold: Any, unit: str) -> str:
    amount = f"{threshold} {unit}".strip() if threshold is not None else "the official limit"
    if comparator in (">=", "gte"):
        return f"at least {amount}"
    if comparator in ("<=", "lte"):
        return f"at most {amount}"
    if comparator in (">", "gt"):
        return f"more than {amount}"
    if comparator in ("<", "lt"):
        return f"less than {amount}"
    return amount


def template_explanation(
    claim_text: str,
    decision: Dict[str, Any],
    similar_products: List[Dict],
) -> str:
    """Deterministic fallback used when no LLM is available.

    `similar_products` is unused on purpose: the UI already lists those packs.
    """
    status = decision.get("status", "UNKNOWN_CLAIM")
    unit = decision.get("unit") or ""
    measured = decision.get("measured_value")
    threshold = decision.get("threshold")
    comparator = decision.get("comparator")
    reason = (decision.get("reason") or "").strip()
    flags = [f for f in (decision.get("deceptive_flags") or []) if f]
    deceptive = bool(decision.get("is_deceptive") or flags)

    if status == "COMPLIANT" and deceptive:
        gist = (
            f'The numbers on this pack meet the official rule for "{claim_text}", '
            "so the wording is allowed. That is not the same as the food being a healthy choice. "
            "The ingredient list still contains items that can make the front of the pack look cleaner than the food is."
        )
    elif status == "COMPLIANT":
        gist = (
            f'The numbers on this pack meet the official rule for "{claim_text}". '
            "The pack is allowed to use this wording. That only confirms the legal threshold, not overall healthiness."
        )
    elif status == "NON_COMPLIANT":
        gist = (
            f'The numbers on this pack do not meet the official rule for "{claim_text}". '
            "A shopper reading the front of the pack would get a stronger promise than the nutrition table supports."
        )
    elif status == "PROHIBITED":
        gist = (
            f'Official rules do not allow a pack to use wording like "{claim_text}". '
            "Foods may describe nutrients, but they may not claim to prevent, treat, or cure disease."
        )
    elif status == "INSUFFICIENT_DATA":
        missing = ", ".join(decision.get("missing_fields") or []) or "a key nutrition value"
        gist = (
            f'There is not enough information on the label to check "{claim_text}". '
            f"The check still needs {missing} before a pass or fail can be given."
        )
    elif status == "UNKNOWN_CLAIM":
        gist = (
            f'"{claim_text}" is not one of the claims this checker can judge yet. '
            "No pass or fail has been issued."
        )
    else:
        gist = f'The check for "{claim_text}" could not be completed.'

    blocks = ["The gist", gist]

    why_bits: List[str] = []
    if measured is not None and threshold is not None:
        why_bits.append(
            f"The label shows {measured} {unit}".strip()
            + f". The official limit for this claim is {_limit_phrase(comparator, threshold, unit)}."
        )
    if reason:
        why_bits.append(reason)
    if why_bits:
        if measured is not None and threshold is not None:
            if status == "COMPLIANT":
                why_bits.append(
                    "Because that figure sits inside the limit, the claim is technically allowed."
                )
            elif status == "NON_COMPLIANT":
                why_bits.append(
                    "Because that figure sits outside the limit, the claim does not hold up."
                )
        blocks.extend(["", "Why it landed this way", " ".join(why_bits)])

    if deceptive:
        named = ", ".join(flags) if flags else "an ingredient that undercuts the claim"
        blocks.extend(
            [
                "",
                "Watch out",
                (
                    f"The claim can still mislead even when the numbers pass. "
                    f"The ingredient list includes {named}. "
                    "Those ingredients can add sweetness, sugars, or a health halo that the front claim does not mention, "
                    "so a shopper can still be left with the wrong impression."
                ),
            ]
        )

    return "\n".join(blocks)


def generate_explanation(
    claim_text: str,
    decision: Dict[str, Any],
    similar_products: List[Dict],
    extracted_text: str = "",
    panel: Optional[Dict[str, Any]] = None,
    ingredients: str = "",
) -> Tuple[str, bool]:
    """
    Return (explanation_text, used_llm).

    `panel` and `ingredients` should be the values the user confirmed on screen,
    not the raw OCR output: they take precedence in the prompt so the model never
    narrates a digit the user has already corrected.

    Falls back to a deterministic template when no key is set or the call fails,
    so the API contract is always satisfied.
    """
    if not config.LLM_API_KEY:
        return template_explanation(claim_text, decision, similar_products), False

    try:
        from openai import OpenAI  # OpenAI-compatible client for Groq/OpenRouter

        client = OpenAI(
            base_url=config.LLM_BASE_URL,
            api_key=config.LLM_API_KEY,
            timeout=config.LLM_TIMEOUT_SECONDS,
        )
        payload = _build_payload(
            claim_text,
            decision,
            similar_products,
            extracted_text,
            confirmed_panel=panel,
            confirmed_ingredients=ingredients,
        )
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        text = _tidy_explanation((response.choices[0].message.content or "").strip())
        if text:
            return text, True
        return template_explanation(claim_text, decision, similar_products), False
    except Exception as exc:  # network / quota / auth - degrade gracefully
        fallback = template_explanation(claim_text, decision, similar_products)
        return f"{fallback}\n\n(LLM unavailable: {type(exc).__name__})", False


def _tidy_explanation(text: str) -> str:
    """Strip markdown and any similar-product recap the model should not write."""
    if not text:
        return ""
    cleaned_lines: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        lowered = line.lower()
        if lowered.startswith(("similar pack", "similar real", "similar product")):
            continue
        line = line.lstrip("#").strip()
        line = line.replace("**", "").replace("__", "")
        cleaned_lines.append(line)
    tidy = "\n".join(cleaned_lines).strip()
    while "\n\n\n" in tidy:
        tidy = tidy.replace("\n\n\n", "\n\n")
    return tidy
