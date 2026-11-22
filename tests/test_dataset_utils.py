"""Tests for dataset similarity search."""
from backend import dataset_utils
from backend.dataset_utils import find_similar, get_categories, load_dataset


def test_dataset_loads_all_rows():
    df = load_dataset()
    assert len(df) == 25
    assert df.iloc[0]["id"] == 1  # BOM handled -> column is 'id'


def test_similar_returns_requested_count():
    results = find_similar("No Added Sugar", top_n=3)
    assert len(results) == 3
    assert all("product_name" in p for p in results)


def test_exact_claim_match_ranks_first():
    results = find_similar("No Added Sugar", top_n=3)
    # Bagrry's Muesli and Sunfeast both carry an added-sugar claim.
    top_names = " ".join(p["product_name"] for p in results)
    assert "Bagrry" in top_names or "Sunfeast" in top_names


def test_category_boost_applies():
    # Kellogg's (id 13) is both a "High Protein" claim AND category
    # "Cereals & Breakfast", so it should out-rank a high-protein product from
    # a different category.
    results = find_similar("High Protein", category="Cereals & Breakfast", top_n=3)
    assert results[0]["id"] == 13


# --- relevance cutoff ------------------------------------------------------
# The dataset is a 25-row sample, so most real claims fall outside it. Before
# the cutoff these returned three unrelated products each, chosen on shared
# letters alone, and both the UI and the LLM presented them as relevant.

def test_off_dataset_claim_returns_no_rows():
    # Used to return an energy drink, a protein lassi and a protein cookie.
    assert find_similar("Gluten Free") == []


def test_organic_claim_returns_no_rows():
    assert find_similar("Organic") == []


def test_off_dataset_claim_with_unmatched_category_returns_no_rows():
    assert find_similar("Keto Friendly", category="Not A Real Category") == []


def test_incidental_string_overlap_alone_never_qualifies():
    # 0.3 * fuzzy similarity is the smallest scoring term, so no row may pass on
    # it by itself. Asking for one result must still yield nothing here.
    assert find_similar("Gluten Free", top_n=1) == []


def test_on_dataset_claim_still_returns_rows():
    # The cutoff must not starve claims the dataset does cover.
    assert len(find_similar("No Added Sugar", top_n=3)) == 3


# --- graceful degradation --------------------------------------------------

def test_categories_are_sorted_and_unique():
    categories = get_categories()
    assert categories
    assert categories == sorted(set(categories))


def test_missing_dataset_degrades_to_empty_results(monkeypatch):
    def _boom():
        raise FileNotFoundError("dataset removed")

    monkeypatch.setattr(dataset_utils, "load_dataset", _boom)

    # None of these may raise: the dataset is supplementary.
    assert dataset_utils.find_similar("No Added Sugar") == []
    assert dataset_utils.get_categories() == []
    assert dataset_utils.get_sample_products(3) == []


def test_load_dataset_stays_strict_when_the_file_is_gone(monkeypatch):
    # Data-integrity checks should still fail loudly rather than silently.
    from pathlib import Path

    monkeypatch.setattr(dataset_utils, "DATASET_PATH", Path("does_not_exist.csv"))
    dataset_utils.load_dataset.cache_clear()
    try:
        import pytest

        with pytest.raises(FileNotFoundError):
            dataset_utils.load_dataset()
    finally:
        dataset_utils.load_dataset.cache_clear()
