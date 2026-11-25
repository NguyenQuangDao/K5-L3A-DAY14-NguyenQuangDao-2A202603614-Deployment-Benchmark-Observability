"""
Cost guard (tiêu chí 8): cộng dồn chi phí vào Redis, vượt budget -> 402.
"""
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

BUDGET_KEY = "cost:daily"


def _current_cost() -> float:
    try:
        return float(r.get(BUDGET_KEY) or 0)
    except Exception:
        return 0.0


def check_budget() -> None:
    if _current_cost() >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Budget exceeded")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    cost = (input_tokens / 1000) * PRICE_INPUT_PER_1K + (output_tokens / 1000) * PRICE_OUTPUT_PER_1K
    try:
        r.incrbyfloat(BUDGET_KEY, cost)
        r.expire(BUDGET_KEY, 86400)
    except Exception:
        pass
    return cost
