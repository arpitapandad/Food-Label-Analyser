"""
URE Nutrition Claim Verifier - backend package.

This package exposes a UI-agnostic service layer + REST API. The frontend can
be anything (Streamlit, React, plain HTML) and only needs to talk to the API.

Importing this package guarantees the project root is importable, so that
modules can simply do `from config import ...`.
"""
from __future__ import annotations

import sys
from pathlib import Path

# project root importable regardless of how the package launched.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

__all__ = ["__version__"]
__version__ = "0.1.0"
