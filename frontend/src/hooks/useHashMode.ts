import { useEffect, useState } from "react";
import type { AppMode } from "@shared/types";

const DEFAULT_MODE: AppMode =
  (import.meta.env.VITE_DEFAULT_MODE as AppMode) || "explainer";

function parseModeFromHash(): AppMode {
  const segment = window.location.hash.replace(/^#\/?/, "").split("?")[0];
  return segment === "ecommerce" || segment === "explainer" || segment === "speculative"
    ? segment
    : DEFAULT_MODE;
}

export function useHashMode() {
  const [mode, setMode] = useState<AppMode>(parseModeFromHash);

  useEffect(() => {
    if (!window.location.hash) {
      window.location.hash = `/${mode}`;
    }
    const onHashChange = () => setMode(parseModeFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [mode]);

  const switchMode = (next: AppMode) => {
    setMode(next);
    window.location.hash = `/${next}`;
  };

  return { mode, switchMode };
}
