"""
Similarity search over the curated 25-product dataset.

Given the user's claim (and optionally category / ingredient keywords), return
the most relevant real Indian products from fmcg_label_audit_dataset.csv, along
with that product's compliance clause and deceptive mechanism. These 2-3 rows
are what make the demo convincing AND they are the only "examples" the LLM is
allowed to cite.

IMPORTANT - this module is SUPPLEMENTARY, not load-bearing:
  * The verdict is produced by backend.rule_engine from fssai_rules.json and
    the values the user supplied. Nothing here can change it.
  * This dataset is a 25-row Phase-1 sample used for illustration only. A claim
    that falls outside it returns NO rows (see MIN_RELEVANCE_SCORE) rather than
    a loosely-related one, so the UI never shows a product that has nothing to
    do with what the user asked about.
  * If the CSV is missing or unreadable, every function degrades to an empty
    result instead of raising. A real deployment must still produce verdicts.
"""
from __future__ import annotations

import difflib
from functools import lru_cache
from typing import Dict, List, Optional

import pandas as pd

from backend.claim_mapper import map_claim
from backend.utils import infer_form
from config import DATASET_PATH, TOP_SIMILAR_PRODUCTS

# Columns we surface to the UI. Everything else stays internal.
_EXPOSED_COLUMNS = (
    "id",
    "product_name",
    "category",
    "front_claim",
    "ingredients",
    "is_technically_compliant",
    "compliance_clause",
    "deceptive_mechanism",
    "severity_level",
)

# A row must earn at least this score to be shown.
#
# The score comes from three terms: +1.0 for a canonical claim match,
# +0.5 for a category match, and at most +0.3 for string similarity. Setting the
# bar at 0.5 means a product qualifies only if it genuinely shares the claim or
# the category; incidental string overlap alone (max 0.3) never qualifies.
#
# Without this cutoff, an off-dataset claim like "Gluten Free" or "Organic"
# ranked three unrelated products (an energy drink, a lassi, a cookie) purely on
# shared letters, and both the UI and the LLM presented them as relevant.
MIN_RELEVANCE_SCORE = 0.5


@lru_cache(maxsize=1)
def load_dataset() -> pd.DataFrame:
    """Load and cache the audit dataset."""
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATASET_PATH}")
    # utf-8-sig strips the BOM present in the curated CSV, so the first column
    # is read as "id" (not "\ufeffid").
    df = pd.read_csv(DATASET_PATH, encoding="utf-8-sig")
    # Cache a canonical claim per row so matching is consistent.
    df["_canonical"] = df["front_claim"].apply(map_claim)
    return df


def _safe_load() -> Optional[pd.DataFrame]:
    """
    load_dataset() but never raises.

    The dataset only supplies illustrative examples, so a missing or malformed
    CSV must not take down a verdict. Callers treat None as "no examples".
    load_dataset() stays strict for data-integrity checks and tests.
    """
    try:
        return load_dataset()
    except Exception:
        return None


def _row_to_dict(row: pd.Series) -> Dict:
    """Convert a dataset row into a JSON-friendly dict for the API."""
    record: Dict = {}
    for col in _EXPOSED_COLUMNS:
        if col not in row:
            continue
        value = row[col]
        # pandas stores values as numpy scalars, which FastAPI/pydantic cannot
        # serialise. .item() converts them to native Python int/float/bool.
        if hasattr(value, "item"):
            value = value.item()
        record[col] = value
    record["inferred_form"] = infer_form(row.get("category"), row.get("product_name"))
    return record


def find_similar(
    claim_text: str,
    category: Optional[str] = None,
    top_n: Optional[int] = None,
    exclude_id: Optional[int] = None,
) -> List[Dict]:
    """
    Rank dataset rows against the query claim.

    Scoring (higher is better):
      +1.0   if the canonical claim matches exactly
      +0.5   if the category matches
      +0.3 * fuzzy string similarity between the raw claim texts
    The fuzzy term is deliberately small so that a meaningful claim/category
    match is never out-ranked by string-length noise.

    Rows scoring below MIN_RELEVANCE_SCORE are dropped, so an off-dataset claim
    returns an empty list rather than the closest-looking unrelated products.
    """
    df = _safe_load()
    if df is None:
        return []

    top_n = top_n or TOP_SIMILAR_PRODUCTS
    query_canonical = map_claim(claim_text)
    query_claim = (claim_text or "").lower().strip()

    scored: List[tuple] = []
    for _, row in df.iterrows():
        if exclude_id is not None and row.get("id") == exclude_id:
            continue

        score = 0.0
        if query_canonical and row.get("_canonical") == query_canonical:
            score += 1.0
        if category and str(row.get("category", "")).lower() == str(category).lower():
            score += 0.5
        score += 0.3 * difflib.SequenceMatcher(
            None, query_claim, str(row.get("front_claim", "")).lower()
        ).ratio()

        if score >= MIN_RELEVANCE_SCORE:
            scored.append((score, row))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [_row_to_dict(row) for _, row in scored[:top_n]]


def get_categories() -> List[str]:
    """Distinct dataset categories - drives the frontend's optional picker."""
    df = _safe_load()
    if df is None or "category" not in df:
        return []
    return sorted({str(c).strip() for c in df["category"].dropna() if str(c).strip()})


def get_sample_products(limit: int = 5) -> List[Dict]:
    """Return the first `limit` products - handy for demos and frontend tests."""
    df = _safe_load()
    if df is None:
        return []
    limit = max(1, min(limit, len(df)))
    return [_row_to_dict(df.iloc[i]) for i in range(limit)]
