"""Speculative drill engine — predict-and-prefetch the top-5 clickable regions.

Per depth we make ONE VLM call to rank the top-N regions a user is most likely to
click, then immediately fan out background tasks that analyze + generate the child
image for each region BEFORE the user clicks. When the user clicks one of the N
hotspots, its child image is already cached (or the in-flight task is awaited — no
duplicate work), so the click feels instant. The chosen child becomes the new
parent and the loop repeats until max_depth.

Driving the fan-out here with asyncio (rather than through the sequential pi-agent
tool loop) is deliberate: speculative parallelism doesn't fit a Reason→Act→Observe
loop. The LLM is used only for ranking and per-region analysis.

In-flight sessions (and their cached branch images) live in memory; on end_session
the full speculative tree is flushed to SQLite via SessionRepository.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.app.controllers import tools as layer3
from backend.core.factory import get_service_factory
from backend.shared.config import settings

logger = logging.getLogger(__name__)

# Cap concurrent image generations per session (GPU / cost guard).
DEFAULT_PREFETCH_CONCURRENCY = 2
DEFAULT_HOTSPOTS = 5


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class HotspotBranch:
    """One predicted-click region and its speculatively prefetched child image."""

    hotspot_id: str
    depth: int
    rank: int
    x: float
    y: float
    label: str
    status: str = "pending"  # pending | generating | ready | error | chosen
    analysis: str | None = None
    image_prompt: str | None = None
    image_b64: str | None = None
    error: str | None = None
    # Which worker Mac generated this image (set once it's cached on main).
    worker: str | None = None
    task: asyncio.Task | None = field(default=None, repr=False)

    def public(self) -> dict:
        """Lightweight view for SSE/JSON (no image payload, no task)."""
        return {
            "hotspot_id": self.hotspot_id,
            "depth": self.depth,
            "rank": self.rank,
            "x": self.x,
            "y": self.y,
            "label": self.label,
            "status": self.status,
            "worker": self.worker,
        }


@dataclass
class SpeculativeSession:
    session_id: str
    max_depth: int
    hotspots_per_depth: int
    parent_b64: str
    topic: str | None = None
    depth: int = 0
    created_at: str = field(default_factory=_now)
    # Current depth's live branches, keyed by hotspot_id.
    branches: dict[str, HotspotBranch] = field(default_factory=dict)
    # Every branch ever generated, across all depths (for DB flush).
    archive: list[HotspotBranch] = field(default_factory=list)
    semaphore: asyncio.Semaphore | None = None
    # Stack of parent images (one per depth) so the user can go back up the tree.
    parent_history: list[str] = field(default_factory=list)
    # Whether the depth-0 parent had hotspots (topic) or not (upload).
    predict_root: bool = True
    # Cache of each layer's hotspots keyed by the parent's depth, so going Back
    # restores the already-generated hotspots (instant) instead of re-generating.
    hotspot_cache: dict[int, dict[str, "HotspotBranch"]] = field(default_factory=dict)


_sessions: dict[str, SpeculativeSession] = {}


def get_session(session_id: str) -> SpeculativeSession:
    sess = _sessions.get(session_id)
    if sess is None:
        raise KeyError(f"Unknown session_id: {session_id}")
    return sess


# --------------------------------------------------------------------------- #
# Prefetch fan-out
# --------------------------------------------------------------------------- #


async def _prefetch_branch(sess: SpeculativeSession, branch: HotspotBranch) -> None:
    """Analyze the region then generate its child image; fill the branch in place."""
    assert sess.semaphore is not None
    async with sess.semaphore:
        try:
            branch.status = "generating"
            analyze_result = await layer3.handle_analyze_b64(
                {"image_b64": sess.parent_b64, "x": branch.x, "y": branch.y}
            )
            branch.analysis = analyze_result.get("analysis")
            branch.image_prompt = analyze_result.get("image_prompt")

            image_generator = get_service_factory().create_image_generator()
            gen = await layer3.handle_generate(
                {
                    "prompt": branch.image_prompt or "",
                    "local_crop_b64": analyze_result.get("local_crop_b64"),
                    "global_b64": analyze_result.get("global_b64"),
                },
                image_generator,
            )
            # The worker returned the image over HTTP; it now lives in this
            # SpeculativeSession (main Mac RAM) -> a click serves it from here.
            branch.image_b64 = gen["image_b64"]
            branch.worker = gen.get("worker")
            branch.status = "ready"
            kb = len(branch.image_b64) * 3 // 4 // 1024
            logger.info(
                "[main-cache] cached hotspot rank=%d '%s' from %s (%d KB) — click now instant",
                branch.rank,
                branch.label,
                branch.worker or "local",
                kb,
            )
        except asyncio.CancelledError:
            branch.status = "pending"
            raise
        except Exception as exc:  # noqa: BLE001 — surface per-branch, never crash the fan-out
            branch.status = "error"
            branch.error = str(exc)


async def _prefetch_predicted(
    sess: SpeculativeSession,
    branch: HotspotBranch,
    guide_local_b64: str | None,
    guide_global_b64: str | None,
) -> None:
    """Generate a PREDICTED hotspot's image on the worker pool (overlapped flow).

    Uses the prompt the VLM predicted before the child existed, guided by the
    parent's clicked-region crop. No per-hotspot analyze call — the prompt is
    already known — so this fires in parallel with the child generation.
    """
    assert sess.semaphore is not None
    async with sess.semaphore:
        try:
            branch.status = "generating"
            image_generator = get_service_factory().create_image_generator()  # pool -> workers
            gen = await layer3.handle_generate(
                {
                    "prompt": branch.image_prompt or "",
                    "local_crop_b64": guide_local_b64,
                    "global_b64": guide_global_b64,
                },
                image_generator,
            )
            branch.image_b64 = gen["image_b64"]
            branch.worker = gen.get("worker")
            branch.status = "ready"
            kb = len(branch.image_b64) * 3 // 4 // 1024
            logger.info(
                "[main-cache] cached predicted hotspot '%s' from %s (%d KB)",
                branch.label,
                branch.worker or "local",
                kb,
            )
        except asyncio.CancelledError:
            branch.status = "pending"
            raise
        except Exception as exc:  # noqa: BLE001
            branch.status = "error"
            branch.error = str(exc)


async def _rank_and_fan_out(sess: SpeculativeSession) -> list[HotspotBranch]:
    """One VLM call to rank top-N regions, then launch a prefetch task per region."""
    picked = await layer3.handle_pick_top_regions(
        {"image_b64": sess.parent_b64, "n": sess.hotspots_per_depth}
    )
    regions = picked.get("regions", [])

    sess.branches = {}
    branches: list[HotspotBranch] = []
    for region in regions:
        branch = HotspotBranch(
            hotspot_id=uuid.uuid4().hex[:12],
            depth=sess.depth + 1,
            rank=int(region.get("rank", len(branches) + 1)),
            x=float(region.get("x", 0.5)),
            y=float(region.get("y", 0.5)),
            label=str(region.get("label", "region")),
        )
        sess.branches[branch.hotspot_id] = branch
        branches.append(branch)

    # Launch rank #1 first so the most-likely branch warms first; the semaphore
    # bounds how many actually run at once.
    for branch in sorted(branches, key=lambda b: b.rank):
        branch.task = asyncio.create_task(_prefetch_branch(sess, branch))
    # Cache this layer's hotspots so Back can restore them without regenerating.
    sess.hotspot_cache[sess.depth] = sess.branches
    return branches


async def _stream_prefetch(sess: SpeculativeSession, branches: list[HotspotBranch]) -> AsyncIterator[str]:
    """Emit hotspots immediately, then a prefetch_ready event as each branch finishes."""
    yield _sse(
        "hotspots",
        {"depth": sess.depth + 1, "regions": [b.public() for b in branches]},
    )
    pending = {b.task for b in branches if b.task is not None}
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            branch = next(b for b in branches if b.task is task)
            yield _sse("prefetch_ready", branch.public())
    yield _sse(
        "depth_ready",
        {
            "depth": sess.depth + 1,
            "ready": [b.hotspot_id for b in branches if b.status == "ready"],
            "errored": [b.hotspot_id for b in branches if b.status == "error"],
        },
    )


# --------------------------------------------------------------------------- #
# Public entry points (SSE generators)
# --------------------------------------------------------------------------- #


def _effective_concurrency(requested: int | None, hotspots: int) -> int:
    """Size the prefetch fan-out to the image pool so every worker stays busy.

    With a multi-Mac PooledImageGenerator we want as many hotspots rendering at
    once as the pool can handle (its total per-worker capacity), capped at the
    number of hotspots. An explicit ``concurrency`` overrides the auto-sizing.
    """
    capacity = getattr(get_service_factory().create_image_generator(), "total_capacity", None)
    if requested is None:
        base = capacity or DEFAULT_PREFETCH_CONCURRENCY
    else:
        # Honour an explicit request, but never throttle below pool capacity.
        base = max(requested, capacity or requested)
    return max(1, min(base, hotspots))


async def start_session(
    *,
    parent_image_b64: str | None = None,
    topic: str | None = None,
    max_depth: int = 3,
    hotspots: int = DEFAULT_HOTSPOTS,
    concurrency: int | None = None,
    predict: bool = True,
) -> AsyncIterator[str]:
    """Create a session and (optionally) rank + prefetch depth-1 hotspots.

    ``predict=False`` is used for an uploaded first parent: no hotspots are shown
    on the original image; the user free-clicks (red-ring) to start drilling, and
    hotspot prediction kicks in on the generated children from then on.
    """
    session_id = uuid.uuid4().hex
    try:
        if not parent_image_b64:
            if not topic:
                yield _sse("error", {"message": "parent_image_b64 or topic required"})
                return
            # Parent/overview image renders on the MAIN Mac; workers stay free for
            # hotspots. (Hotspot prefetch in _prefetch_branch uses the worker pool.)
            main_image_generator = get_service_factory().create_main_image_generator()
            first = await layer3.handle_generate_from_text(
                {"topic": topic}, main_image_generator
            )
            parent_image_b64 = first["image_b64"]

        sess = SpeculativeSession(
            session_id=session_id,
            max_depth=max_depth,
            hotspots_per_depth=hotspots,
            parent_b64=parent_image_b64,
            topic=topic,
        )
        sess.semaphore = asyncio.Semaphore(_effective_concurrency(concurrency, hotspots))
        sess.parent_history = [parent_image_b64]
        sess.predict_root = predict
        _sessions[session_id] = sess

        yield _sse(
            "session",
            {
                "session_id": session_id,
                "max_depth": max_depth,
                "hotspots": hotspots,
                "parent_image_b64": parent_image_b64,
            },
        )
        if not predict:
            # Uploaded parent: no speculative hotspots — wait for a free click.
            yield _sse("depth_ready", {"depth": sess.depth, "ready": [], "errored": []})
            return

        branches = await _rank_and_fan_out(sess)
        async for event in _stream_prefetch(sess, branches):
            yield event
    except Exception as exc:  # noqa: BLE001
        yield _sse("error", {"message": str(exc), "session_id": session_id})


async def click_point(session_id: str, x: float, y: float) -> AsyncIterator[str]:
    """User clicks an arbitrary point. Dispatches to the overlapped flow (child +
    hotspots in parallel) or the serial flow (child, then hotspots) by config."""
    try:
        sess = get_session(session_id)
    except KeyError as exc:
        yield _sse("error", {"message": str(exc)})
        return
    if settings.SPEC_OVERLAP:
        async for event in _click_point_overlapped(sess, x, y):
            yield event
    else:
        async for event in _click_point_serial(sess, x, y):
            yield event


async def _click_point_serial(
    sess: SpeculativeSession, x: float, y: float
) -> AsyncIterator[str]:
    """Serial flow: generate the child first, THEN rank + prefetch its hotspots."""
    session_id = sess.session_id
    try:
        yield _sse("status", {"phase": "generating_freeclick", "x": x, "y": y})
        analyze = await layer3.handle_analyze_b64(
            {"image_b64": sess.parent_b64, "x": x, "y": y}
        )
        # Free-click "child" images render on the MAIN Mac (like the parent);
        # only prefetched hotspots go to the worker pool.
        image_generator = get_service_factory().create_main_image_generator()
        gen = await layer3.handle_generate(
            {
                "prompt": analyze.get("image_prompt") or "",
                "local_crop_b64": analyze.get("local_crop_b64"),
                "global_b64": analyze.get("global_b64"),
            },
            image_generator,
        )
        child_b64 = gen["image_b64"]
        worker = gen.get("worker")

        # The current depth's speculative branches were alternatives to this point;
        # cancel any still in flight and archive them before moving on.
        for b in sess.branches.values():
            if b.task is not None and not b.task.done():
                b.task.cancel()
        sess.archive.extend(sess.branches.values())
        sess.branches = {}
        sess.depth += 1
        sess.parent_b64 = child_b64
        sess.parent_history.append(child_b64)

        chosen = HotspotBranch(
            hotspot_id=uuid.uuid4().hex[:12],
            depth=sess.depth,
            rank=0,
            x=x,
            y=y,
            label="custom point",
            status="chosen",
            analysis=analyze.get("analysis"),
            image_prompt=analyze.get("image_prompt"),
            image_b64=child_b64,
            worker=worker,
        )
        sess.archive.append(chosen)

        yield _sse(
            "chosen",
            {
                "session_id": session_id,
                "depth": sess.depth,
                "hotspot_id": chosen.hotspot_id,
                "label": chosen.label,
                "image_b64": child_b64,
                "worker": worker,
                "from_cache": False,
            },
        )

        if sess.depth >= sess.max_depth:
            yield _sse("complete", {"session_id": session_id, "final_depth": sess.depth})
            return

        next_branches = await _rank_and_fan_out(sess)
        async for event in _stream_prefetch(sess, next_branches):
            yield event
    except Exception as exc:  # noqa: BLE001
        yield _sse("error", {"message": str(exc), "session_id": session_id})


async def _click_point_overlapped(
    sess: SpeculativeSession, x: float, y: float
) -> AsyncIterator[str]:
    """Overlapped flow (latency win): render the CHILD on the main Mac and the
    predicted HOTSPOTS on the workers IN PARALLEL, then locate the markers on the
    finished child. Hotspots are predicted from the child's prompt before it exists.
    """
    session_id = sess.session_id
    try:
        yield _sse("status", {"phase": "generating_freeclick", "x": x, "y": y})

        # 1. Analyze the clicked region on the current parent (VLM, main Mac).
        analyze = await layer3.handle_analyze_b64(
            {"image_b64": sess.parent_b64, "x": x, "y": y}
        )
        child_prompt = analyze.get("image_prompt") or ""
        guide_local = analyze.get("local_crop_b64")
        guide_global = analyze.get("global_b64")

        will_have_hotspots = (sess.depth + 1) < sess.max_depth
        hotspot_depth = sess.depth + 2  # children-of-the-child

        # 2. Predict the child's hotspots from its PROMPT — before the child exists.
        predicted: list[dict] = []
        if will_have_hotspots:
            pred = await layer3.handle_predict_child_hotspots(
                {
                    "child_prompt": child_prompt,
                    "parent_crop_b64": guide_local,
                    "n": sess.hotspots_per_depth,
                }
            )
            predicted = pred.get("hotspots", [])

        # 3. Fire CHILD (main) and all HOTSPOT images (workers) IN PARALLEL.
        main_gen = get_service_factory().create_main_image_generator()
        child_task = asyncio.create_task(
            layer3.handle_generate(
                {
                    "prompt": child_prompt,
                    "local_crop_b64": guide_local,
                    "global_b64": guide_global,
                },
                main_gen,
            )
        )
        pred_branches: list[HotspotBranch] = []
        for p in predicted:
            branch = HotspotBranch(
                hotspot_id=uuid.uuid4().hex[:12],
                depth=hotspot_depth,
                rank=int(p.get("rank", len(pred_branches) + 1)),
                x=0.5,
                y=0.5,
                label=str(p.get("label", "region")),
                image_prompt=str(p.get("gen_prompt", "")),
            )
            branch.task = asyncio.create_task(
                _prefetch_predicted(sess, branch, guide_local, guide_global)
            )
            pred_branches.append(branch)

        # 4. Wait for the child, promote it to the new parent.
        child_gen = await child_task
        child_b64 = child_gen["image_b64"]
        worker = child_gen.get("worker")

        # Keep the previous layer's hotspots (cached for Back) — don't cancel them.
        sess.archive.extend(sess.branches.values())
        sess.branches = {}
        sess.depth += 1
        sess.parent_b64 = child_b64
        sess.parent_history.append(child_b64)

        chosen = HotspotBranch(
            hotspot_id=uuid.uuid4().hex[:12],
            depth=sess.depth,
            rank=0,
            x=x,
            y=y,
            label="custom point",
            status="chosen",
            analysis=analyze.get("analysis"),
            image_prompt=child_prompt,
            image_b64=child_b64,
            worker=worker,
        )
        sess.archive.append(chosen)
        yield _sse(
            "chosen",
            {
                "session_id": session_id,
                "depth": sess.depth,
                "hotspot_id": chosen.hotspot_id,
                "label": chosen.label,
                "image_b64": child_b64,
                "worker": worker,
                "from_cache": False,
            },
        )

        # Terminal child or nothing predicted -> stop here.
        if sess.depth >= sess.max_depth or not pred_branches:
            for b in pred_branches:
                if b.task is not None and not b.task.done():
                    b.task.cancel()
            if sess.depth >= sess.max_depth:
                yield _sse("complete", {"session_id": session_id, "final_depth": sess.depth})
            else:
                yield _sse("depth_ready", {"depth": sess.depth, "ready": [], "errored": []})
            return

        # 5. Locate the predicted labels on the REAL child (fast — coordinates only).
        located = await layer3.handle_locate_hotspots(
            {"image_b64": child_b64, "labels": [b.label for b in pred_branches]}
        )
        positions = located.get("located", {})

        # 6. Keep hotspots Flux actually drew (give them real positions); drop the
        #    rest (their pre-rendered image is discarded).
        kept: list[HotspotBranch] = []
        for b in pred_branches:
            pos = positions.get(b.label)
            if pos:
                b.x, b.y = float(pos[0]), float(pos[1])
                sess.branches[b.hotspot_id] = b
                kept.append(b)
            elif b.task is not None and not b.task.done():
                b.task.cancel()

        if not kept:
            yield _sse("depth_ready", {"depth": sess.depth, "ready": [], "errored": []})
            return

        # Cache this layer's hotspots so Back restores them instantly.
        sess.hotspot_cache[sess.depth] = sess.branches
        # Their images are already generating/done (started in step 3) — stream
        # readiness as each finishes.
        async for event in _stream_prefetch(sess, kept):
            yield event
    except Exception as exc:  # noqa: BLE001
        yield _sse("error", {"message": str(exc), "session_id": session_id})


async def go_back(session_id: str) -> AsyncIterator[str]:
    """Return to the previous depth's parent and re-offer its hotspots.

    Lets the user back out of a drill and pick a different region. The previous
    layer's hotspots are restored FROM CACHE (already generated) so the user can
    click another one with zero wait; only if there's no cache do we re-rank.
    """
    try:
        sess = get_session(session_id)
    except KeyError as exc:
        yield _sse("error", {"message": str(exc)})
        return

    if len(sess.parent_history) <= 1:
        yield _sse("error", {"message": "Already at the first layer"})
        return

    try:
        # Keep the current depth's hotspots cached too — don't cancel them.
        sess.parent_history.pop()
        sess.parent_b64 = sess.parent_history[-1]
        sess.depth -= 1

        yield _sse(
            "back",
            {
                "session_id": session_id,
                "depth": sess.depth,
                "image_b64": sess.parent_b64,
            },
        )

        # Restore this layer's hotspots from cache (instant) if we have them.
        cached = sess.hotspot_cache.get(sess.depth)
        if cached and any(b.image_b64 for b in cached.values()):
            sess.branches = cached
            for b in cached.values():
                if b.image_b64:  # a previously-chosen one is clickable again
                    b.status = "ready"
            async for event in _stream_prefetch(sess, list(cached.values())):
                yield event
            return

        # Root upload had no hotspots — keep it that way (free-click only).
        if sess.depth == 0 and not sess.predict_root:
            sess.branches = {}
            yield _sse("depth_ready", {"depth": sess.depth, "ready": [], "errored": []})
            return

        # No cache (e.g. first visit) -> regenerate.
        sess.branches = {}
        branches = await _rank_and_fan_out(sess)
        async for event in _stream_prefetch(sess, branches):
            yield event
    except Exception as exc:  # noqa: BLE001
        yield _sse("error", {"message": str(exc), "session_id": session_id})


async def click(session_id: str, hotspot_id: str) -> AsyncIterator[str]:
    """User clicks a hotspot: serve its (cached/in-flight) child, then prefetch next depth."""
    try:
        sess = get_session(session_id)
    except KeyError as exc:
        yield _sse("error", {"message": str(exc)})
        return

    branch = sess.branches.get(hotspot_id)
    if branch is None:
        yield _sse("error", {"message": f"Unknown hotspot_id: {hotspot_id}"})
        return

    try:
        # Cache hit -> returns immediately; in-flight -> awaits the SAME task
        # (no duplicate generation). Cache and "almost-hit" share this path.
        if branch.task is not None:
            yield _sse("status", {"phase": "awaiting_branch", "hotspot_id": hotspot_id})
            await branch.task

        if branch.status != "ready" or not branch.image_b64:
            yield _sse(
                "error",
                {"message": f"Branch failed to generate: {branch.error}", "hotspot_id": hotspot_id},
            )
            return

        # Promote the chosen branch. KEEP the siblings (cached for Back) — they
        # finish generating and stay in hotspot_cache[parent depth], so coming
        # back lets the user click another one instantly.
        branch.status = "chosen"
        sess.archive.extend(sess.branches.values())
        sess.depth += 1
        sess.parent_b64 = branch.image_b64
        sess.parent_history.append(branch.image_b64)

        yield _sse(
            "chosen",
            {
                "session_id": session_id,
                "depth": sess.depth,
                "hotspot_id": hotspot_id,
                "label": branch.label,
                "image_b64": branch.image_b64,
                "worker": branch.worker,
                "from_cache": True,
            },
        )

        if sess.depth >= sess.max_depth:
            sess.branches = {}
            yield _sse(
                "complete",
                {"session_id": session_id, "final_depth": sess.depth},
            )
            return

        # Loop: rank + prefetch the next depth's hotspots on the new parent.
        next_branches = await _rank_and_fan_out(sess)
        async for event in _stream_prefetch(sess, next_branches):
            yield event
    except Exception as exc:  # noqa: BLE001
        yield _sse("error", {"message": str(exc), "session_id": session_id})


async def end_session(session_id: str) -> dict:
    """Cancel any in-flight prefetch, flush the full tree to SQLite, free memory."""
    sess = _sessions.pop(session_id, None)
    if sess is None:
        raise KeyError(f"Unknown session_id: {session_id}")

    # Archive whatever the current depth still holds, then stop in-flight work.
    sess.archive.extend(sess.branches.values())
    for branch in sess.archive:
        if branch.task is not None and not branch.task.done():
            branch.task.cancel()
    pending = [b.task for b in sess.archive if b.task is not None and not b.task.done()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    payload = {
        "session_id": sess.session_id,
        "topic": sess.topic,
        "max_depth": sess.max_depth,
        "final_depth": sess.depth,
        "created_at": sess.created_at,
        "ended_at": _now(),
        "branches": [
            {
                "depth": b.depth,
                "hotspot_id": b.hotspot_id,
                "rank": b.rank,
                "x": b.x,
                "y": b.y,
                "label": b.label,
                "chosen": b.status == "chosen",
                "status": b.status,
                "worker": b.worker,
                "analysis": b.analysis,
                "image_prompt": b.image_prompt,
                "image_b64": b.image_b64,
            }
            for b in sess.archive
        ],
    }
    store = get_service_factory().create_drill_session_store()
    await asyncio.to_thread(store.save_session, payload)
    return {
        "session_id": sess.session_id,
        "persisted_branches": len(payload["branches"]),
        "final_depth": sess.depth,
    }
