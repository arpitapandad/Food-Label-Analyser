"""
OCR wrapper: label image -> list of text lines.

Engine choice (why RapidOCR, not PaddleOCR)
-------------------------------------------
This project runs on Python 3.14. PaddlePaddle publishes no wheels for 3.14,
so `pip install paddleocr` cannot install here at all. RapidOCR
(`rapidocr-onnxruntime`) is used instead because it:

  * ships cp314 wheels and installs cleanly on this interpreter;
  * needs no external system binary (unlike Tesseract);
  * bundles the PP-OCR detection/recognition models inside the wheel, so there
    is no first-run download;
  * runs the same PP-OCR model family as PaddleOCR, exported to ONNX, so
    extraction quality on Indian packaging is comparable.

The engine is imported lazily inside `_get_engine()`, so the rest of the backend
runs fine when OCR is not installed. In that case callers get a typed
`OCRUnavailableError` (surfaced as HTTP 501) and the UI falls back to manual
entry.
"""
from __future__ import annotations

import os
import tempfile
from typing import Callable, List, Optional

import config


class OCRUnavailableError(RuntimeError):
    """Raised when the OCR engine is not installed in the environment."""


class OCRExtractionError(RuntimeError):
    """Raised when OCR runs but the image cannot be read."""


# The engine is expensive to build, so we create it once and reuse it.
_engine_instance = None


def _load_rapidocr():
    """Build and return the RapidOCR engine."""
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on local install
        raise OCRUnavailableError(
            "RapidOCR is not installed. Run 'pip install -r requirements-ocr.txt' "
            "or use the manual-entry endpoint (/verify/json)."
        ) from exc
    return RapidOCR()


def _box_centre(box) -> float:
    """Vertical centre of a detection box (4 points of [x, y])."""
    return sum(point[1] for point in box) / len(box)


def _box_left(box) -> float:
    """Left edge of a detection box - the ordering key within a row."""
    return min(point[0] for point in box)


def _box_height(box) -> float:
    ys = [point[1] for point in box]
    return max(ys) - min(ys)


def _is_usable_box(box) -> bool:
    """True when box is 4 points of at least [x, y]."""
    return (
        isinstance(box, (list, tuple))
        and len(box) == 4
        and all(isinstance(point, (list, tuple)) and len(point) >= 2 for point in box)
    )


