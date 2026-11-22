"""
Central configuration for the URE Nutrition Claim Verifier (Phase-1).

Every magic number, file path and environment-driven setting lives here, so the
rest of the code stays declarative and easy to defend in a university demo.

Nothing in this file talks to the network or the disk at import time (other
than loading the optional .env file).
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a local .env file if present (ignored if missing).
load_dotenv()

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent

# Machine-readable rules (see fssai_rules.json).
RULES_PATH = BASE_DIR / "fssai_rules.json"

# Curated 25-product dataset (source of truth for "similar examples").
DATASET_PATH = BASE_DIR / "fmcg_label_audit_dataset.csv"

# --------------------------------------------------------------------------- #
# RDA reference values (ICMR-NIN, adult)
# --------------------------------------------------------------------------- #
# IMPORTANT: Phase-1 decisions use the FIXED per-100g / per-100ml thresholds in
# fssai_rules.json (deterministic and easy to verify). The RDA values below are
# used ONLY for informational "% of RDA" text shown to the user.
RDA_REFERENCE = {
    "protein_g_per_day": 50.0,
    "fibre_g_per_day": 25.0,
}

# Physical form used when it cannot be inferred ("solid" or "liquid").
DEFAULT_FORM = "solid"

# --------------------------------------------------------------------------- #
# LLM configuration (free tiers only)
# --------------------------------------------------------------------------- #
# Provider: "groq" (default) or "openrouter". Both are OpenAI-compatible.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()

_PROVIDER_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

# Default free models (see README / chat notes for the full free lineup).
#   Groq free   : qwen/qwen3.8-27b (fast & clean), openai/gpt-oss-20b
#   OpenRouter  : nvidia/nemotron-3.5-super-vl:free (vision), etc.
_PROVIDER_DEFAULT_MODELS = {
    "groq": "qwen/qwen3.8-27b",
    "openrouter": "nvidia/nemotron-3.5-super-vl:free",
}

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip() or _PROVIDER_BASE_URLS.get(
    LLM_PROVIDER, _PROVIDER_BASE_URLS["groq"]
)
LLM_MODEL = os.getenv("LLM_MODEL", "").strip() or _PROVIDER_DEFAULT_MODELS.get(
    LLM_PROVIDER, _PROVIDER_DEFAULT_MODELS["groq"]
)

# Pick up whichever key the user provided.
LLM_API_KEY = (
    os.getenv("GROQ_API_KEY", "").strip()
    or os.getenv("OPENROUTER_API_KEY", "").strip()
    or os.getenv("LLM_API_KEY", "").strip()
)

LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "700"))
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

# --------------------------------------------------------------------------- #
# OCR configuration (optional - only needed for image input)
# --------------------------------------------------------------------------- #
# Engine used to turn a label photo into text. "rapidocr" is the default and
# installs on Python 3.14; "tesseract" is an alternative if you have the
# Tesseract binary installed. See backend/ocr_utils.py for the trade-offs.
OCR_ENGINE = os.getenv("OCR_ENGINE", "rapidocr").strip().lower()

# --------------------------------------------------------------------------- #
# Misc
# --------------------------------------------------------------------------- #
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "8"))
TOP_SIMILAR_PRODUCTS = int(os.getenv("TOP_SIMILAR_PRODUCTS", "3"))
