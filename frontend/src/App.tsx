import EcommercePage from "./pages/EcommercePage";
import ExplainerPage from "./pages/ExplainerPage";
import SpeculativeDrillPage from "./pages/SpeculativeDrillPage";
import AppHeader from "./components/AppHeader";
import { useAppHealth } from "./hooks/useAppHealth";
import { useHashMode } from "./hooks/useHashMode";
import { API_BASE } from "./services/api";

export default function App() {
  const { mode, switchMode } = useHashMode();
  const {
    health,
    loading,
    error,
    refresh,
    backendOnline,
    ecommerceReady,
    explainerReady,
  } = useAppHealth();

  return (
    <div className="app-shell">
      <AppHeader
        mode={mode}
        onSwitchMode={switchMode}
        loading={loading}
        backendOnline={backendOnline}
        ecommerceReady={ecommerceReady}
        explainerReady={explainerReady}
        showModuleStatus={Boolean(health)}
        onRefresh={refresh}
      />

      {error && (
        <div className="banner error">
          Cannot reach backend at <code>{API_BASE}</code>: {error}
        </div>
      )}

      <main className="mode-viewport">
        {mode === "ecommerce" ? (
          <EcommercePage key="ecommerce" />
        ) : mode === "speculative" ? (
          <SpeculativeDrillPage key="speculative" />
        ) : (
          <ExplainerPage key="explainer" />
        )}
      </main>
    </div>
  );
}