def _reconstruct_rows(detections: list) -> List[str]:
    """
    Group detections into visual rows using their bounding boxes.

    RapidOCR does not reliably return text left-to-right, and a two-column
    nutrition table can be emitted as two blocks: every label, then every
    value. The label cell and its value cell then sit far apart in the result,
    so the number falls outside the parser's search window and the nutrient is
    dropped entirely.

    Grouping detections by vertical centre and ordering each group by left edge
    restores human reading order ("Energy 390 kcal"), so a label and its value
    arrive adjacent on one line.
    """
    heights = sorted(_box_height(box) for box, _ in detections)
    median_height = heights[len(heights) // 2] if heights else 10.0
    # Consecutive rows sit roughly one line height apart. Allowing 60% of the
    # median absorbs the small vertical jitter between cells of the SAME row
    # without merging two genuinely separate rows.
    tolerance = max(8.0, median_height * 0.6)

    rows: list = []
    current: list = []
    anchor: Optional[float] = None

    for box, text in sorted(detections, key=lambda item: _box_centre(item[0])):
        centre = _box_centre(box)
        if current and abs(centre - anchor) > tolerance:
            rows.append(current)
            current = []
        if not current:
            anchor = centre
        current.append((_box_left(box), text))

    if current:
        rows.append(current)

    return [" ".join(text for _left, text in sorted(row)) for row in rows]


def _run_rapidocr(engine, image_path: str) -> List[str]:
    """Run RapidOCR and return text lines in visual reading order."""
    result, _elapsed = engine(image_path)
    if not result:
        return []

    detections: list = []
    for entry in result:
        # Each entry is [bounding_box, text, confidence_score].
        try:
            box, text = entry[0], entry[1]
        except (IndexError, TypeError):
            continue
        if text:
            detections.append((box, str(text)))

    # Prefer the layout-aware path, but fall back to engine order if any box is
    # malformed: a surprise result shape must never lose text.
    if detections and all(_is_usable_box(box) for box, _ in detections):
        return _reconstruct_rows(detections)
    return [text for _box, text in detections]


def _load_tesseract():
    """Build and return the pytesseract module (optional alternative engine)."""
    try:
        import pytesseract  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on local install
        raise OCRUnavailableError(
            "pytesseract is not installed. Run 'pip install pytesseract Pillow' "
            "and install the Tesseract application."
        ) from exc
    return pytesseract


def _run_tesseract(engine, image_path: str) -> List[str]:
    """Run Tesseract and split its output into non-empty lines."""
    from PIL import Image  # provided by Pillow

    text = engine.image_to_string(Image.open(image_path))
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


# Phone photos arrive sideways (EXIF rotation) and at 8-12 MP. OCR is both
# faster and more accurate when the pixels are upright and the long edge is
# capped. The browser downscales before uploading, but direct API callers and
# older browsers rely on this safety net.
MAX_OCR_IMAGE_EDGE = 2400


def normalize_image_file(image_path: str) -> Optional[str]:
    """
    Return a path to an upright, size-capped JPEG, or None if the file cannot
    be normalised (unsupported format, Pillow missing, corrupt bytes, ...).

    Callers must delete the returned temp file. On None they should fall back
    to the original path, so a normalisation failure never loses the photo.
    """
    try:
        from PIL import Image, ImageOps  # provided by Pillow
    except ImportError:
        return None

    out_path = None
    try:
        with Image.open(image_path) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode in ("RGBA", "LA") or (
                image.mode == "P" and "transparency" in image.info
            ):
                # Flatten transparency onto the white label stock instead of
                # letting JPEG save the transparent pixels as black.
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.split()[-1])
                image = background
            elif image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            if max(image.size) > MAX_OCR_IMAGE_EDGE:
                image.thumbnail((MAX_OCR_IMAGE_EDGE, MAX_OCR_IMAGE_EDGE), Image.LANCZOS)
            handle, out_path = tempfile.mkstemp(suffix=".jpg")
            os.close(handle)
            image.save(out_path, format="JPEG", quality=88)
        return out_path
    except Exception:
        if out_path:
            try:
                os.unlink(out_path)
            except OSError:
                pass
        return None


# Registry: engine name -> (loader, runner). Adding an engine is one entry.
_ENGINES: dict[str, tuple[Callable[[], object], Callable[[object, str], List[str]]]] = {
    "rapidocr": (_load_rapidocr, _run_rapidocr),
    "tesseract": (_load_tesseract, _run_tesseract),
}


def _get_engine():
    """Return (engine_name, runner) with the engine built once and cached."""
    global _engine_instance

    name = (config.OCR_ENGINE or "rapidocr").strip().lower()
    if name not in _ENGINES:
        raise OCRUnavailableError(
            f"Unknown OCR engine '{name}'. Set OCR_ENGINE to one of: "
            f"{', '.join(sorted(_ENGINES))}."
        )
    loader, runner = _ENGINES[name]

    if _engine_instance is None:
        _engine_instance = loader()
    return name, runner, _engine_instance


def build_engine() -> bool:
    """
    Try to initialise the OCR engine now (used by the /health probe).

    Returns True when OCR is usable, False otherwise. Never raises.
    """
    try:
        _get_engine()
        return True
    except Exception:
        return False


def extract_text_from_image(image_path: str) -> List[str]:
    """
    Run OCR on an image file and return a list of text lines.

    Raises OCRUnavailableError if the engine is missing, or OCRExtractionError
    if the image cannot be processed.
    """
    _name, runner, engine = _get_engine()
    try:
        return runner(engine, image_path)
    except (OCRUnavailableError, OCRExtractionError):
        raise
    except Exception as exc:  # pragma: no cover - depends on local install
        raise OCRExtractionError(f"Failed to read image: {exc}") from exc


def extract_combined_text(image_path: str) -> str:
    """Convenience helper: OCR an image and join the lines into one string."""
    return "\n".join(extract_text_from_image(image_path))
