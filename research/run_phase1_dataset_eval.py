"""
One-off Phase-1 evaluation: run the existing rule engine on all 25 dataset
products using gold CSV nutrition/ingredient columns (no OCR).

Does not change rule-engine behaviour. Run from repo root:

    python research/run_phase1_dataset_eval.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.claim_mapper import _build_alias_map, get_display_name, map_claim
from backend.dataset_utils import load_dataset
from backend.llm_utils import template_explanation
from backend.rule_engine import evaluate_claim
from backend.utils import infer_form

PANEL_KEYS = (
    "energy_kcal",
    "protein_g",
    "carbohydrates_g",
    "total_sugars_g",
    "added_sugars_g",
    "dietary_fibre_g",
    "total_fat_g",
    "saturated_fat_g",
    "sodium_mg",
)

POSITIVE_STATUSES = {"NON_COMPLIANT", "PROHIBITED"}
NEGATIVE_STATUSES = {"COMPLIANT"}
ABSTAIN_STATUSES = {"INSUFFICIENT_DATA", "UNKNOWN_CLAIM"}


def panel_from_row(row) -> dict:
    panel = {}
    for key in PANEL_KEYS:
        value = row[key]
        if value == value:  # skip NaN
            panel[key] = float(value)
    return panel


def matched_alias(claim_text: str) -> tuple[str | None, str | None]:
    if not claim_text:
        return None, None
    haystack = claim_text.lower().strip()
    for alias, canonical in _build_alias_map():
        if alias and alias in haystack:
            return alias, canonical
    return None, None


def system_label(status: str) -> str:
    if status in NEGATIVE_STATUSES:
        return "Compliant"
    if status in POSITIVE_STATUSES:
        return "Non-Compliant"
    return f"Abstain ({status})"


def gt_label(is_compliant) -> str:
    return "Compliant" if bool(is_compliant) else "Non-Compliant"


def confusion_cell(status: str, gt_compliant: bool) -> str:
    """Place every row in a 2x2 matrix. Abstain is always an error vs boolean GT."""
    gt_positive = not gt_compliant  # Non-Compliant is the positive class
    pred_positive = status in POSITIVE_STATUSES
    pred_negative = status in NEGATIVE_STATUSES
    if pred_positive and gt_positive:
        return "TP"
    if pred_positive and not gt_positive:
        return "FP"
    if pred_negative and not gt_positive:
        return "TN"
    if pred_negative and gt_positive:
        return "FN"
    # Abstain / other: count as the error cell for that GT
    if gt_positive:
        return "FN"
    return "FP"


def main() -> None:
    df = load_dataset()
    rows_out = []
    counts = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}

    for _, row in df.iterrows():
        claim_text = str(row["front_claim"])
        ingredients = str(row["ingredients"]) if row["ingredients"] == row["ingredients"] else ""
        form = infer_form(row.get("category"), row.get("product_name"))
        panel = panel_from_row(row)
        alias, canonical = matched_alias(claim_text)
        decision = evaluate_claim(
            claim_text=claim_text,
            panel=panel,
            ingredients_text=ingredients,
            form=form,
        )
        explanation = template_explanation(claim_text, decision, [])
        status = decision["status"]
        gt_compliant = bool(row["is_technically_compliant"])
        sys_lab = system_label(status)
        gt_lab = gt_label(gt_compliant)
        match = sys_lab == gt_lab
        cell = confusion_cell(status, gt_compliant)
        counts[cell] += 1

        claim_evaluated = get_display_name(canonical) or (
            f"unmapped ({claim_text})" if canonical is None else canonical
        )

        rows_out.append(
            {
                "id": int(row["id"]),
                "product_name": row["product_name"],
                "category": row["category"],
                "front_claim": claim_text,
                "matched_alias": alias,
                "canonical_claim": canonical or decision.get("canonical_claim"),
                "claim_evaluated": claim_evaluated,
                "form": form,
                "status": status,
                "system_label": sys_lab,
                "gt_compliant": gt_compliant,
                "gt_label": gt_lab,
                "match": match,
                "confusion_cell": cell,
                "is_deceptive": bool(decision.get("is_deceptive")),
                "deceptive_flags": decision.get("deceptive_flags") or [],
                "reason": decision.get("reason"),
                "measured_value": decision.get("measured_value"),
                "threshold": decision.get("threshold"),
                "comparator": decision.get("comparator"),
                "rule_id": decision.get("rule_id"),
                "missing_fields": decision.get("missing_fields") or [],
                "warnings": decision.get("warnings") or [],
                "severity_level": row["severity_level"],
                "compliance_clause": row["compliance_clause"],
                "deceptive_mechanism": row["deceptive_mechanism"],
                "explanation": explanation,
            }
        )

    n = len(rows_out)
    tp, fp, tn, fn = counts["TP"], counts["FP"], counts["TN"], counts["FN"]
    correct = sum(1 for r in rows_out if r["match"])
    incorrect = n - correct
    accuracy = correct / n if n else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    summary = {
        "n": n,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "correct": correct,
        "incorrect": incorrect,
        "accuracy": accuracy,
        "precision_non_compliant": precision,
        "recall_non_compliant": recall,
        "f1_non_compliant": f1,
        "status_counts": {},
        "abstain_count": sum(1 for r in rows_out if r["status"] in ABSTAIN_STATUSES),
    }
    for r in rows_out:
        summary["status_counts"][r["status"]] = summary["status_counts"].get(r["status"], 0) + 1

    payload = {"summary": summary, "rows": rows_out}
    out_path = ROOT / "research" / "phase1_dataset_eval_raw.json"
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {out_path}")
    print(f"{'id':>3}  {'match':5}  {'cell':2}  {'status':18}  {'GT':13}  claim")
    for r in rows_out:
        print(
            f"{r['id']:>3}  {str(r['match']):5}  {r['confusion_cell']:2}  "
            f"{r['status']:18}  {r['gt_label']:13}  {r['claim_evaluated']}"
        )


if __name__ == "__main__":
    main()
