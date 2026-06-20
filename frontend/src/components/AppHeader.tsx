import { Circle, RefreshCw, ShoppingBag, Sparkles } from "lucide-react";
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
  const handleHomeClick = () => {
    window.location.hash = "/";
  };

  return (
    <header className="top-bar">
      <div className="brand">
        <button
          type="button"
          className="home-btn"
          onClick={handleHomeClick}
          title="Go to home"
          aria-label="Home"
        >
          <Sparkles size={24} strokeWidth={1.5} />
          <h1>DrillDown</h1>
        </button>
      </div>

      <nav className="mode-toggle" aria-label="Application mode">
        <button
          type="button"
          className={mode === "explainer" ? "active" : ""}
          onClick={() => onSwitchMode("explainer")}
          title="Switch to Explainer mode"
        >
          <Sparkles size={16} strokeWidth={1.5} />
          Explainer
        </button>
        <button
          type="button"
          className={mode === "ecommerce" ? "active" : ""}
          onClick={() => onSwitchMode("ecommerce")}
          title="Switch to Ecommerce mode"
        >
          <ShoppingBag size={16} strokeWidth={1.5} />
          Ecommerce
        </button>
      </nav>

      <div className="status-cluster">
        <div className="status-pill" data-online={backendOnline} title="Backend API status">
          <Circle size={6} fill="currentColor" strokeWidth={0} />
          {loading ? "Checking…" : backendOnline ? "Backend Active" : "Backend Offline"}
        </div>
        {showModuleStatus && (
          <>
            <div
              className="status-pill module"
              data-online={ecommerceReady}
              title="Ecommerce module status"
            >
              Shop {ecommerceReady ? "Ready" : "Degraded"}
            </div>
            <div
              className="status-pill module"
              data-online={explainerReady}
              title="Explainer module status"
            >
              Explain {explainerReady ? "Ready" : "Degraded"}
            </div>
          </>
        )}
        <button 
          type="button" 
          className="icon-btn" 
          onClick={onRefresh} 
          title="Refresh health status" 
          aria-label="Refresh"
        >
          <RefreshCw size={16} strokeWidth={1.5} />
        </button>
      </div>
    </header>
  );
}
