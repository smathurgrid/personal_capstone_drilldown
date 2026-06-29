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

export function uploadExplainerImage(file: File): Promise<ExplainerPage> {
  return new Promise((resolve, reject) => {
    const fd = new FormData();
    fd.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${VISION}/upload`, true);
    
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText);
          resolve({ ...data, imageUrl: resolveUrl(data.imageUrl) });
        } catch (err) {
          reject(new Error("Failed to parse upload response JSON"));
        }
      } else {
        reject(new Error(xhr.responseText || `Upload failed with status ${xhr.status}`));
      }
    };

    xhr.onerror = () => {
      reject(new Error("Network error during upload"));
    };

    xhr.send(fd);
  });
}

export type ScanMode = "global" | "focus";

export async function analyzeExplainerPage(
  pageId: string,
  visionModel: VisionModelKey = "qwen3.5",
  scanMode: ScanMode = "global",
  depth?: number
): Promise<{
  metadata: ExplainerPage["metadata"];
  rawJson: string;
}> {
  const res = await fetch(`${VISION}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pageId, visionModel, scanMode, depth }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchExplainerPage(pageId: string): Promise<ExplainerPage> {
  const res = await fetch(`${VISION}/page/${pageId}`);
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  const nested = data.metadata;
  const metadata =
    nested && typeof nested === "object" && "editorial_headline" in nested
      ? nested
      : nested?.metadata ?? nested ?? {};
  return {
    id: data.id,
    imageUrl: resolveUrl(data.imageUrl),
    parentId: data.parentId,
    click: data.click,
    depth: data.depth,
    context: data.context,
    metadata,
    groundingMode: data.groundingMode,
    visionModel: data.visionModel,
    rawJson: data.rawJson,
    inputPrompt: data.inputPrompt,
    samConfidence: data.samConfidence,
  };
}

export async function confirmExplainerDrill(
  pageId: string,
  drillTopic?: string
): Promise<ExplainerPage> {
  const res = await fetch(`${VISION}/confirm-drill`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pageId, drillTopic }),
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return { ...data, imageUrl: resolveUrl(data.imageUrl) };
}

export async function cancelExplainerDrill(pageId: string): Promise<void> {
  const res = await fetch(`${VISION}/confirm-drill/${pageId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
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

import { throwIfResponseNotOk } from "../utils/errors";

// ─── Knowledge Base API ───────────────────────────────────────────────────────

const KB = `${API_BASE}/api/kb`;

export interface KbEntry {
  id: string;
  name: string;
  page_count: number;
  created_at: string;
  status?: "processing" | "ready" | "failed";
  error?: string;
}

export async function uploadKnowledgeBase(file: File): Promise<KbEntry> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${KB}/upload`, { method: "POST", body: fd });
  if (!res.ok) await throwIfResponseNotOk(res);
  return res.json();
}

export async function getKnowledgeBaseStatus(kbId: string): Promise<KbEntry> {
  const res = await fetch(`${KB}/status/${kbId}`);
  if (res.status === 404) {
    throw new Error("Knowledge base was removed before ingestion finished");
  }
  if (!res.ok) await throwIfResponseNotOk(res);
  return res.json();
}

export async function waitForKnowledgeBase(
  kbId: string,
  { intervalMs = 2000, timeoutMs = 30 * 60 * 1000 } = {},
): Promise<KbEntry> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const entry = await getKnowledgeBaseStatus(kbId);
    if (entry.status === "ready") return entry;
    if (entry.status === "failed") {
      throw new Error(entry.error || "Knowledge base ingestion failed");
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error("Knowledge base ingestion timed out");
}

export async function listKnowledgeBases(): Promise<KbEntry[]> {
  const res = await fetch(`${KB}/list`);
  if (!res.ok) await throwIfResponseNotOk(res);
  return res.json();
}

export async function deleteKnowledgeBase(kbId: string): Promise<void> {
  const res = await fetch(`${KB}/${kbId}`, { method: "DELETE" });
  if (!res.ok) await throwIfResponseNotOk(res);
}

// ─── Stream page ─────────────────────────────────────────────────────────────

export async function streamExplainerPage(
  params: {
    query?: string;
    parentId?: string;
    x?: number;
    y?: number;
    customTopic?: string;
    groundingMode?: string;
    visionModel?: string;
    cacheBust?: string;
    drillMode?: string;
    kbId?: string | null;
  },
  onEvent: (type: string, data: Record<string, unknown>) => void
): Promise<void> {
  const res = await fetch(`${VISION}/stream-page`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...params,
      visionModel: params.visionModel ?? "qwen3.5",
      groundingMode: params.groundingMode ?? "red_ring",
      drillMode: params.drillMode ?? "inside",
      kbId: params.kbId ?? null,
    }),
  });
  if (!res.ok) await throwIfResponseNotOk(res);

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatchEvents = () => {
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      let eventType = "message";
      let eventData: Record<string, unknown> | null = null;
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event: ")) eventType = line.slice(7).trim();
        else if (line.startsWith("data: ")) {
          try {
            eventData = JSON.parse(line.slice(6).trim());
          } catch {
            eventData = { message: line.slice(6).trim() };
          }
        }
      }
      if (eventData) {
        if (typeof eventData.imageUrl === "string") {
          eventData.imageUrl = resolveUrl(eventData.imageUrl);
        }
        onEvent(eventType, eventData);
      }
      boundary = buffer.indexOf("\n\n");
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (value) buffer += decoder.decode(value, { stream: true });
    dispatchEvents();
    if (done) break;
  }

  buffer += decoder.decode();
  dispatchEvents();
}

export function b64ToDataUrl(b64: string) {
  return `data:image/png;base64,${b64}`;
}

export type { ExplainerPage, GroundingMode, VisionModelKey };
