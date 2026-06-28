"""Mac 2 Flux worker — dedicated image-generation server (distributed inference).

Runs on the second Mac. Mac 1 (the orchestrator) POSTs gen-prompts here; this server
generates the child image on its own GPU and returns the JPEG/PNG bytes (base64) back
over the Thunderbolt link. Because there is exactly one GPU, generation is serialized
through a single ranked job queue: requests carry a priority (the hotspot rank), and the
worker always picks the lowest-rank (most-likely-clicked) job next. Requests can be
cancelled by job_id or session_id so abandoned drills stop wasting GPU time.

Run with:  scripts/run_flux_worker.sh   (uvicorn on :9000)

This server only needs Ollama + the Flux model on Mac 2 — it does not import the heavy
orchestrator stack, so it stays light and independent.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import requests
from fastapi import FastAPI
from pydantic import BaseModel

logger = logging.getLogger("flux_worker")

OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434").rstrip("/")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "x/flux2-klein:4b-bf16")
GEN_TIMEOUT = int(os.getenv("FLUX_TIMEOUT", "300"))


class GenerateRequest(BaseModel):
    prompt: str
    local_crop_b64: str | None = None
    global_b64: str | None = None
    job_id: str | None = None
    session_id: str | None = None
    priority: int = 100  # lower = generated sooner (hotspot rank)


@dataclass(order=True)
class _Job:
    priority: int
    seq: int  # FIFO tie-breaker; also keeps the dataclass sortable
    request: GenerateRequest = field(compare=False)
    future: asyncio.Future = field(compare=False)


class _FluxQueue:
    """Single-GPU ranked job queue: one worker drains a PriorityQueue in rank order."""

    def __init__(self) -> None:
        self._pq: asyncio.PriorityQueue[_Job] = asyncio.PriorityQueue()
        self._seq = itertools.count()
        self._cancelled_jobs: set[str] = set()
        self._cancelled_sessions: set[str] = set()
        self._worker: asyncio.Task | None = None

    def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None

    def submit(self, req: GenerateRequest) -> asyncio.Future:
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        job = _Job(priority=req.priority, seq=next(self._seq), request=req, future=future)
        self._pq.put_nowait(job)
        return future

    def cancel(self, *, job_id: str | None = None, session_id: str | None = None) -> None:
        if job_id:
            self._cancelled_jobs.add(job_id)
        if session_id:
            self._cancelled_sessions.add(session_id)

    def _is_cancelled(self, req: GenerateRequest) -> bool:
        return (req.job_id and req.job_id in self._cancelled_jobs) or (
            req.session_id and req.session_id in self._cancelled_sessions
        )

    async def _run(self) -> None:
        while True:
            job = await self._pq.get()
            req = job.request
            if job.future.cancelled():
                continue
            if self._is_cancelled(req):
                if not job.future.done():
                    job.future.set_exception(RuntimeError("cancelled"))
                continue
            try:
                result = await asyncio.to_thread(_generate_via_ollama, req)
                if not job.future.done():
                    job.future.set_result(result)
            except Exception as exc:  # noqa: BLE001 — surface per-job, keep worker alive
                if not job.future.done():
                    job.future.set_exception(exc)


def _generate_via_ollama(req: GenerateRequest) -> dict[str, Any]:
    """Call the local Ollama Flux model and return {"image_b64": ...}."""
    payload: dict[str, Any] = {"model": IMAGE_MODEL, "prompt": req.prompt, "stream": False}
    images = [img for img in (req.local_crop_b64, req.global_b64) if img]
    if images:
        payload["images"] = images

    resp = requests.post(f"{OLLAMA_BASE}/api/generate", json=payload, timeout=GEN_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    image_b64 = data.get("image") or (data.get("images") or [None])[0]
    if not image_b64:
        preview = str(data.get("response", ""))[:200]
        raise ValueError(f"Flux returned no image. Preview: {preview}")
    return {"image_b64": image_b64}


_queue = _FluxQueue()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _queue.start()
    logger.info("Flux worker ready — model=%s ollama=%s", IMAGE_MODEL, OLLAMA_BASE)
    yield
    await _queue.stop()


app = FastAPI(title="Flux2-Klein worker", lifespan=lifespan)


@app.post("/generate")
async def generate(req: GenerateRequest) -> dict[str, Any]:
    future = _queue.submit(req)
    return await future


@app.post("/cancel")
async def cancel(body: dict) -> dict[str, str]:
    _queue.cancel(job_id=body.get("job_id"), session_id=body.get("session_id"))
    return {"status": "cancelled"}


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "model": IMAGE_MODEL, "ollama": OLLAMA_BASE}
