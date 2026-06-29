import React, { useEffect, useState } from 'react';
import { User, ChevronRight, Menu, HelpCircle } from 'lucide-react';
import { AIStatusBadge } from './core_components';
import { API_BASE } from '../../services/api';

interface HeaderProps {
  breadcrumbs?: string[];
  activeTab: string;
  onNavigate: (tab: string) => void;
  onClearSearch: () => void;
  showTabs?: boolean;
}

export default function Header({
  breadcrumbs,
  activeTab,
  onNavigate,
  onClearSearch,
  showTabs = true,
}: HeaderProps) {
  const [vlmStatus, setVlmStatus] = useState<'online' | 'loading' | 'offline'>('loading');
  const [qdrantStatus, setQdrantStatus] = useState<'connected' | 'loading' | 'offline'>('loading');
  const [fluxStatus, setFluxStatus] = useState<'ready' | 'loading' | 'offline'>('loading');

  // Query backend health to set live system status badges!
  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/health`);
        if (res.ok) {
          const data = await res.json();
          const modules = data.modules || {};
          
          // Explainer Vision VLM
          if (modules.explainer_vision?.ready && modules.explainer_vision?.checks?.ollama_reachable) {
            setVlmStatus('online');
          } else {
            setVlmStatus('offline');
          }

          // Qdrant (Ecommerce DB status)
          if (modules.ecommerce?.checks?.qdrant_path_exists) {
            setQdrantStatus('connected');
          } else {
            setQdrantStatus('offline');
          }

          // Flux Image Generator
          if (modules.explainer_generate?.ready) {
            setFluxStatus('ready');
          } else {
            setFluxStatus('offline');
          }
        } else {
          throw new Error();
        }
      } catch (err) {
        setVlmStatus('offline');
        setQdrantStatus('offline');
        setFluxStatus('offline');
      }
    };

    fetchHealth();
    const interval = setInterval(fetchHealth, 15000); // Check every 15s
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-12 border-b border-outline bg-[#0A0D14] flex-shrink-0 z-[100] w-full">
      <div className="flex justify-between items-center h-full px-6 w-full mx-auto">
        <div className="flex items-center gap-6">
          <div 
            onClick={onClearSearch}
            className="flex items-center gap-3 cursor-pointer group select-none"
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-primary to-secondary flex items-center justify-center shadow-[0_0_15px_rgba(0,229,255,0.3)] group-hover:scale-105 transition-transform">
              <span className="font-mono text-xs font-black text-background">DD</span>
            </div>
            <span className="font-sans text-lg font-bold tracking-tight text-on-surface flex items-center">
              DrillDown
              <span className="text-[10px] font-mono tracking-widest font-bold text-primary ml-2 border border-primary/20 px-1.5 py-0.5 rounded bg-primary/5">
                V1.0
              </span>
            </span>
          </div>
          
          {/* Breadcrumbs */}
          {breadcrumbs && breadcrumbs.length > 0 && (
            <nav className="hidden md:flex items-center gap-2 text-on-surface-muted font-mono text-[11px] tracking-wider">
              <ChevronRight className="w-3.5 h-3.5 text-on-surface-muted/30" />
              {breadcrumbs.map((crumb, idx) => (
                <React.Fragment key={idx}>
                  {idx > 0 && <ChevronRight className="w-3.5 h-3.5 text-on-surface-muted/30" />}
                  <span 
                    className={`${
                      idx === breadcrumbs.length - 1 
                        ? 'text-primary font-bold font-mono' 
                        : 'hover:text-on-surface hover:underline cursor-pointer transition-colors'
                    }`}
                  >
                    {crumb}
                  </span>
                </React.Fragment>
              ))}
            </nav>
          )}
        </div>

        {/* Center menu links */}
        {showTabs && (
          <nav className="hidden md:flex items-center gap-1.5 bg-white/2 border border-white/5 p-1 rounded-xl">
            {[
              { id: 'explore', label: 'Explore Workspace' },
              { id: 'history', label: 'Explore Logs' }
            ].map((link) => (
              <button
                key={link.id}
                onClick={() => onNavigate(link.id)}
                className={`font-mono text-[10px] uppercase tracking-wider transition-all py-1.5 px-4 rounded-lg cursor-pointer ${
                  activeTab === link.id
                    ? 'text-primary bg-primary/10 border border-primary/20 font-bold shadow-[0_0_10px_rgba(0,229,255,0.05)]'
                    : 'text-on-surface-muted border border-transparent hover:text-on-surface'
                }`}
              >
                {link.label}
              </button>
            ))}
          </nav>
        )}

        {/* Right side diagnostics and details */}
        <div className="flex items-center gap-4">
          {/* AI Diagnostics Panel */}
          <div className="hidden lg:flex items-center gap-2.5">
            <AIStatusBadge label="VLM" status={vlmStatus} />
            <AIStatusBadge label="Qdrant" status={qdrantStatus} />
            <AIStatusBadge label="Flux" status={fluxStatus} />
          </div>

          <div className="w-[1px] h-4 bg-outline hidden lg:block" />

          <button className="hover:bg-white/5 p-2 rounded-xl cursor-pointer transition-colors text-on-surface-muted hover:text-primary">
            <HelpCircle className="w-4 h-4" />
          </button>
          
          <button className="hover:bg-white/5 p-2 rounded-xl cursor-pointer transition-colors text-on-surface-muted hover:text-primary">
            <User className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
