import type { ExplainerPage, GroundingMode, VisionModelKey } from "@shared/types";

import { API_BASE, resolveUrl } from "./api";

const VISION = `${API_BASE}/api/explainer/vision`;
const GENERATE = `${API_BASE}/api/explainer/generate`;

export async function fetchVisionHealth(): Promise<{
  sam2_available?: boolean;
  default_grounding_mode?: GroundingMode;
}> {
  const res = await fetch(`${VISION}/health`);
  if (!res.ok) throw new Error("Vision health failed");
  const data = await res.json();
  return data.checks ?? {};
}

export async function uploadExplainerImage(file: File): Promise<ExplainerPage> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${VISION}/upload`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return { ...data, imageUrl: resolveUrl(data.imageUrl) };
}

export async function analyzeExplainerPage(
  pageId: string,
  visionModel: VisionModelKey = "qwen3.5"
): Promise<{
  metadata: ExplainerPage["metadata"];
  rawJson: string;
}> {
  const res = await fetch(`${VISION}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pageId, visionModel }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function generateFromTopic(topic: string) {
  const res = await fetch(`${GENERATE}/generate-from-text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<{ image_b64: string; image_prompt: string }>;
}

export async function streamExplainerPage(
  params: {
    query?: string;
    parentId?: string;
    x?: number;
    y?: number;
    customTopic?: string;
    groundingMode?: string;
    visionModel?: string;
  },
  onEvent: (type: string, data: Record<string, unknown>) => void
) {
  const res = await fetch(`${VISION}/stream-page`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...params,
      visionModel: params.visionModel ?? "qwen3.5",
      groundingMode: params.groundingMode ?? "red_ring",
    }),
  });
  if (!res.ok) throw new Error("Failed to start stream");

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

export function b64ToDataUrl(b64: string) {
  return `data:image/png;base64,${b64}`;
}

export type { ExplainerPage, GroundingMode, VisionModelKey };
