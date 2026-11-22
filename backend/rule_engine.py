"""
The rule engine: the deterministic heart of the verifier.

Given a claim, the extracted nutrition panel, the ingredients text and the
physical form (solid/liquid), it returns a verdict that is:
  * grounded    - it only uses fssai_rules.json + the numbers it was handed
  * explicit    - it names the FSSAI rule id and the exact comparison made
  * honest      - it says INSUFFICIENT_DATA rather than guessing

It deliberately separates two ideas the whole project is about:
  * "is_technically_compliant"  -> does it satisfy the numeric FSSAI threshold?
  * "is_deceptive"              -> does the ingredient list hide the real story
                                   (e.g. "No Added Sugar" + apple juice
                                   concentrate / maltodextrin)?

Per-serving panels are NOT compared against per-100 thresholds silently; a
warning is raised instead (see detect_serving_basis in panel_parser).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from backend.claim_mapper import map_claim
from backend.rules_loader import get_claim, get_prohibited_terms
from backend.utils import contains_any

# Status constants (also form the API contract).
STATUS_COMPLIANT = "COMPLIANT"
STATUS_NON_COMPLIANT = "NON_COMPLIANT"
STATUS_PROHIBITED = "PROHIBITED"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
STATUS_UNKNOWN_CLAIM = "UNKNOWN_CLAIM"


def _compare(value: float, comparator: str, threshold: float) -> bool:
    """Apply a comparison operator between two numbers."""
    if comparator == ">=":
        return value >= threshold
    if comparator == "<=":
        return value <= threshold
    if comparator == ">":
        return value > threshold
    if comparator == "<":
        return value < threshold
    raise ValueError(f"Unsupported comparator: {comparator}")


def _empty_decision() -> Dict[str, Any]:
    return {
        "status": STATUS_INSUFFICIENT_DATA,
        "rule_id": None,
        "canonical_claim": None,
        "measured_value": None,
        "threshold": None,
        "comparator": None,
        "unit": None,
        "reason": "",
        "is_technically_compliant": None,
        "is_deceptive": False,
        "deceptive_flags": [],
        "missing_fields": [],
        "requires_disclaimer": None,
        "disclaimer_present": None,
        "warnings": [],
    }


def evaluate_claim(
    claim_text: str,
    panel: Optional[Dict[str, float]] = None,
    ingredients_text: str = "",
    form: str = "solid",
    raw_text: str = "",
    serving_basis: str = "unknown",
) -> Dict[str, Any]:
    """
    Evaluate a single claim against the FSSAI rules.

    Parameters
    ----------
    claim_text      : the front-of-pack claim, exactly as written.
    panel           : {nutrient: value} extracted from the nutrition panel.
    ingredients_text: the ingredients string (used for ingredient-sensitive claims).
    form            : "solid" or "liquid".
    raw_text        : full label text (used for disclaimer detection).
    serving_basis   : "per_100" | "per_serving" | "unknown".

    Returns a decision dict (see _empty_decision for the shape).
    """
    panel = panel or {}
    decision = _empty_decision()
    form = form if form in ("solid", "liquid") else "solid"

    combined_text = f"{claim_text} {ingredients_text} {raw_text}".lower()
    ingredients_low = (ingredients_text or "").lower()

    # ---- 1) Prohibited / high-risk terms short-circuit ----------------------
    prohibited = get_prohibited_terms()
    hits = contains_any(combined_text, prohibited.get("keywords", []))
    if hits:
        decision.update(
            status=STATUS_PROHIBITED,
            rule_id=prohibited.get("rule_id"),
            is_technically_compliant=False,
            reason=(
                prohibited.get("message", "Prohibited claim term detected.")
                + f" Triggered by: {', '.join(hits)}."
            ),
            deceptive_flags=hits,
        )
        return decision

    # ---- 2) Map the claim to a canonical rule -------------------------------
    canonical = map_claim(claim_text)
    decision["canonical_claim"] = canonical
    if canonical is None:
        decision.update(
            status=STATUS_UNKNOWN_CLAIM,
            is_technically_compliant=None,
            reason=(
                "This claim is not covered by the Phase-1 rule set, so no "
                "automatic pass/fail decision was made."
            ),
        )
        return decision

    claim = get_claim(canonical) or {}
    decision["rule_id"] = claim.get("rule_id")
    nutrient = claim.get("nutrient")
    thresholds = claim.get("thresholds") or {}
    threshold = thresholds.get(form, thresholds.get("solid"))
    decision["threshold"] = threshold
    decision["comparator"] = claim.get("comparator")
    decision["unit"] = claim.get("unit")

    # Warn when the panel is per-serving (thresholds are per 100 g/ml).
    if serving_basis == "per_serving":
        decision["warnings"].append(
            "The nutrition panel appears to be declared PER SERVING. FSSAI "
            "thresholds used here are per 100 g / 100 ml, so please confirm the "
            "per-100 values before relying on this verdict."
        )

    # ---- 3) Ingredient checks ----------------------------------------------
    hard_hits = contains_any(ingredients_low, claim.get("hard_deny_list", []))
    soft_hits = contains_any(ingredients_low, claim.get("soft_deny_list", []))
    decision["deceptive_flags"] = soft_hits

    # ---- 4) Numeric check (skipped for ingredient-only rules) ---------------
    numeric_ok: Optional[bool] = None
    if nutrient is not None:
        value = panel.get(nutrient)
        decision["measured_value"] = value
        if value is None:
            decision["missing_fields"] = [nutrient]
            decision.update(
                status=STATUS_INSUFFICIENT_DATA,
                is_technically_compliant=None,
                reason=(
                    f"Could not find '{nutrient}' in the nutrition panel. "
                    "Enter it manually to get a verdict."
                ),
            )
            return decision
        numeric_ok = _compare(value, claim.get("comparator", ">="), threshold or 0.0)

    # ---- 5) Combine into a verdict -----------------------------------------
    # Hard deny = an ingredient that outright contradicts the claim.
    if hard_hits:
        decision.update(
            status=STATUS_NON_COMPLIANT,
            is_technically_compliant=False,
            is_deceptive=True,
            reason=(
                claim.get("fail_text", "Claim contradicted by the ingredients list.")
                + f" Contradicting ingredient(s): {', '.join(hard_hits)}."
            ),
        )
        return decision

    if numeric_ok is None:
        # Ingredient-only rule (e.g. 100% wholewheat) with no numeric nutrient.
        decision.update(
            status=STATUS_COMPLIANT,
            is_technically_compliant=True,
            reason=claim.get("pass_text", "No contradicting ingredient found."),
        )
    elif numeric_ok:
        decision.update(
            status=STATUS_COMPLIANT,
            is_technically_compliant=True,
            reason=claim.get("pass_text", "Meets the FSSAI threshold."),
        )
    else:
        decision.update(
            status=STATUS_NON_COMPLIANT,
            is_technically_compliant=False,
            reason=claim.get("fail_text", "Fails the FSSAI threshold."),
        )

    # ---- 6) Deception layer (independent of the numeric verdict) -----------
    if soft_hits:
        decision["is_deceptive"] = True
        decision["warnings"].append(
            claim.get("deceptive_note", "A sugar substitute / hidden ingredient is present.")
            + f" Flagged ingredient(s): {', '.join(soft_hits)}."
        )

    # ---- 7) Mandatory disclaimer for "No Added Sugar" ----------------------
    disclaimer = claim.get("requires_disclaimer")
    if disclaimer:
        decision["requires_disclaimer"] = disclaimer
        present = disclaimer.lower() in (raw_text or "").lower()
        decision["disclaimer_present"] = present
        if not present:
            decision["warnings"].append(
                f"Missing mandatory label statement: '{disclaimer}'."
            )

    return decision
