"""
Kết nối Redis dùng chung cho rate limiter và cost guard.
"""
import redis

from app.config import settings


def _make_client():
    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )


r = _make_client()


def redis_healthy() -> bool:
    try:
        return bool(r.ping())
    except Exception:
        return False
