import { API_BASE } from "./api";

const SPEC = `${API_BASE}/api/agent/spec-drill`;

export type HotspotStatus = "pending" | "generating" | "ready" | "error" | "chosen";

export interface Hotspot {
  hotspot_id: string;
  depth: number;
  rank: number;
  x: number;
  y: number;
  label: string;
  status: HotspotStatus;
  worker?: string | null;
}

/** "http://mac2.local:11434" -> "mac2.local" for compact display. */
export function shortWorker(url?: string | null): string {
  if (!url) return "local";
  return url.replace(/^https?:\/\//, "").replace(/:\d+$/, "");
}

type SseHandler = (type: string, data: Record<string, unknown>) => void;

export function isAbortError(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

/** POST a spec-drill endpoint and stream its SSE events to `onEvent`. */
async function streamPost(
  path: string,
  body: object,
  onEvent: SseHandler,
  signal?: AbortSignal
) {
  const res = await fetch(`${SPEC}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw new Error(await res.text());

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      let eventType = "message";
      let eventData: Record<string, unknown> | null = null;
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event: ")) eventType = line.slice(7).trim();
        else if (line.startsWith("data: ")) eventData = JSON.parse(line.slice(6).trim());
      }
      if (eventData) onEvent(eventType, eventData);
      boundary = buffer.indexOf("\n\n");
    }
  }
}

export function startSpecDrill(
  body: {
    topic?: string;
    parent_image_b64?: string;
    max_depth?: number;
    hotspots?: number;
    predict?: boolean;
  },
  onEvent: SseHandler,
  signal?: AbortSignal
) {
  return streamPost("start", body, onEvent, signal);
}

export function clickSpecDrill(
  sessionId: string,
  hotspotId: string,
  onEvent: SseHandler,
  signal?: AbortSignal
) {
  return streamPost("click", { session_id: sessionId, hotspot_id: hotspotId }, onEvent, signal);
}

/** Free click at an arbitrary point — generates the child on the fly. */
export function clickPointSpecDrill(
  sessionId: string,
  x: number,
  y: number,
  onEvent: SseHandler,
  signal?: AbortSignal
) {
  return streamPost("click-point", { session_id: sessionId, x, y }, onEvent, signal);
}

export function backSpecDrill(sessionId: string, onEvent: SseHandler, signal?: AbortSignal) {
  return streamPost("back", { session_id: sessionId }, onEvent, signal);
}

export async function endSpecDrill(sessionId: string) {
  const res = await fetch(`${SPEC}/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function b64ToDataUrl(b64: string) {
  return `data:image/png;base64,${b64}`;
}
