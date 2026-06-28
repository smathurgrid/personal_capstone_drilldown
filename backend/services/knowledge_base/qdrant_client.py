"""Singleton Qdrant client — one embedded instance per path per process."""

from __future__ import annotations

import logging
import threading

from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_clients: dict[str, QdrantClient] = {}
_collection_cache: dict[str, set[str]] = {}


def get_qdrant_client(qdrant_path: str) -> QdrantClient:
    with _lock:
        if qdrant_path not in _clients:
            logger.info("Opening Qdrant client at %s", qdrant_path)
            _clients[qdrant_path] = QdrantClient(path=qdrant_path)
            _collection_cache[qdrant_path] = set()
        return _clients[qdrant_path]


def collection_exists(qdrant_path: str, collection_name: str) -> bool:
    with _lock:
        cached = _collection_cache.get(qdrant_path)
        if cached is not None and collection_name in cached:
            return True
        client = get_qdrant_client(qdrant_path)
        names = {c.name for c in client.get_collections().collections}
        _collection_cache[qdrant_path] = names
        return collection_name in names


def invalidate_collection_cache(qdrant_path: str) -> None:
    with _lock:
        _collection_cache.pop(qdrant_path, None)


def register_collection(qdrant_path: str, collection_name: str) -> None:
    with _lock:
        _collection_cache.setdefault(qdrant_path, set()).add(collection_name)


def unregister_collection(qdrant_path: str, collection_name: str) -> None:
    with _lock:
        cached = _collection_cache.get(qdrant_path)
        if cached is not None:
            cached.discard(collection_name)
