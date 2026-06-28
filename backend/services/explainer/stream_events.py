"""Server-sent event formatting for explainer page streaming."""

import json


def format_sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
