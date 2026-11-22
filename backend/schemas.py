"""
Pydantic request/response models = the stable contract your frontend codes to.

Keep these in sync with the API docs at http://localhost:8000/docs.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class PanelValues(BaseModel):
    """Nutrition values the user (or OCR) has provided. All optional."""

    energy_kcal: Optional[float] = None
    protein_g: Optional[float] = None
    carbohydrates_g: Optional[float] = None
    total_sugars_g: Optional[float] = None
    added_sugars_g: Optional[float] = None
    dietary_fibre_g: Optional[float] = None
    total_fat_g: Optional[float] = None
    saturated_fat_g: Optional[float] = None
    sodium_mg: Optional[float] = None


class Decision(BaseModel):
    """The rule-engine verdict."""

    status: str
    rule_id: Optional[str] = None
    canonical_claim: Optional[str] = None
    measured_value: Optional[float] = None
    threshold: Optional[float] = None
    comparator: Optional[str] = None
    unit: Optional[str] = None
    reason: str = ""
    is_technically_compliant: Optional[bool] = None
    is_deceptive: bool = False
    deceptive_flags: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    requires_disclaimer: Optional[str] = None
    disclaimer_present: Optional[bool] = None
    warnings: List[str] = Field(default_factory=list)


class SimilarProduct(BaseModel):
    id: Optional[int] = None
    product_name: Optional[str] = None
    category: Optional[str] = None
    front_claim: Optional[str] = None
    ingredients: Optional[str] = None
    is_technically_compliant: Optional[bool] = None
    compliance_clause: Optional[str] = None
    deceptive_mechanism: Optional[str] = None
    severity_level: Optional[str] = None
    inferred_form: Optional[str] = None


class VerifyResponse(BaseModel):
    claim_text: str
    canonical_claim: Optional[str] = None
    form: str
    decision: Decision
    similar_products: List[SimilarProduct] = Field(default_factory=list)
    explanation: str = ""
    llm_used: bool = False
    parsed_panel: dict = Field(default_factory=dict)
    extracted_text: Optional[str] = None


class VerifyJsonRequest(BaseModel):
    """JSON body for POST /verify/json (no image - manual entry or pasted text)."""

    claim: str = Field(..., description="Front-of-pack claim, e.g. 'No Added Sugar'")
    form: Literal["solid", "liquid", "auto"] = "auto"
    panel: Optional[PanelValues] = None
    ingredients: Optional[str] = None
    label_text: Optional[str] = Field(
        default=None,
        description="Optional raw label text; nutrients/ingredients are parsed from it.",
    )
    category: Optional[str] = None
    use_llm: bool = True
