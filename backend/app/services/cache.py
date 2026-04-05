from __future__ import annotations

import json
import logging
import time
from typing import Any

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class _LocalCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at < time.time():
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        self._store[key] = (time.time() + ttl, value)


class CacheService:
    def __init__(self) -> None:
        self._client = None
        self._local = _LocalCache()

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            self._client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            self._client.ping()
        except Exception as exc:  # pragma: no cover
            logger.warning("Redis unavailable, falling back to local cache: %s", exc)
            self._client = False
        return self._client

    def get_json(self, key: str) -> Any | None:
        client = self._get_client()
        if client:
            raw = client.get(key)
            return json.loads(raw) if raw else None
        return self._local.get(key)

    def set_json(self, key: str, value: Any, ttl: int) -> None:
        client = self._get_client()
        if client:
            client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
            return
        self._local.set(key, value, ttl)

    def get_text(self, key: str) -> str | None:
        client = self._get_client()
        if client:
            return client.get(key)
        return self._local.get(key)

    def set_text(self, key: str, value: str, ttl: int) -> None:
        client = self._get_client()
        if client:
            client.set(key, value, ex=ttl)
            return
        self._local.set(key, value, ttl)


cache_service = CacheService()
