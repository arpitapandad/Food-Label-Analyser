"""Vercel entrypoint.

Vercel loads a top-level FastAPI instance named ``app``. The application
itself stays in ``backend.main``.
"""
from backend.main import app
