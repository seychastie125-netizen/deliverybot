import time
from typing import Any


class SimpleCache:
    def __init__(self, ttl: int = 300):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Any | None:
        if key in self._cache:
            value, expire_at = self._cache[key]
            if time.time() < expire_at:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = None):
        expire_at = time.time() + (ttl or self._ttl)
        self._cache[key] = (value, expire_at)

    def invalidate(self, key: str = None):
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()


settings_cache = SimpleCache(ttl=300)