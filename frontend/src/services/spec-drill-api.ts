import { API_BASE } from "./api";

const SPEC = `${API_BASE}/api/agent/spec-drill`;

export type SseHandler = (type: string, data: Record<string, unknown>) => void;

async function streamPost(path: string, body: object, onEvent: SseHandler): Promise<void> {
  const res = await fetch(`${SPEC}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
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

export function startSpec(
  body: { topic?: string; parent_image_b64?: string; max_depth?: number; hotspots?: number; predict?: boolean },
  onEvent: SseHandler,
) {
  return streamPost("start", body, onEvent);
}

export function clickSpec(sessionId: string, hotspotId: string, onEvent: SseHandler) {
  return streamPost("click", { session_id: sessionId, hotspot_id: hotspotId }, onEvent);
}

export function clickPointSpec(sessionId: string, x: number, y: number, onEvent: SseHandler) {
  return streamPost("click-point", { session_id: sessionId, x, y }, onEvent);
}

export function endSpec(sessionId: string): Promise<unknown> {
  return fetch(`${SPEC}/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  }).then((r) => r.json()).catch(() => null);
}

export const b64ToDataUrl = (b64: string) => `data:image/png;base64,${b64}`;
