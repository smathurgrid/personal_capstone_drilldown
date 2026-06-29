"""Distribute image generation across a pool of worker Macs.

This is the execution substrate for the speculative prefetch fan-out: when the
engine ranks the top-N hotspots and launches N background generations, the pool
spreads those jobs across several Ollama endpoints (one per worker Mac) so they
render in parallel instead of queueing on one box. Jobs go to the least-loaded
healthy worker; failures fail over to another worker with a short cooldown.

Implements the ``ImageGenerator`` protocol, so it is a drop-in replacement for
``OllamaImageGenerator`` / ``RemoteFluxImageGenerator`` at the factory seam.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from backend.services.explainer.image_generator import (
    OllamaImageGenerator,
    ollama_generate_image,
)
from backend.shared.config import settings

logger = logging.getLogger(__name__)


def probe_live_workers(urls: list[str], *, timeout: float = 4.0) -> list[str]:
    """Return the subset of worker URLs whose Ollama answers /api/tags right now.

    Used at startup to decide which workers to actually wire into the pool: a URL
    that responds is used; dead ones (e.g. expired ngrok tunnels) are dropped so we
    don't pay a per-request failover tax on them. If none respond the caller should
    fall back to the main Mac's local Ollama.
    """
    live: list[str] = []
    transport = (
        httpx.HTTPTransport(local_address=settings.BIND_LAN_IP)
        if settings.BIND_LAN_IP
        else None
    )
    with httpx.Client(
        timeout=timeout,
        trust_env=False,
        transport=transport,
        headers={"ngrok-skip-browser-warning": "true"},
    ) as client:
        for url in urls:
            base = url.rstrip("/")
            try:
                resp = client.get(f"{base}/api/tags")
                resp.raise_for_status()
                live.append(base)
                logger.info("[pool] worker reachable: %s", base)
            except httpx.HTTPError as exc:
                logger.warning("[pool] worker UNREACHABLE, dropping: %s (%s)", base, exc)
    return live


class _Worker:
    """One worker Mac's Ollama endpoint plus its live load/health state."""

    def __init__(self, base_url: str, concurrency: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.semaphore = asyncio.Semaphore(max(1, concurrency))
        self.inflight = 0
        self.consecutive_failures = 0
        self.unhealthy_until = 0.0

    def is_available(self, now: float) -> bool:
        return now >= self.unhealthy_until

    def mark_success(self) -> None:
        self.consecutive_failures = 0
        self.unhealthy_until = 0.0

    def mark_failure(self, cooldown: float = 30.0) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= 2:
            self.unhealthy_until = time.monotonic() + cooldown
            logger.warning(
                "image worker %s quarantined for %.0fs after %d failures",
                self.base_url,
                cooldown,
                self.consecutive_failures,
            )


class PooledImageGenerator:
    """Least-loaded, failover image dispatcher across worker Macs."""

    def __init__(
        self,
        base_urls: list[str] | None = None,
        *,
        per_worker_concurrency: int | None = None,
        max_retries: int | None = None,
        model: str | None = None,
        fallback: Any | None = None,
    ) -> None:
        urls = base_urls or settings.IMAGE_OLLAMA_BASES
        concurrency = (
            per_worker_concurrency
            if per_worker_concurrency is not None
            else settings.IMAGE_WORKER_CONCURRENCY
        )
        self._workers = [_Worker(u, concurrency) for u in urls]
        self._model = model or settings.IMAGE_MODEL
        self._max_retries = (
            max_retries if max_retries is not None else settings.IMAGE_GEN_MAX_RETRIES
        )
        # Main-Mac fallback: if every worker is unavailable (down/quarantined),
        # render the hotspot on this Mac's local Ollama instead of failing the
        # whole drill. Latency degrades gracefully to single-Mac speed.
        self._fallback = fallback or OllamaImageGenerator()
        self._select_lock = asyncio.Lock()
        logger.info(
            "PooledImageGenerator: %d worker(s), concurrency=%d each -> %s",
            len(self._workers),
            concurrency,
            [w.base_url for w in self._workers],
        )

    @property
    def total_capacity(self) -> int:
        """Sum of per-worker concurrency — the max images that can render at once."""
        return sum(w.semaphore._value for w in self._workers)  # noqa: SLF001

    async def _pick_worker(self, exclude: set[str]) -> _Worker | None:
        """Choose the least-loaded healthy worker not already tried this job."""
        now = time.monotonic()
        async with self._select_lock:
            # Only HEALTHY (non-quarantined) workers. If all are down/quarantined we
            # return None so the caller falls back to the main Mac immediately, instead
            # of re-hammering dead workers every job. Quarantine auto-expires (see
            # _Worker.is_available), so a worker that comes back online is retried
            # automatically within the cooldown — no restart needed.
            candidates = [
                w for w in self._workers if w.base_url not in exclude and w.is_available(now)
            ]
            if not candidates:
                return None
            worker = min(candidates, key=lambda w: w.inflight)
            worker.inflight += 1
            return worker

    async def generate(
        self,
        prompt: str,
        local_crop_b64: str | None,
        global_b64: str | None,
        *,
        base_url: str | None = None,  # accepted for protocol parity; pool ignores it
    ) -> dict[str, Any]:
        del base_url
        images = [img for img in (local_crop_b64, global_b64) if img] or None
        tried: set[str] = set()
        last_error: Exception | None = None

        for _ in range(self._max_retries + 1):
            worker = await self._pick_worker(tried)
            if worker is None:
                break
            tried.add(worker.base_url)
            # Real-time view of which worker is generating right now. The prompt's
            # first ~50 chars identify the hotspot/component being rendered.
            logger.info(
                "[pool] ▶ %s generating: \"%s…\"  (worker now busy: %d)",
                worker.base_url, (prompt or "")[:50].replace(chr(10), " "), worker.inflight,
            )
            try:
                async with worker.semaphore:
                    image_b64 = await ollama_generate_image(
                        prompt,
                        base_url=worker.base_url,
                        model=self._model,
                        images=images,
                    )
                worker.mark_success()
                logger.info("[pool] ✓ %s finished a job", worker.base_url)
                return {"image_b64": image_b64, "worker": worker.base_url}
            except (httpx.HTTPError, ValueError, asyncio.TimeoutError) as exc:
                worker.mark_failure()
                last_error = exc
                logger.warning(
                    "image gen failed on %s (%s); failing over", worker.base_url, exc
                )
            finally:
                worker.inflight -= 1

        # No worker could serve this job (all down / quarantined / failed over).
        # Fall back to the main Mac's local Ollama so the user still gets an image.
        logger.warning(
            "[pool] all workers unavailable (tried %s: %s) — falling back to main Mac Ollama",
            sorted(tried) or "none",
            last_error,
        )
        result = await self._fallback.generate(
            prompt, local_crop_b64=local_crop_b64, global_b64=global_b64
        )
        return {"image_b64": result["image_b64"], "worker": "main-fallback"}

    async def health_check(self) -> dict[str, bool]:
        """Ping each worker's /api/tags; reset quarantine for those that respond."""
        results: dict[str, bool] = {}

        async def _ping(worker: _Worker) -> None:
            try:
                transport = (
                    httpx.AsyncHTTPTransport(local_address=settings.BIND_LAN_IP)
                    if settings.BIND_LAN_IP
                    else None
                )
                async with httpx.AsyncClient(
                    timeout=5,
                    trust_env=False,
                    transport=transport,
                    headers={"ngrok-skip-browser-warning": "true"},
                ) as client:
                    resp = await client.get(f"{worker.base_url}/api/tags")
                    resp.raise_for_status()
                worker.mark_success()
                results[worker.base_url] = True
            except httpx.HTTPError:
                results[worker.base_url] = False

        await asyncio.gather(*(_ping(w) for w in self._workers))
        return results
