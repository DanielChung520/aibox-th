import hashlib
import threading
import time
from typing import Any, Optional


class SimpleCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: float) -> None:
        with self._lock:
            self._store[key] = (time.time() + ttl, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_cache: Optional[SimpleCache] = None
_cache_lock = threading.Lock()


def get_cache() -> SimpleCache:
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = SimpleCache()
    return _cache


def generate_cache_key(prefix: str, **kwargs: Any) -> str:
    parts = [prefix]
    for k in sorted(kwargs.keys()):
        parts.append(f"{k}={kwargs[k]}")
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
