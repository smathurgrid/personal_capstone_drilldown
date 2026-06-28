"""Small Redis cache wrapper with graceful local fallback."""

import json
import logging
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from backend.shared.config import settings

logger = logging.getLogger(__name__)

_client: Redis | None = None
_available: bool | None = None


def get_redis_client() -> Redis | None:
    global _client, _available
    if not settings.REDIS_URL:
        return None
    if _available is False:
        return None
    if _client is None:
        try:
            _client = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            _client.ping()
            _available = True
        except RedisError as exc:
            _available = False
            logger.warning("Redis unavailable at %s: %s", settings.REDIS_URL, exc)
            return None
    return _client


def cache_get_json(key: str) -> dict[str, Any] | None:
    client = get_redis_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
    except RedisError as exc:
        logger.debug("Redis get failed for %s: %s", key, exc)
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def cache_set_json(
    key: str,
    value: dict[str, Any],
    ttl_seconds: int | None = None,
) -> None:
    client = get_redis_client()
    if client is None:
        return
    try:
        client.setex(
            key,
            ttl_seconds or settings.REDIS_CACHE_TTL_SECONDS,
            json.dumps(value),
        )
    except RedisError as exc:
        logger.debug("Redis set failed for %s: %s", key, exc)
