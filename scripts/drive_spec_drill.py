"""Manual end-to-end driver for the speculative drill loop.

Runs a full session against a RUNNING backend: start -> click depth 1 -> click
depth 2 -> complete -> end (flush to SQLite). Prints every SSE event so you can
watch the top-N ranking, the parallel prefetch, and the instant cache-served click.

Usage:
    # 1. start the backend first (see scripts/run_spec_backend.sh), then:
    PYTHONPATH=. python scripts/drive_spec_drill.py
    PYTHONPATH=. python scripts/drive_spec_drill.py --topic "a wristwatch" --depth 3 --hotspots 5
"""

from __future__ import annotations

import argparse
import json

import requests


def sse(resp: requests.Response):
    event = None
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: "):
            yield event, json.loads(line[6:])


def _short(d: dict) -> dict:
    # Hide the heavy base64 image blobs so the console stays readable.
    return {k: v for k, v in d.items() if k not in ("image_b64", "parent_image_b64")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000/api/agent")
    ap.add_argument("--topic", default="a bicycle")
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--hotspots", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=2)
    args = ap.parse_args()

    print(f">>> START topic={args.topic!r} max_depth={args.depth} hotspots={args.hotspots}")
    r = requests.post(
        f"{args.base}/spec-drill/start",
        json={
            "topic": args.topic,
            "max_depth": args.depth,
            "hotspots": args.hotspots,
            "concurrency": args.concurrency,
        },
        stream=True,
        timeout=900,
    )
    sid = None
    next_hotspot = None
    for ev, d in sse(r):
        if ev == "session":
            sid = d["session_id"]
        if ev == "hotspots" and next_hotspot is None:
            next_hotspot = d["regions"][0]["hotspot_id"]  # rank #1
        print(f"   [{ev}] {_short(d)}")

    if not sid:
        print("!! no session_id — is the backend running and ollama up?")
        return

    # Walk down: click rank-#1 at each depth until the loop reports complete.
    depth = 1
    while next_hotspot:
        print(f">>> CLICK depth {depth} hotspot={next_hotspot}")
        r = requests.post(
            f"{args.base}/spec-drill/click",
            json={"session_id": sid, "hotspot_id": next_hotspot},
            stream=True,
            timeout=900,
        )
        next_hotspot = None
        completed = False
        for ev, d in sse(r):
            if ev == "hotspots" and next_hotspot is None:
                next_hotspot = d["regions"][0]["hotspot_id"]
            if ev == "complete":
                completed = True
            print(f"   [{ev}] {_short(d)}")
        depth += 1
        if completed:
            break

    print(">>> END (flush full speculative tree to SQLite)")
    r = requests.post(f"{args.base}/spec-drill/end", json={"session_id": sid}, timeout=120)
    print("   ", r.json())


if __name__ == "__main__":
    main()
