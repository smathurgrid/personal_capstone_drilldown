import { useEffect, useState } from "react";
import type { AppMode } from "@shared/types";

type PageMode = "home" | AppMode;

const DEFAULT_MODE: PageMode = "home";

function parseModeFromHash(): PageMode {
  const segment = window.location.hash.replace(/^#\/?/, "").split("?")[0];
  if (segment === "ecommerce" || segment === "explainer") {
    return segment;
  }
  return segment === "" || segment === "home" ? "home" : DEFAULT_MODE;
}

export function useHashMode() {
  const [mode, setMode] = useState<PageMode>(parseModeFromHash);

  useEffect(() => {
    if (!window.location.hash || window.location.hash === "#/") {
      window.location.hash = "/";
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
