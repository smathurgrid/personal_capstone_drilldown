"""Per-KB BM25 sparse index for hybrid retrieval (exact part numbers, labels)."""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9._/-]*[a-z0-9]|[a-z0-9]", re.IGNORECASE)
_K1 = 1.5
_B = 0.75


def _index_path(kb_dir: Path, kb_id: str) -> Path:
    return kb_dir / kb_id / "sparse_index.json"


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def build_sparse_index(kb_dir: Path, kb_id: str, chunks: list[dict]) -> None:
    """Persist a BM25 index aligned with Qdrant chunk_index payloads."""
    documents = [
        {
            "chunk_index": i,
            "text": c.get("text", ""),
            "page_num": c.get("page_num", 0),
            "content_type": c.get("content_type", "text"),
        }
        for i, c in enumerate(chunks)
    ]
    tokenized = [tokenize(doc["text"]) for doc in documents]
    doc_lens = [len(toks) for toks in tokenized]
    avgdl = sum(doc_lens) / len(doc_lens) if doc_lens else 0.0
    df: Counter[str] = Counter()
    for toks in tokenized:
        for term in set(toks):
            df[term] += 1
    n_docs = len(documents)
    payload = {
        "version": 1,
        "documents": documents,
        "tokenized": tokenized,
        "doc_lens": doc_lens,
        "avgdl": avgdl,
        "df": dict(df),
        "n_docs": n_docs,
    }
    path = _index_path(kb_dir, kb_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    logger.info("Built sparse index for kb_id=%s (%d docs)", kb_id, n_docs)


def delete_sparse_index(kb_dir: Path, kb_id: str) -> None:
    path = _index_path(kb_dir, kb_id)
    if path.exists():
        path.unlink(missing_ok=True)


def _load_index(kb_dir: Path, kb_id: str) -> dict | None:
    path = _index_path(kb_dir, kb_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        logger.warning("Failed to load sparse index kb_id=%s: %s", kb_id, exc)
        return None


def _bm25_score(query_terms: list[str], index: dict, doc_idx: int) -> float:
    if not query_terms:
        return 0.0
    df = index["df"]
    n_docs = index["n_docs"]
    avgdl = index["avgdl"]
    doc_len = index["doc_lens"][doc_idx]
    toks = index["tokenized"][doc_idx]
    tf = Counter(toks)
    score = 0.0
    for term in query_terms:
        if term not in df:
            continue
        freq = tf.get(term, 0)
        idf = math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
        denom = freq + _K1 * (1 - _B + _B * doc_len / max(avgdl, 1.0))
        score += idf * (freq * (_K1 + 1)) / max(denom, 1e-9)
    return score


def search_sparse(
    query: str,
    kb_dir: Path,
    kb_id: str,
    top_k: int = 24,
) -> list[dict]:
    """Return top_k BM25 hits with chunk_index and normalized score."""
    index = _load_index(kb_dir, kb_id)
    if not index or index["n_docs"] == 0:
        return []

    query_terms = tokenize(query)
    if not query_terms:
        return []

    scored: list[tuple[int, float]] = []
    for doc_idx in range(index["n_docs"]):
        raw = _bm25_score(query_terms, index, doc_idx)
        if raw > 0:
            scored.append((doc_idx, raw))

    if not scored:
        return []

    scored.sort(key=lambda x: x[1], reverse=True)
    max_score = scored[0][1] or 1.0
    results = []
    for doc_idx, raw in scored[:top_k]:
        doc = index["documents"][doc_idx]
        results.append(
            {
                "chunk_index": doc["chunk_index"],
                "text": doc["text"],
                "page_num": doc["page_num"],
                "content_type": doc["content_type"],
                "sparse_score": round(raw / max_score, 4),
            }
        )
    return results
