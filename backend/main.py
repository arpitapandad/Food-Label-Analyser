"""
FastAPI application - the single backend surface your frontend talks to.

Run locally:
    uvicorn backend.main:app --reload --port 8000
Interactive docs:
    http://localhost:8000/docs

Endpoints
---------
GET  /health              -> liveness + config summary (incl. OCR availability)
GET  /claims              -> supported claims (for building a dropdown)
GET  /categories          -> distinct dataset categories (optional picker)
GET  /dataset/sample      -> a few rows from the curated dataset
POST /ocr/extract         -> multipart: OCR only -> text + parsed values (no verdict)
POST /verify              -> multipart: claim + up to 2 images (ingredients + panel)
POST /verify/json         -> JSON: claim + manual values / pasted label text
GET  /                    -> the built React frontend (if frontend/dist exists)

CORS is fully open so any frontend (Streamlit, React, plain HTML) can call it
during development. Lock this down before any public deployment.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from backend import dataset_utils, panel_parser
from backend.ocr_utils import (
    OCRExtractionError,
    OCRUnavailableError,
    build_engine,
    extract_combined_text,
    normalize_image_file,
)
from backend.rules_loader import get_claims, get_meta
from backend.schemas import VerifyJsonRequest, VerifyResponse
from backend.verify_service import verify

app = FastAPI(
    title="URE Nutrition Claim Verifier API",
    description="Backend for the FSSAI nutrition-claim audit (Phase-1).",
    version="0.1.0",
)

# Open CORS for local development. Restrict origins before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """Liveness probe + a summary of how the service is configured."""
    return {
        "status": "ok",
        "rules_version": get_meta().get("version"),
        "llm_provider": config.LLM_PROVIDER,
        "llm_model": config.LLM_MODEL,
        "llm_configured": bool(config.LLM_API_KEY),
        "ocr_engine": config.OCR_ENGINE,
        "ocr_available": build_engine(),
    }


@app.get("/claims")
def claims() -> dict:
    """List the claims this system can evaluate (build your dropdown from this)."""
    return {
        "claims": [
            {
                "canonical": c.get("canonical"),
                "display_name": c.get("display_name"),
                "aliases": c.get("aliases", []),
                "rule_id": c.get("rule_id"),
            }
            for c in get_claims()
        ],
        "prohibited_examples": [
            "100% Pure", "Cures", "Boosts Immunity", "Diabetic Friendly",
        ],
    }


@app.get("/categories")
def categories() -> dict:
    """
    Distinct dataset categories (for an optional picker in the UI).

    Picking one improves two things: `infer_form` can guess solid vs liquid when
    the user hasn't said, and find_similar adds its category bonus. Neither is
    required for a correct verdict - the claim and the panel decide that.
    """
    return {"categories": dataset_utils.get_categories()}


@app.get("/dataset/sample")
def dataset_sample(limit: int = 5) -> dict:
    """Return a few real products (useful for demos / testing the frontend)."""
    products = dataset_utils.get_sample_products(limit)
    return {"count": len(products), "products": products}


@app.post("/ocr/extract")
async def ocr_extract(
    ingredients_file: Optional[UploadFile] = File(
        None, description="Photo of the INGREDIENT LIST"
    ),
    panel_file: Optional[UploadFile] = File(
        None, description="Photo of the NUTRITION TABLE"
    ),
    file: Optional[UploadFile] = File(
        None, description="Single combined photo (legacy)"
    ),
) -> dict:
    """
    OCR ONLY - extract text and values, but do NOT decide a verdict.

    The UI calls this right after the two scans so the user can see (and fix)
    what was read before the claim is checked. That two-step flow is what makes
    the verdict trustworthy: a single misread digit cannot silently change the
    answer, because the user confirms the numbers first.

    The corrected values are then posted to /verify/json, which returns the
    same response shape as /verify.
    """
    raw_text_parts: list = []
    ingredients_text = ""

    if panel_file is not None:
        raw_text_parts.append(await _ocr_upload(panel_file))

    if ingredients_file is not None:
        ingredients_ocr = await _ocr_upload(ingredients_file)
        raw_text_parts.append(ingredients_ocr)
        ingredients_text = panel_parser.extract_ingredients(ingredients_ocr)
        if not ingredients_text:
            # The heading was cropped or misread. The rest of the photo is
            # still the ingredient list, so surface it for the user to edit
            # instead of leaving the field empty.
            ingredients_text = panel_parser.ingredient_text_fallback(ingredients_ocr)

    if file is not None:
        raw_text_parts.append(await _ocr_upload(file))

    raw_text = "\n".join(part for part in raw_text_parts if part)

    # Fall back to the combined text when there was no dedicated ingredient photo.
    if not ingredients_text:
        ingredients_text = panel_parser.extract_ingredients(raw_text)

    return {
        "extracted_text": raw_text,
        "parsed_panel": panel_parser.parse_nutrition_panel(raw_text),
        "ingredients": ingredients_text,
        "serving_basis": panel_parser.detect_serving_basis(raw_text),
    }


@app.post("/verify/json", response_model=VerifyResponse)
def verify_json(payload: VerifyJsonRequest) -> VerifyResponse:
    """Verify a claim from JSON input (manual nutrition values and/or pasted text)."""
    panel = payload.panel.model_dump(exclude_none=True) if payload.panel else None
    result = verify(
        claim_text=payload.claim,
        panel=panel,
        ingredients=payload.ingredients or "",
        raw_text=payload.label_text or "",
        form=payload.form,
        category=payload.category,
        use_llm=payload.use_llm,
    )
    return VerifyResponse(**result)


async def _ocr_upload(upload: UploadFile) -> str:
    """
    Validate one uploaded image, OCR it, and return the extracted text.

    A temp file is used because the OCR engines expect a path, not a buffer.
    Raises HTTPException with a helpful status code on any failure.
    """
    suffix = Path(upload.filename or "upload.jpg").suffix or ".jpg"
    data = await upload.read()
    if not data:
        return ""
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"'{upload.filename}' exceeds the {config.MAX_UPLOAD_MB} MB limit.",
        )

    tmp_path = None
    normalized_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        # Apply EXIF rotation and cap the resolution before the engine runs.
        # Run in worker threads so the async event loop stays responsive.
        normalized_path = await asyncio.to_thread(normalize_image_file, tmp_path)
        return await asyncio.to_thread(
            extract_combined_text, normalized_path or tmp_path
        )
    except OCRUnavailableError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except OCRExtractionError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not read '{upload.filename or 'image'}': {exc}",
        )
    finally:
        if normalized_path:
            Path(normalized_path).unlink(missing_ok=True)
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


@app.post("/verify", response_model=VerifyResponse)
async def verify_image(
    claim: str = Form(..., description="Front-of-pack claim"),
    ingredients_file: Optional[UploadFile] = File(
        None, description="Photo of the INGREDIENT LIST"
    ),
    panel_file: Optional[UploadFile] = File(
        None, description="Photo of the NUTRITION TABLE"
    ),
    file: Optional[UploadFile] = File(
        None, description="Single combined photo (legacy; used if the two above are absent)"
    ),
    form: str = Form("auto", description="solid | liquid | auto"),
    panel_json: Optional[str] = Form(None, description="Optional manual panel as JSON"),
    ingredients: Optional[str] = Form(None, description="Optional manual ingredients text"),
    category: Optional[str] = Form(None),
    use_llm: bool = Form(True),
) -> VerifyResponse:
    """
    Verify a claim from label photos, with optional manual overrides.

    The front-of-pack design calls for TWO scans (ingredient list + nutrition
    table), so this endpoint accepts them separately:

      * `ingredients_file` -> OCR text is parsed for the ingredient string
      * `panel_file`       -> OCR text is parsed for the nutrition numbers
      * `file`             -> legacy single image, OCR'd as a combined label

    Any combination works: send both, send one, or send none and pass
    `panel_json` / `ingredients` by hand. Manual values always take precedence
    over OCR output. If OCR is not installed, the endpoint still works via the
    manual fields instead of failing.
    """
    manual_panel = None
    if panel_json:
        try:
            manual_panel = json.loads(panel_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"panel_json is not valid JSON: {exc}")

    ingredients_text = ingredients or ""
    raw_text_parts: list = []

    # Nutrition table first, so the parsed panel is not confused by the
    # ingredient text that follows it.
    if panel_file is not None:
        raw_text_parts.append(await _ocr_upload(panel_file))

    if ingredients_file is not None:
        ingredients_ocr = await _ocr_upload(ingredients_file)
        raw_text_parts.append(ingredients_ocr)
        # Extract here rather than letting verify() guess from combined text:
        # the ingredient photo is a much more reliable source than a mixed blob.
        if not ingredients_text:
            ingredients_text = panel_parser.extract_ingredients(ingredients_ocr)
            if not ingredients_text:
                ingredients_text = panel_parser.ingredient_text_fallback(ingredients_ocr)

    if file is not None:
        raw_text_parts.append(await _ocr_upload(file))

    raw_text = "\n".join(part for part in raw_text_parts if part)

    result = verify(
        claim_text=claim,
        panel=manual_panel,
        ingredients=ingredients_text,
        raw_text=raw_text,
        form=form,
        category=category,
        use_llm=use_llm,
    )
    return VerifyResponse(**result)


# --------------------------------------------------------------------------- #
# Frontend hosting
# --------------------------------------------------------------------------- #
# The React app is built into frontend/dist (see frontend/README notes) and
# served from the same origin as the API, so the browser needs no CORS and
# "http://localhost" counts as a secure origin for phone camera access.
#
# This mount is registered LAST on purpose: Starlette matches routes in order,
# so every API route above still wins and only unknown paths fall through to
# the static file handler.
#
# If frontend/dist does not exist yet (you have not run `npm run build`), the
# API simply runs without a UI attached.
_FRONTEND_DIST = config.BASE_DIR / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(_FRONTEND_DIST), html=True),
        name="frontend",
    )
