"""
Cache Layer — Redis, TTL per tool type.
Cache key = (tool_name, sha256(params)).
Không cache toàn bộ LLM response — cache riêng từng tool call.
"""
import hashlib
import json
import os
from functools import wraps
from typing import Any, Callable

import redis
import structlog

log = structlog.get_logger()

# TTL (giây) cho từng tool — data ổn định hơn thì TTL dài hơn
TOOL_TTL: dict[str, int] = {
    "get_price_history":       300,   # 5 phút
    "get_supplier_comparison": 600,   # 10 phút
    "get_price_volatility":    300,   # 5 phút
    "get_supplier_score":      1800,  # 30 phút — delivery history ít thay đổi
    "get_budget_compliance":   60,    # 1 phút — CEO approval có thể thay đổi nhanh
    "get_market_benchmark":    1800,  # 30 phút — benchmark ổn định
    "get_salary_benchmark":    3600,  # 1 giờ
    "get_retention_risk":      3600,
    "get_headcount_trend":     3600,
    "get_reorder_suggestion":  120,   # 2 phút — tồn kho thay đổi nhanh
    "get_demand_forecast":     1800,
    "get_lead_time_risk":      600,
    "get_margin_analysis":     300,
    "get_discount_benchmark":  600,
    "get_cashflow_forecast":   1800,
}
DEFAULT_TTL = 300


def _make_cache_key(tool_name: str, params: dict) -> str:
    params_hash = hashlib.sha256(
        json.dumps(params, sort_keys=True, default=str).encode()
    ).hexdigest()[:12]
    return f"nfc_ai:{tool_name}:{params_hash}"


class CacheLayer:
    def __init__(self, redis_url: str | None = None):
        url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/1")
        try:
            self._redis = redis.from_url(url, decode_responses=True)
            self._redis.ping()
            self._enabled = True
            log.info("cache_ready", url=url)
        except Exception as e:
            log.warning("cache_disabled", reason=str(e))
            self._enabled = False

    def get(self, tool_name: str, params: dict) -> Any | None:
        if not self._enabled:
            return None
        key = _make_cache_key(tool_name, params)
        try:
            raw = self._redis.get(key)
            if raw:
                log.info("cache_hit", tool=tool_name, key=key)
                return json.loads(raw)
        except Exception as e:
            log.warning("cache_get_error", error=str(e))
        return None

    def set(self, tool_name: str, params: dict, value: Any) -> None:
        if not self._enabled:
            return
        key = _make_cache_key(tool_name, params)
        ttl = TOOL_TTL.get(tool_name, DEFAULT_TTL)
        try:
            self._redis.setex(key, ttl, json.dumps(value, default=str))
            log.info("cache_set", tool=tool_name, ttl=ttl)
        except Exception as e:
            log.warning("cache_set_error", error=str(e))

    def invalidate(self, pattern: str = "nfc_ai:*") -> int:
        """Xóa cache theo pattern — dùng khi data thay đổi."""
        if not self._enabled:
            return 0
        keys = self._redis.keys(pattern)
        if keys:
            return self._redis.delete(*keys)
        return 0

    @property
    def enabled(self) -> bool:
        return self._enabled


# Singleton
_cache: CacheLayer | None = None


def get_cache() -> CacheLayer:
    global _cache
    if _cache is None:
        _cache = CacheLayer()
    return _cache


def cached_tool(fn: Callable) -> Callable:
    """Wrap tool function với cache. Inject sau @tool decorator."""
    @wraps(fn)
    def wrapper(q, **kwargs):
        cache = get_cache()
        cached = cache.get(fn.__tool_name__, kwargs)
        if cached is not None:
            return cached
        result = fn(q, **kwargs)
        if result:
            cache.set(fn.__tool_name__, kwargs, result)
        return result
    wrapper.__tool__ = True
    wrapper.__tool_name__ = fn.__tool_name__
    return wrapper
