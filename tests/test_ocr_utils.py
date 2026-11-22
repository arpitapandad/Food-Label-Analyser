"""
Tests for the OCR wrapper.

These deliberately do NOT require RapidOCR to be installed: they exercise the
engine-selection logic and the result-parsing shape with fakes, so the suite
stays green on a machine without OCR dependencies.
"""
import pytest

from backend import ocr_utils


class _FakeRapidOCR:
    """Mimics RapidOCR's `(result, elapsed)` return shape."""

    def __call__(self, image_path):
        return (
            [
                [[[0, 0], [10, 0], [10, 10], [0, 10]], "Nutrition Information", 0.99],
                [[[0, 12], [10, 12], [10, 22], [0, 22]], "Protein 11.5 g", 0.98],
            ],
            [0.1, 0.2],
        )


class _EmptyRapidOCR:
    """RapidOCR returns (None, ...) when it finds no text."""

    def __call__(self, image_path):
        return None, [0.1]


def test_rapidocr_result_is_flattened_to_text_lines():
    lines = ocr_utils._run_rapidocr(_FakeRapidOCR(), "ignored.jpg")
    assert lines == ["Nutrition Information", "Protein 11.5 g"]


def test_rapidocr_no_text_returns_empty_list():
    assert ocr_utils._run_rapidocr(_EmptyRapidOCR(), "ignored.jpg") == []


def test_rapidocr_skips_malformed_entries():
    """A bad entry must not crash the whole extraction."""

    class _PartlyBroken:
        def __call__(self, image_path):
            return ([["not-an-entry"], [[[0, 0]], "Protein 5 g", 0.9]], [0.1])

    assert ocr_utils._run_rapidocr(_PartlyBroken(), "x.jpg") == ["Protein 5 g"]


def test_unknown_engine_raises_clear_error(monkeypatch):
    monkeypatch.setattr(ocr_utils.config, "OCR_ENGINE", "does-not-exist")
    monkeypatch.setattr(ocr_utils, "_engine_instance", None)
    with pytest.raises(ocr_utils.OCRUnavailableError, match="Unknown OCR engine"):
        ocr_utils.extract_text_from_image("x.jpg")


def test_missing_engine_raises_unavailable(monkeypatch):
    """Missing dependency surfaces as OCRUnavailableError (=> HTTP 501)."""
    monkeypatch.setattr(ocr_utils, "_engine_instance", None)
    monkeypatch.setattr(ocr_utils.config, "OCR_ENGINE", "rapidocr")

    def _missing():
        raise ocr_utils.OCRUnavailableError("RapidOCR is not installed.")

    monkeypatch.setitem(
        ocr_utils._ENGINES, "rapidocr", (_missing, ocr_utils._run_rapidocr)
    )
    with pytest.raises(ocr_utils.OCRUnavailableError):
        ocr_utils.extract_text_from_image("x.jpg")


def test_engine_failure_becomes_extraction_error(monkeypatch):
    """An engine that throws mid-image becomes OCRExtractionError (=> HTTP 422)."""
    monkeypatch.setattr(ocr_utils, "_engine_instance", None)
    monkeypatch.setattr(ocr_utils.config, "OCR_ENGINE", "rapidocr")

    def _broken_runner(engine, image_path):
        raise RuntimeError("corrupt image bytes")

    monkeypatch.setitem(ocr_utils._ENGINES, "rapidocr", (lambda: object(), _broken_runner))
    with pytest.raises(ocr_utils.OCRExtractionError):
        ocr_utils.extract_text_from_image("x.jpg")


def test_build_engine_never_raises_and_returns_bool():
    """The /health probe must be safe whether or not OCR is installed."""
    assert isinstance(ocr_utils.build_engine(), bool)


# --- layout reconstruction -------------------------------------------------
# RapidOCR's detections are not reliably ordered left-to-right, and a
# two-column table can arrive as two blocks: every label, then every value.
# Without reconstruction the label and its number land far apart, the parser's
# 25-character window misses the number, and the nutrient is dropped silently.

def test_reconstructs_two_column_layout_left_to_right():
    class _TwoColumn:
        def __call__(self, image_path):
            return (
                [
                    [[[10, 0], [120, 0], [120, 20], [10, 20]], "Energy", 0.9],
                    [[[600, 0], [720, 0], [720, 20], [600, 20]], "390 kcal", 0.95],
                    [[[10, 40], [140, 40], [140, 60], [10, 60]], "Protein", 0.9],
                    [[[600, 40], [740, 40], [740, 60], [600, 60]], "11.5 g", 0.95],
                ],
                [0.1],
            )

    assert ocr_utils._run_rapidocr(_TwoColumn(), "x.jpg") == [
        "Energy 390 kcal",
        "Protein 11.5 g",
    ]


def test_reconstructs_values_emitted_after_all_labels():
    """The exact failure being fixed: all labels, then all values."""

    class _ColumnBlocks:
        def __call__(self, image_path):
            return (
                [
                    [[[10, 0], [120, 0], [120, 20], [10, 20]], "Added Sugars", 0.9],
                    [[[10, 40], [160, 40], [160, 60], [10, 60]], "Total Fat", 0.9],
                    [[[600, 40], [700, 40], [700, 60], [600, 60]], "6.5 g", 0.95],
                    [[[600, 0], [700, 0], [700, 20], [600, 20]], "0 g", 0.95],
                ],
                [0.1],
            )

    assert ocr_utils._run_rapidocr(_ColumnBlocks(), "x.jpg") == [
        "Added Sugars 0 g",
        "Total Fat 6.5 g",
    ]


def test_separate_rows_are_not_merged():
    """Rows a line-height apart must stay distinct."""

    class _Stacked:
        def __call__(self, image_path):
            return (
                [
                    [[[10, 0], [120, 0], [120, 40], [10, 40]], "Protein", 0.9],
                    [[[600, 0], [700, 0], [700, 40], [600, 40]], "11.5 g", 0.9],
                    [[[10, 80], [120, 80], [120, 120], [10, 120]], "Sodium", 0.9],
                    [[[600, 80], [700, 80], [700, 120], [600, 120]], "35 mg", 0.9],
                ],
                [0.1],
            )

    assert ocr_utils._run_rapidocr(_Stacked(), "x.jpg") == [
        "Protein 11.5 g",
        "Sodium 35 mg",
    ]


def test_degenerate_boxes_fall_back_to_engine_order():
    """A present-but-unusable box must not cost us the text."""

    class _DegenerateBoxes:
        def __call__(self, image_path):
            return (
                [
                    [[[0, 0]], "Protein 5 g", 0.9],
                    [[[0, 8]], "Sodium 35 mg", 0.9],
                ],
                [0.1],
            )

    assert ocr_utils._run_rapidocr(_DegenerateBoxes(), "x.jpg") == [
        "Protein 5 g",
        "Sodium 35 mg",
    ]
