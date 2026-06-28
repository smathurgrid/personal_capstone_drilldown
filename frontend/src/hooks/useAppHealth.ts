import { useCallback, useEffect, useState } from "react";
import type { GlobalHealth } from "@shared/types";

import { fetchGlobalHealth } from "../services/api";

export function useAppHealth(pollIntervalMs = 30_000) {
  const [health, setHealth] = useState<GlobalHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setHealth(await fetchGlobalHealth());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backend unreachable");
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, pollIntervalMs);
    return () => clearInterval(id);
  }, [refresh, pollIntervalMs]);

  const backendOnline = health?.status === "ok";
  const ecommerceReady = health?.modules.ecommerce.ready;
  const explainerReady =
    health?.modules.explainer_vision.ready && health?.modules.explainer_generate.ready;

  return {
    health,
    loading,
    error,
    refresh,
    backendOnline,
    ecommerceReady,
    explainerReady,
  };
}
