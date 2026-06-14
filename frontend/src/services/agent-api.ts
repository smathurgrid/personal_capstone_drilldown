import { API_BASE, resolveUrl } from "./api";

const AGENT = `${API_BASE}/api/agent`;
const TOOLS = `${API_BASE}/api`;

export type AutoDrillEvent = {
  type: string;
  data: Record<string, unknown>;
};

/** Layer 3 per-click analyze (FormData — human path). */
export async function analyzeAtClick(
  imageBlob: Blob,
  x: number,
  y: number,
  radius = 80
): Promise<{
  analysis: string;
  image_prompt: string;
  global_b64: string;
  local_crop_b64: string;
}> {
  const fd = new FormData();
  fd.append("image", imageBlob, "frame.jpg");
  fd.append("x", String(x));
  fd.append("y", String(y));
  fd.append("radius", String(radius));
  const res = await fetch(`${TOOLS}/analyze`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** Layer 3 generate (JSON — same contract as explainer generate). */
export async function generateDrillImage(body: {
  prompt: string;
  local_crop_b64: string;
  global_b64?: string;
}) {
  const res = await fetch(`${TOOLS}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<{ image_b64: string }>;
}

/** F7 auto-drill SSE — deterministic or pi-agent mode. */
export async function streamAutoDrill(
  params: {
    parent_id?: string;
    parent_image_b64?: string;
    topic?: string;
    max_depth?: number;
    mode?: "deterministic" | "pi-agent";
    vision_model?: string;
    grounding_mode?: string;
  },
  onEvent: (type: string, data: Record<string, unknown>) => void
) {
  const res = await fetch(`${AGENT}/auto-drill`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      max_depth: params.max_depth ?? 3,
      mode: params.mode ?? "deterministic",
      vision_model: params.vision_model ?? "qwen3.5",
      grounding_mode: params.grounding_mode ?? "red_ring",
      ...params,
    }),
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
        else if (line.startsWith("data: "))
          eventData = JSON.parse(line.slice(6).trim());
      }
      if (eventData) {
        if (typeof eventData.imageUrl === "string") {
          eventData.imageUrl = resolveUrl(eventData.imageUrl);
        }
        onEvent(eventType, eventData);
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}

export async function fetchAgentHealth() {
  const res = await fetch(`${AGENT}/health`);
  if (!res.ok) throw new Error("Agent health failed");
  return res.json();
}
