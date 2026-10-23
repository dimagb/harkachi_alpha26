"""Чистый движок кредитного решения: без БД, HTTP и FastAPI."""

from .config import DEFAULT_CONFIG
from .engine import decide, eligible_date, validation_rule
from .models import DecisionInputs, DecisionResult

__all__ = [
    "decide",
    "eligible_date",
    "validation_rule",
    "DecisionInputs",
    "DecisionResult",
    "DEFAULT_CONFIG",
]
