import time
from typing import Any, Optional

class CacheService:
    def __init__(self):
        self._cache = {}

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache."""
        try:
            if key in self._cache:
                item = self._cache[key]
                if time.time() < item["expires_at"]:
                    return item["value"]
                else:
                    del self._cache[key]
            return None
        except Exception as e:
            print(f"Cache GET error for {key}: {e}")
            return None

    async def set(self, key: str, value: Any, expire_seconds: int = 3600):
        """Store a value in the cache with an expiration."""
        try:
            self._cache[key] = {
                "value": value,
                "expires_at": time.time() + expire_seconds
            }
        except Exception as e:
            print(f"Cache SET error for {key}: {e}")

cache = CacheService()
