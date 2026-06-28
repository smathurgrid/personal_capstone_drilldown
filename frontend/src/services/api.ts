import type { AppMode, GlobalHealth } from "@shared/types";

const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export function resolveUrl(url: string): string {
  if (url.startsWith("http") || url.startsWith("data:")) return url;
  return `${API_BASE}${url}`;
}

export function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  return fetch(input, {
    ...init,
    credentials: init.credentials ?? "include",
  });
}

export async function apiPostForm<T>(path: string, fields: Record<string, string>): Promise<T> {
  const fd = new FormData();
  for (const [key, value] of Object.entries(fields)) {
    fd.append(key, value);
  }
  const res = await apiFetch(path, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<T>;
}

export async function fetchGlobalHealth(): Promise<GlobalHealth> {
  const res = await apiFetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}

export async function fetchModuleHealth(mode: AppMode) {
  const path =
    mode === "ecommerce"
      ? "/api/ecommerce/health"
      : mode === "explainer"
        ? "/api/explainer/vision/health"
        : "/api/health";
  const res = await apiFetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`Module health failed: ${res.status}`);
  return res.json();
}

export { API_BASE };
export type { AppMode, GlobalHealth };
