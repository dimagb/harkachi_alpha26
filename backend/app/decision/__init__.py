"""Чистый движок кредитного решения: без БД, HTTP и FastAPI."""

from .config import DEFAULT_CONFIG
from .engine import decide
from .models import DecisionInputs, DecisionResult

__all__ = ["decide", "DecisionInputs", "DecisionResult", "DEFAULT_CONFIG"]
