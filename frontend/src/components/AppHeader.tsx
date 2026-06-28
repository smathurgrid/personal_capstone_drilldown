import { Circle, RefreshCw, ShoppingBag, Sparkles, Zap } from "lucide-react";
import type { AppMode } from "@shared/types";

type AppHeaderProps = {
  mode: AppMode;
  onSwitchMode: (mode: AppMode) => void;
  loading: boolean;
  backendOnline: boolean;
  ecommerceReady?: boolean;
  explainerReady?: boolean;
  showModuleStatus: boolean;
  onRefresh: () => void;
};

export default function AppHeader({
  mode,
  onSwitchMode,
  loading,
  backendOnline,
  ecommerceReady,
  explainerReady,
  showModuleStatus,
  onRefresh,
}: AppHeaderProps) {
  return (
    <header className="top-bar">
      <div className="brand">
        <Sparkles size={22} />
        <div>
          <h1>DrillDown</h1>
          <span className="brand-sub">Visual Intelligence Platform</span>
        </div>
      </div>

      <nav className="mode-toggle" aria-label="Application mode">
        <button
          type="button"
          className={mode === "ecommerce" ? "active" : ""}
          onClick={() => onSwitchMode("ecommerce")}
        >
          <ShoppingBag size={16} />
          Ecommerce
        </button>
        <button
          type="button"
          className={mode === "explainer" ? "active" : ""}
          onClick={() => onSwitchMode("explainer")}
        >
          <Sparkles size={16} />
          Explainer
        </button>
        <button
          type="button"
          className={mode === "speculative" ? "active" : ""}
          onClick={() => onSwitchMode("speculative")}
        >
          <Zap size={16} />
          Speculative
        </button>
      </nav>

      <div className="status-cluster">
        <div className="status-pill" data-online={backendOnline} title="API gateway">
          <Circle size={8} fill="currentColor" />
          {loading ? "Checking…" : backendOnline ? "API online" : "API offline"}
        </div>
        {showModuleStatus && (
          <>
            <div
              className="status-pill module"
              data-online={ecommerceReady}
              title="Ecommerce module (Qdrant + Gemini)"
            >
              Shop {ecommerceReady ? "ready" : "degraded"}
            </div>
            <div
              className="status-pill module"
              data-online={explainerReady}
              title="Explainer vision + generation"
            >
              Explain {explainerReady ? "ready" : "degraded"}
            </div>
          </>
        )}
        <button type="button" className="icon-btn" onClick={onRefresh} title="Refresh health" aria-label="Refresh">
          <RefreshCw size={14} />
        </button>
      </div>
    </header>
  );
}
