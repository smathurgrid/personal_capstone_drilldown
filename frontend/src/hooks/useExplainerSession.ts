import { useCallback, useEffect, useRef } from "react";
import type { ExplainerPage } from "../services/explainer-api";
import { fetchExplainerPage } from "../services/explainer-api";

function parseSessionFromHash(): { chain: string[]; index: number } {
  const query = window.location.hash.split("?")[1] ?? "";
  const params = new URLSearchParams(query);
  const chain = (params.get("chain") ?? "")
    .split(",")
    .map((id) => id.trim())
    .filter(Boolean);
  const index = Math.max(0, parseInt(params.get("i") ?? "0", 10) || 0);
  return { chain, index: chain.length ? Math.min(index, chain.length - 1) : 0 };
}

function writeSessionToHash(pages: ExplainerPage[], currentIndex: number) {
  const ids = pages.filter((p) => p.id && !p.id.startsWith("streaming_")).map((p) => p.id);
  if (!ids.length) return;
  const base = window.location.hash.split("?")[0] || "#/explainer";
  const params = new URLSearchParams();
  params.set("chain", ids.join(","));
  params.set("i", String(currentIndex));
  const next = `${base}?${params.toString()}`;
  if (window.location.hash !== next) {
    window.history.replaceState(null, "", next);
  }
}

export function useExplainerSession(
  pages: ExplainerPage[],
  currentIndex: number,
  setPages: (pages: ExplainerPage[]) => void,
  setCurrentIndex: (index: number) => void
) {
  const restored = useRef(false);

  useEffect(() => {
    if (restored.current || pages.length > 0) return;
    const { chain, index } = parseSessionFromHash();
    if (!chain.length) return;
    restored.current = true;

    Promise.all(chain.map((id) => fetchExplainerPage(id)))
      .then((loaded) => {
        setPages(loaded);
        setCurrentIndex(Math.min(index, loaded.length - 1));
      })
      .catch((err) => console.warn("Session restore failed:", err));
  }, [pages.length, setPages, setCurrentIndex]);

  useEffect(() => {
    if (pages.length === 0 || pages.some((p) => p.isStreaming)) return;
    writeSessionToHash(pages, currentIndex);
  }, [pages, currentIndex]);

  const navigateToIndex = useCallback(
    (index: number) => {
      setCurrentIndex(index);
    },
    [setCurrentIndex]
  );

  return { navigateToIndex };
}
