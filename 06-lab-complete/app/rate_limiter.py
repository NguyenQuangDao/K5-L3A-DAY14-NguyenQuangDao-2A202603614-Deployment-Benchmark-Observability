"""
Rate limiting (tiêu chí 7): sliding window 60s, state trong Redis.
"""
import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    now = time.time()
    window_start = now - WINDOW_SECONDS
    redis_key = f"rate:{key}"
    try:
        r.zremrangebyscore(redis_key, 0, window_start)
        if r.zcard(redis_key) >= settings.rate_limit_per_minute:
            retry_after = max(1, int(WINDOW_SECONDS - (now - window_start)))
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )
        r.zadd(redis_key, {f"{now}:{uuid.uuid4()}": now})
        r.expire(redis_key, WINDOW_SECONDS + 1)
    except HTTPException:
        raise
    except Exception:
        pass
