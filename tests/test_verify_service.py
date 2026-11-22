"""
The verdict must never depend on the curated dataset.

The dataset only supplies illustrative "similar products". These tests pin that
down: remove the dataset entirely and the rule engine must still produce exactly
the same verdict from the user's own numbers.
"""
from backend import dataset_utils
from backend.verify_service import verify

PANEL = {
    "protein_g": 11.5,
    "total_sugars_g": 14.5,
    "added_sugars_g": 0.0,
    "dietary_fibre_g": 10.2,
}
INGREDIENTS = "Multigrain (85.2%), Apple Juice Concentrate, Antioxidant (INS 306)"


def _break_dataset(monkeypatch):
    def _boom():
        raise FileNotFoundError("dataset removed")

    monkeypatch.setattr(dataset_utils, "load_dataset", _boom)


def test_verdict_survives_a_missing_dataset(monkeypatch):
    _break_dataset(monkeypatch)

    result = verify(
        "No Added Sugar",
        panel=PANEL,
        ingredients=INGREDIENTS,
        form="solid",
        use_llm=False,
    )

    # Rule engine still decides from the user's own numbers...
    assert result["decision"]["status"] == "COMPLIANT"
    assert result["decision"]["is_deceptive"] is True
    flags = [f.lower() for f in result["decision"]["deceptive_flags"]]
    assert any("apple juice" in flag for flag in flags)

    # ...and the missing dataset only costs us the examples.
    assert result["similar_products"] == []


def test_verdict_is_identical_with_and_without_the_dataset(monkeypatch):
    with_dataset = verify(
        "No Added Sugar", panel=PANEL, ingredients=INGREDIENTS, form="solid", use_llm=False
    )

    _break_dataset(monkeypatch)
    without_dataset = verify(
        "No Added Sugar", panel=PANEL, ingredients=INGREDIENTS, form="solid", use_llm=False
    )

    # Everything except the illustrative rows must match exactly.
    assert without_dataset["decision"] == with_dataset["decision"]
    assert without_dataset["canonical_claim"] == with_dataset["canonical_claim"]
    assert without_dataset["form"] == with_dataset["form"]


def test_category_is_forwarded_to_similarity_search(monkeypatch):
    seen = {}

    def _spy(claim_text, category=None, **kwargs):
        seen["category"] = category
        return []

    monkeypatch.setattr(dataset_utils, "find_similar", _spy)

    verify(
        "High Protein",
        panel={"protein_g": 11.5},
        form="solid",
        category="Cereals & Breakfast",
        use_llm=False,
    )

    assert seen["category"] == "Cereals & Breakfast"
