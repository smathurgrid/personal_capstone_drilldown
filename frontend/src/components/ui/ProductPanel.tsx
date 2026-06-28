import { useState, useEffect, useRef } from 'react';
import { Sparkles, X, ChevronRight, BookOpen, Trash2, Upload, Loader2 } from 'lucide-react';
import { Hotspot, Mode, DrillResult } from '../../types';
import type { KbEntry } from '../../services/explainer-api';

interface ProductPanelProps {
  hotspot: Hotspot | null;
  onClose: () => void;
  mode: Mode;
  drillResult: DrillResult | null;
  onDrillDown: (hotspot?: Hotspot) => void;
  customClickPosition?: { x: number; y: number } | null;
  drillMode?: string;
  onDrillModeChange?: (mode: string) => void;
  kbMode?: 'generic' | 'kb';
  onKbModeChange?: (mode: 'generic' | 'kb') => void;
  kbList?: KbEntry[];
  activeKbId?: string | null;
  onActiveKbChange?: (id: string) => void;
  onKbUpload?: (file: File) => void;
  onKbDelete?: (id: string) => void;
  kbUploading?: boolean;
}

export default function ProductPanel({
  hotspot,
  onClose,
  drillResult,
  onDrillDown,
  customClickPosition,
  drillMode = 'inside',
  onDrillModeChange,
  kbMode = 'generic',
  onKbModeChange,
  kbList = [],
  activeKbId,
  onActiveKbChange,
  onKbUpload,
  onKbDelete,
  kbUploading = false,
}: ProductPanelProps) {
  const [activeTabId, setActiveTabId] = useState<string>('all-labels');
  const kbFileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Always default to "all-labels" tab
    setActiveTabId('all-labels');
  }, [hotspot]);

  if (!drillResult) {
    return (
      <aside className="w-[420px] min-w-[420px] max-w-[420px] shrink-0 glass-panel shadow-[-20px_0_40px_rgba(0,0,0,0.3)] z-[501] flex flex-col h-full p-8 items-center justify-center text-center animate-in slide-in-from-right duration-300">
        <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4 border border-white/10 animate-pulse">
          <Sparkles className="w-6 h-6 text-secondary" />
        </div>
        <h3 className="font-serif text-lg text-on-surface font-bold mb-2">Select a Target Spot</h3>
        <p className="text-on-surface-variant text-sm font-light leading-relaxed max-w-[260px]">
          Click any active marker or bounding box inside the visual scope workspace to drill down into precise specifications.
        </p>
      </aside>
    );
  }

  // Show panel if there's either a hotspot or a custom click position
  const hasSelection = hotspot || customClickPosition;

  const allHotspots = drillResult.hotspots || [];
  const imageDescription = drillResult.metadata?.explainer_paragraph || drillResult.subtitle || 'No description available.';
  const imageTitle = drillResult.title || 'Image Analysis';
  const kbCitation = drillResult.metadata?.kb_citation as string | undefined;
  const kbScore = drillResult.metadata?.kb_score as number | undefined;
  const kbWarning = drillResult.metadata?.kb_warning as string | undefined;
  const povWarning = drillResult.metadata?.pov_warning as string | undefined;
  const kbExtraHits = (drillResult.metadata?.kb_extra_hits as Array<{
    text: string;
    page_num: number;
    source_name: string;
    score?: number;
  }>) || [];

  if (!hasSelection) {
    return (
      <aside className="w-[420px] min-w-[420px] max-w-[420px] shrink-0 glass-panel shadow-[-20px_0_40px_rgba(0,0,0,0.3)] z-[501] flex flex-col h-full p-8 items-center justify-center text-center animate-in slide-in-from-right duration-300">
        <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4 border border-white/10 animate-pulse">
          <Sparkles className="w-6 h-6 text-secondary" />
        </div>
        <h3 className="font-serif text-lg text-on-surface font-bold mb-2">Select a Target Spot</h3>
        <p className="text-on-surface-variant text-sm font-light leading-relaxed max-w-[260px]">
          Click any marker on the image or anywhere on the canvas to drill down into that area.
        </p>
      </aside>
    );
  }

  // Define tabs
  const tabs = [
    { id: 'all-labels', label: 'ALL LABELS' },
    { id: 'description', label: 'DESCRIPTION' }
  ];

  return (
    <aside className="w-[420px] min-w-[420px] max-w-[420px] shrink-0 glass-panel shadow-[-20px_0_40px_rgba(0,0,0,0.3)] z-[501] flex flex-col h-full animate-in slide-in-from-right duration-300 text-left">
      <div className="p-6 border-b border-white/10 pt-8 flex-shrink-0">
        <div className="flex justify-between items-start mb-4">
          <div className="max-w-[280px] flex-1 min-w-0">
            <h2 className="font-serif text-xl md:text-2xl font-bold text-on-surface mb-1 truncate" title={imageTitle}>
              {imageTitle}
            </h2>
            <div className="flex items-center gap-2 text-on-surface-variant font-mono text-[10px] uppercase font-bold tracking-wider">
              <Sparkles className="w-3.5 h-3.5 text-orange-glow animate-pulse shrink-0" />
              <span>AI-Generated Insights</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-on-surface-variant hover:text-secondary bg-white/5 hover:bg-white/10 p-1.5 rounded-full transition-colors cursor-pointer shrink-0"
            title="Collapse Sidebar"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {(onDrillModeChange || onKbModeChange) && (
          <div className="mt-4 space-y-3 border-t border-white/5 pt-4">
            {onDrillModeChange && (
              <div>
                <label className="text-[9px] font-mono uppercase tracking-widest text-on-surface-variant block mb-1.5">
                  Drill Mode
                </label>
                <select
                  value={drillMode}
                  onChange={(e) => onDrillModeChange(e.target.value)}
                  className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-[11px] font-mono text-on-surface focus:outline-none focus:border-orange-glow/50"
                >
                  <option value="inside">Inside Zoom (Macro)</option>
                  <option value="pov">POV Perspective (Outward)</option>
                </select>
              </div>
            )}

            {onKbModeChange && (
              <div>
                <label className="text-[9px] font-mono uppercase tracking-widest text-on-surface-variant block mb-1.5">
                  Context Source
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => onKbModeChange('generic')}
                    className={`flex-1 px-2 py-1.5 font-mono text-[9px] uppercase font-bold rounded transition-all ${
                      kbMode === 'generic'
                        ? 'bg-primary-container text-primary border border-primary/25'
                        : 'text-outline hover:text-on-surface border border-transparent'
                    }`}
                  >
                    Generic
                  </button>
                  <button
                    type="button"
                    onClick={() => onKbModeChange('kb')}
                    className={`flex-1 px-2 py-1.5 font-mono text-[9px] uppercase font-bold rounded transition-all flex items-center justify-center gap-1 ${
                      kbMode === 'kb'
                        ? 'bg-secondary/10 text-secondary border border-secondary/25'
                        : 'text-outline hover:text-on-surface border border-transparent'
                    }`}
                  >
                    <BookOpen className="w-3 h-3" /> KB
                  </button>
                </div>

                {kbMode === 'kb' && onKbUpload && (
                  <div className="mt-2 space-y-2">
                    <input
                      ref={kbFileRef}
                      type="file"
                      accept=".pdf"
                      className="hidden"
                      onChange={(e) => e.target.files?.[0] && onKbUpload(e.target.files[0])}
                    />
                    <button
                      type="button"
                      onClick={() => kbFileRef.current?.click()}
                      disabled={kbUploading}
                      className="w-full flex items-center justify-center gap-2 py-1.5 bg-white/5 border border-white/10 rounded-lg font-mono text-[9px] uppercase font-bold text-on-surface-variant disabled:opacity-50"
                    >
                      {kbUploading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
                      {kbUploading ? 'Ingesting…' : 'Upload PDF'}
                    </button>
                    {kbList.map((kb) => (
                      <div
                        key={kb.id}
                        onClick={() => onActiveKbChange?.(kb.id)}
                        className={`flex items-center gap-2 px-2 py-1.5 rounded border cursor-pointer text-[10px] font-mono ${
                          activeKbId === kb.id ? 'border-secondary/50 bg-secondary/10' : 'border-white/5'
                        }`}
                      >
                        <span className="flex-1 truncate">
                          {kb.name}
                          {kb.status === 'processing' && <span className="ml-1 text-secondary">(ingesting…)</span>}
                        </span>
                        {onKbDelete && (
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); onKbDelete(kb.id); }}
                            disabled={kb.status === 'processing' || kbUploading}
                            className="text-on-surface-variant hover:text-red-400 disabled:opacity-30 disabled:pointer-events-none"
                            title={kb.status === 'processing' ? 'Wait for ingestion to finish' : 'Remove'}
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        <div className="flex gap-2 overflow-x-auto pb-1 mt-4 scrollbar-hide">
          {tabs.map((tab) => {
            const itemActive = tab.id === activeTabId;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTabId(tab.id)}
                className={`px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider rounded whitespace-nowrap transition-all border-b-2 cursor-pointer ${
                  itemActive
                    ? 'bg-secondary-container/20 text-secondary border-secondary'
                    : 'text-on-surface-variant border-transparent hover:text-on-surface hover:bg-white/5'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4 min-h-0">
        {activeTabId === 'all-labels' && (
          <>
            <p className="text-xs text-on-surface-variant font-mono uppercase tracking-[1px] mb-2 flex-shrink-0">
              Detected Components ({allHotspots.length})
            </p>
            
            <div className="space-y-3 flex-shrink-0">
              {allHotspots.map((spot, idx) => {
                const isCurrentSpot = hotspot && spot.id === hotspot.id;
                return (
                  <div
                    key={spot.id}
                    onClick={() => {
                      console.log('[ProductPanel] Label clicked, drilling into:', spot.title);
                      onDrillDown(spot);
                    }}
                    className={`glass-card rounded-xl border p-4 transition-all cursor-pointer ${
                      isCurrentSpot
                        ? 'border-secondary bg-secondary/5 hover:border-secondary/80'
                        : 'border-white/10 hover:border-orange-glow/50 hover:bg-white/5'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`font-mono text-[10px] font-bold tracking-wider shrink-0 ${
                            isCurrentSpot ? 'text-secondary' : 'text-on-surface-variant'
                          }`}>
                            #{String(idx + 1).padStart(2, '0')}
                          </span>
                          <h3 className="font-serif text-sm font-bold text-on-surface truncate">
                            {spot.title}
                          </h3>
                        </div>
                        <p className="text-[11px] text-on-surface-variant leading-relaxed line-clamp-2 mb-2">
                          {spot.description}
                        </p>
                        <div className="flex items-center gap-2 text-[10px] text-on-surface-variant">
                          <span className="font-mono">Position:</span>
                          <span className="font-mono text-primary">
                            {Math.round(spot.x)}%, {Math.round(spot.y)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Single Generate Drilldown button at bottom */}
            <div className="mt-4 flex-shrink-0">
              <button
                onClick={() => {
                  console.log('[ProductPanel] Generate Drilldown button clicked for:', hotspot ? hotspot.title : 'custom position');
                  onDrillDown(hotspot || undefined);
                }}
                className="w-full py-3 px-4 bg-orange-glow hover:bg-[#E0784C] text-white font-mono text-xs uppercase font-bold tracking-widest rounded-lg transition-all hover:scale-[1.02] active:scale-[0.98] shadow-lg flex items-center justify-center gap-2"
              >
                <ChevronRight className="w-5 h-5" />
                Generate Drilldown
              </button>
              <p className="text-[10px] text-on-surface-variant text-center mt-2 font-mono">
                {hotspot ? 'Drill into selected label' : 'Drill into custom position'}
              </p>
            </div>
          </>
        )}

        {activeTabId === 'description' && (
          <div className="flex flex-col gap-4 h-full">
            <div className="flex-shrink-0">
              <p className="text-xs text-on-surface-variant font-mono uppercase tracking-[1px] mb-3">
                Image Analysis
              </p>
              
              <div className="glass-card rounded-xl border border-white/10 p-4 leading-relaxed text-sm text-on-surface font-light">
                <p className="whitespace-pre-line">{imageDescription}</p>
              </div>

              {kbCitation && (
                <div className="mt-3 glass-card rounded-xl border border-secondary/20 bg-secondary/5 p-3">
                  <p className="text-[9px] font-mono uppercase tracking-widest text-secondary mb-1">Source</p>
                  <p className="text-xs text-on-surface font-mono">
                    {kbCitation}
                    {kbScore != null && (
                      <span className="text-on-surface-variant"> · {(kbScore * 100).toFixed(0)}% match</span>
                    )}
                  </p>
                </div>
              )}

              {povWarning && (
                <div className="mt-3 glass-card rounded-xl border border-amber-500/30 bg-amber-500/5 p-3">
                  <p className="text-[9px] font-mono uppercase tracking-widest text-amber-400 mb-1">POV Mode</p>
                  <p className="text-xs text-on-surface-variant">{povWarning}</p>
                </div>
              )}

              {kbWarning && (
                <div className="mt-3 glass-card rounded-xl border border-amber-500/30 bg-amber-500/5 p-3">
                  <p className="text-[9px] font-mono uppercase tracking-widest text-amber-400 mb-1">Knowledge Base</p>
                  <p className="text-xs text-on-surface-variant">{kbWarning}</p>
                </div>
              )}

              {kbExtraHits.length > 0 && (
                <div className="mt-3 glass-card rounded-xl border border-white/10 p-3">
                  <p className="text-[9px] font-mono uppercase tracking-widest text-on-surface-variant mb-2">
                    Related manual excerpts
                  </p>
                  <div className="space-y-2">
                    {kbExtraHits.map((hit, idx) => (
                      <div key={idx} className="text-xs text-on-surface-variant border-l-2 border-secondary/30 pl-2">
                        <p className="font-mono text-[10px] text-secondary mb-0.5">
                          {hit.source_name}, p.{hit.page_num}
                          {hit.score != null && (
                            <span className="text-on-surface-variant"> · {(hit.score * 100).toFixed(0)}%</span>
                          )}
                        </p>
                        <p className="line-clamp-3">{hit.text}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="flex-shrink-0">
              <p className="text-xs text-on-surface-variant font-mono uppercase tracking-[1px] mb-3">
                Image Metadata
              </p>
              <div className="glass-card rounded-xl border border-white/10 overflow-hidden divide-y divide-white/5">
                <div className="flex justify-between items-center p-3 text-xs">
                  <span className="text-on-surface-variant font-mono uppercase tracking-[1px]">Title</span>
                  <span className="text-on-surface font-semibold text-right truncate max-w-[200px]">{drillResult.title}</span>
                </div>
                <div className="flex justify-between items-center p-3 text-xs">
                  <span className="text-on-surface-variant font-mono uppercase tracking-[1px]">Category</span>
                  <span className="text-on-surface font-semibold text-right">{drillResult.category}</span>
                </div>
                <div className="flex justify-between items-center p-3 text-xs">
                  <span className="text-on-surface-variant font-mono uppercase tracking-[1px]">Components</span>
                  <span className="text-on-surface font-semibold text-right">{allHotspots.length} detected</span>
                </div>
                {drillResult.depth !== undefined && (
                  <div className="flex justify-between items-center p-3 text-xs">
                    <span className="text-on-surface-variant font-mono uppercase tracking-[1px]">Drill Depth</span>
                    <span className="text-on-surface font-semibold text-right">Level {drillResult.depth}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
