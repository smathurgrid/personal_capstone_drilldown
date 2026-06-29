import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, X, ChevronRight, BookOpen, Trash2, Upload, Loader2, BarChart2, List, Tag, Eye } from 'lucide-react';
import { Hotspot, Mode, DrillResult, TabData, MatchItem } from '../../types';
import type { KbEntry } from '../../services/explainer-api';
import { GlassPanel, SimilarityScore, AnimatedButton } from './core_components';

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
    // Default to "all-labels" unless a specific hotspot is selected
    if (hotspot) {
      if (hotspot.details?.tabs && hotspot.details.tabs.length > 0) {
        setActiveTabId(hotspot.details.tabs[0].id);
      } else {
        setActiveTabId('description');
      }
    } else {
      setActiveTabId('all-labels');
    }
  }, [hotspot]);

  if (!drillResult) {
    return (
      <aside className="w-[440px] shrink-0 bg-background/40 backdrop-blur-xl border-l border-outline shadow-[-20px_0_50px_rgba(0,0,0,0.5)] z-[50] flex flex-col h-full p-8 items-center justify-center text-center animate-in slide-in-from-right duration-500">
        <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center mb-4 border border-primary/20 animate-pulse">
          <Sparkles className="w-5 h-5 text-primary" />
        </div>
        <h3 className="font-sans text-md font-bold uppercase tracking-wider text-on-surface mb-2">Select Target Spot</h3>
        <p className="text-on-surface-muted text-xs font-light leading-relaxed max-w-[280px]">
          Click any active marker or bounding box inside the visual scope workspace to drill down into precise specifications.
        </p>
      </aside>
    );
  }

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
      <aside className="w-[440px] shrink-0 bg-background/40 backdrop-blur-xl border-l border-outline shadow-[-20px_0_50px_rgba(0,0,0,0.5)] z-[50] flex flex-col h-full p-8 items-center justify-center text-center">
        <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center mb-4 border border-primary/20 animate-pulse">
          <Sparkles className="w-5 h-5 text-primary shadow-[0_0_10px_#00E5FF]" />
        </div>
        <h3 className="font-sans text-md font-bold uppercase tracking-wider text-on-surface mb-2">Select Target Spot</h3>
        <p className="text-on-surface-muted text-xs font-light leading-relaxed max-w-[280px]">
          Click any marker on the image or anywhere on the canvas to inspect its composition or recommendations.
        </p>
      </aside>
    );
  }

  // Dynamic Tabs definition
  const defaultTabs: TabData[] = [
    { id: 'all-labels', label: 'All Labels', type: 'list', contentJson: '[]' },
    { id: 'description', label: 'Description', type: 'markdown', contentJson: '""' }
  ];

  const tabs = (hotspot?.details?.tabs && hotspot.details.tabs.length > 0) 
    ? hotspot.details.tabs 
    : defaultTabs;

  const activeTab = tabs.find((t) => t.id === activeTabId) || tabs[0] || defaultTabs[0];

  // Helper parser for custom Tab contents (Matches, lists, charts)
  const getTabContent = (tab: TabData) => {
    if (!tab) return null;
    try {
      return JSON.parse(tab.contentJson);
    } catch (err) {
      return null;
    }
  };

  const parsedContent = getTabContent(activeTab);

  return (
    <aside className="w-[400px] shrink-0 bg-[#0A0D14] border-l border-outline flex flex-col h-full text-left relative z-20">
      {/* Header details */}
      <div className="p-6 border-b border-outline pt-8 flex-shrink-0 bg-background/30">
        <div className="flex justify-between items-start mb-4">
          <div className="max-w-[320px] flex-1 min-w-0">
            <h2 className="font-sans text-lg font-bold text-on-surface truncate uppercase tracking-wide" title={hotspot ? hotspot.title : 'Custom Scope'}>
              {hotspot ? hotspot.title : 'Custom Scope'}
            </h2>
            <div className="flex items-center gap-2 text-on-surface-muted font-mono text-[9px] uppercase font-bold tracking-wider mt-1">
              <Sparkles className="w-3.5 h-3.5 text-primary animate-pulse shrink-0" />
              <span>AI Interactive Target Analytics</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-on-surface-muted hover:text-primary bg-white/3 hover:bg-white/8 p-1.5 rounded-xl transition-all cursor-pointer shrink-0"
            title="Collapse Sidebar"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Global Controls inside panel (Drill mode + Knowledge Base) */}
        {(onDrillModeChange || onKbModeChange) && (
          <div className="mt-4 space-y-3 border-t border-white/5 pt-4">
            {onDrillModeChange && (
              <div>
                <label className="text-[9px] font-mono uppercase tracking-widest text-on-surface-muted block mb-1.5">
                  Analytical Lens Mode
                </label>
                <select
                  value={drillMode}
                  onChange={(e) => onDrillModeChange(e.target.value)}
                  className="w-full bg-[#05070D]/60 border border-outline rounded-xl px-3 py-2 text-[11px] font-mono text-on-surface focus:outline-none focus:border-primary/50 cursor-pointer"
                >
                  <option value="inside">Inside Zoom (Macro Cross-Section)</option>
                  <option value="pov">POV Perspective (Outward Line of Sight)</option>
                </select>
              </div>
            )}

            {onKbModeChange && (
              <div>
                <label className="text-[9px] font-mono uppercase tracking-widest text-on-surface-muted block mb-1.5">
                  Grounding Context Database
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => onKbModeChange('generic')}
                    className={`flex-1 py-1.5 font-mono text-[9px] uppercase font-bold rounded-xl transition-all cursor-pointer border ${
                      kbMode === 'generic'
                        ? 'bg-primary/10 text-primary border-primary/20 shadow-[0_0_10px_rgba(0,229,255,0.05)]'
                        : 'text-on-surface-muted border-transparent hover:text-on-surface'
                    }`}
                  >
                    Generic
                  </button>
                  <button
                    type="button"
                    onClick={() => onKbModeChange('kb')}
                    className={`flex-1 py-1.5 font-mono text-[9px] uppercase font-bold rounded-xl transition-all flex items-center justify-center gap-1 cursor-pointer border ${
                      kbMode === 'kb'
                        ? 'bg-secondary/10 text-secondary border-secondary/20 shadow-[0_0_10px_rgba(157,78,221,0.05)]'
                        : 'text-on-surface-muted border-transparent hover:text-on-surface'
                    }`}
                  >
                    <BookOpen className="w-3.5 h-3.5" /> PDF Manual
                  </button>
                </div>

                {kbMode === 'kb' && onKbUpload && (
                  <div className="mt-2.5 space-y-2 bg-white/2 border border-white/5 p-2 rounded-xl">
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
                      className="w-full flex items-center justify-center gap-2 py-1.5 bg-white/5 border border-white/10 rounded-lg font-mono text-[9px] uppercase font-bold text-on-surface hover:bg-white/10 cursor-pointer transition-colors"
                    >
                      {kbUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin text-secondary" /> : <Upload className="w-3.5 h-3.5" />}
                      {kbUploading ? 'Ingesting PDF...' : 'Upload PDF'}
                    </button>
                    {kbList.map((kb) => (
                      <div
                        key={kb.id}
                        onClick={() => onActiveKbChange?.(kb.id)}
                        className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg border cursor-pointer text-[10px] font-mono transition-all ${
                          activeKbId === kb.id ? 'border-secondary bg-secondary/5 text-secondary' : 'border-white/5 hover:border-white/15'
                        }`}
                      >
                        <span className="flex-1 truncate">
                          {kb.name}
                          {kb.status === 'processing' && <span className="ml-1 text-secondary text-[8px] animate-pulse">(ingesting…)</span>}
                        </span>
                        {onKbDelete && (
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); onKbDelete(kb.id); }}
                            disabled={kb.status === 'processing' || kbUploading}
                            className="text-on-surface-muted hover:text-red-400 p-0.5 rounded cursor-pointer"
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

        {/* Tab Buttons selection bar */}
        <div className="flex gap-2 overflow-x-auto pb-1 mt-4 scrollbar-hide">
          {tabs.map((tab) => {
            const itemActive = tab.id === activeTabId;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTabId(tab.id)}
                className={`px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider rounded-lg whitespace-nowrap transition-all border cursor-pointer ${
                  itemActive
                    ? 'bg-primary/10 text-primary border-primary/20 shadow-[0_0_10px_rgba(0,229,255,0.05)]'
                    : 'text-on-surface-muted border-transparent hover:text-on-surface hover:bg-white/4'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Dynamic Content Panel area */}
      <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4 min-h-0 bg-background/10">
        
        {/* TAB TYPE: matches (Premium 3D Product Recommendations) */}
        {activeTab.type === 'matches' && parsedContent && (
          <div className="space-y-4">
            <p className="text-[10px] text-on-surface-muted font-mono uppercase tracking-widest mb-1 flex items-center gap-1.5">
              <Tag className="w-3.5 h-3.5 text-primary" /> Similar Luxury Catalog Matches ({parsedContent.length})
            </p>

            <div className="grid grid-cols-1 gap-4">
              {parsedContent.map((product: MatchItem, idx: number) => (
                <motion.div
                  key={idx}
                  whileHover={{ scale: 1.01, y: -2 }}
                  className="glass-card rounded-2xl overflow-hidden border border-white/5 p-3 flex gap-4 glass-card-hover cursor-pointer"
                >
                  <div className="w-20 h-24 bg-black/40 rounded-xl overflow-hidden border border-white/5 relative shrink-0">
                    <img
                      src={product.imageUrl}
                      alt={product.name}
                      className="w-full h-full object-cover"
                    />
                  </div>

                  <div className="flex-1 flex flex-col justify-between min-w-0">
                    <div>
                      <span className="font-mono text-[8px] uppercase tracking-widest text-primary/80 font-bold">
                        {product.brand}
                      </span>
                      <h4 className="font-sans text-xs font-bold text-on-surface truncate mt-0.5">
                        {product.name}
                      </h4>
                      <p className="text-[10px] text-on-surface-muted mt-0.5 uppercase tracking-wide font-mono">
                        Source: {product.source}
                      </p>
                    </div>

                    <div className="flex justify-between items-center border-t border-white/5 pt-2 mt-2">
                      <span className="text-xs font-mono font-bold text-primary">
                        ${product.price}
                      </span>
                      <SimilarityScore score={product.matchPercent} />
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        )}

        {/* TAB TYPE: list (Parameter details) */}
        {activeTab.type === 'list' && parsedContent && (
          <div className="space-y-3">
            <p className="text-[10px] text-on-surface-muted font-mono uppercase tracking-widest mb-1 flex items-center gap-1.5">
              <List className="w-3.5 h-3.5 text-primary" /> Key System Attributes
            </p>

            <div className="glass-card rounded-2xl border border-white/5 overflow-hidden divide-y divide-white/5">
              {parsedContent.map((item: any, idx: number) => (
                <div key={idx} className="flex justify-between items-center p-3 text-xs">
                  <span className="text-on-surface-muted font-mono uppercase tracking-wider">{item.key || item.label}</span>
                  <span className="text-on-surface font-semibold text-right font-mono truncate max-w-[220px]">{item.value || item.text}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB TYPE: chart (Aesthetic Recharts or CSS Bars) */}
        {activeTab.type === 'chart' && parsedContent && (
          <div className="space-y-4">
            <p className="text-[10px] text-on-surface-muted font-mono uppercase tracking-widest mb-1 flex items-center gap-1.5">
              <BarChart2 className="w-3.5 h-3.5 text-primary" /> Operational Metrics Diagram
            </p>

            <GlassPanel className="p-4 flex flex-col gap-4 border border-white/5">
              <div className="space-y-3">
                {parsedContent.data?.map((dp: any, idx: number) => (
                  <div key={idx} className="space-y-1">
                    <div className="flex justify-between text-[10px] font-mono">
                      <span className="text-on-surface">{dp.label}</span>
                      <span className="text-primary font-bold">{dp.value}{parsedContent.unit}</span>
                    </div>
                    <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.min(dp.value, 100)}%` }}
                        transition={{ duration: 0.8, ease: "easeOut" }}
                        className="h-full bg-gradient-to-r from-primary to-secondary rounded-full"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </GlassPanel>
          </div>
        )}

        {/* TAB TYPE: markdown / general image description */}
        {(activeTabId === 'description' || activeTab.type === 'markdown') && (
          <div className="space-y-4">
            <p className="text-[10px] text-on-surface-muted font-mono uppercase tracking-widest mb-1 flex items-center gap-1.5">
              <Eye className="w-3.5 h-3.5 text-primary" /> Full Analytical Description
            </p>

            <div className="glass-card rounded-2xl border border-outline p-4 leading-relaxed text-xs text-on-surface font-light whitespace-pre-line bg-surface/30">
              {activeTabId === 'description' 
                ? imageDescription 
                : (typeof parsedContent === 'object' && parsedContent !== null
                    ? (parsedContent.content || parsedContent.text || JSON.stringify(parsedContent))
                    : (parsedContent || ''))}
            </div>

            {kbCitation && (
              <div className="glass-card rounded-2xl border border-secondary/20 bg-secondary/5 p-3.5">
                <p className="text-[9px] font-mono uppercase tracking-widest text-secondary mb-1.5 font-bold">Verified Manual Grounding Source</p>
                <p className="text-xs text-on-surface font-mono">
                  {kbCitation}
                  {kbScore != null && (
                    <span className="text-on-surface-muted"> · {(kbScore * 100).toFixed(0)}% reference confidence</span>
                  )}
                </p>
              </div>
            )}

            {povWarning && (
              <div className="glass-card rounded-2xl border border-amber-500/30 bg-amber-500/5 p-3.5">
                <p className="text-[9px] font-mono uppercase tracking-widest text-amber-400 mb-1.5 font-bold">POV Analytical Warning</p>
                <p className="text-xs text-on-surface-muted leading-relaxed">{povWarning}</p>
              </div>
            )}

            {kbWarning && (
              <div className="glass-card rounded-2xl border border-amber-500/30 bg-amber-500/5 p-3.5">
                <p className="text-[9px] font-mono uppercase tracking-widest text-amber-400 mb-1.5 font-bold">Knowledge Base Exception</p>
                <p className="text-xs text-on-surface-muted leading-relaxed">{kbWarning}</p>
              </div>
            )}

            {kbExtraHits.length > 0 && (
              <div className="glass-card rounded-2xl border border-white/5 p-4 space-y-3">
                <p className="text-[9px] font-mono uppercase tracking-widest text-on-surface-muted mb-2 font-bold">
                  Reference Manual Excerpts
                </p>
                <div className="space-y-3">
                  {kbExtraHits.map((hit, idx) => (
                    <div key={idx} className="text-xs text-on-surface-muted border-l border-secondary/40 pl-3">
                      <p className="font-mono text-[9px] text-secondary mb-1">
                        {hit.source_name}, p.{hit.page_num}
                        {hit.score != null && (
                          <span className="text-on-surface-muted"> · {(hit.score * 100).toFixed(0)}% score</span>
                        )}
                      </p>
                      <p className="text-[11px] leading-relaxed line-clamp-3">{hit.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Static list of detected components when showing "all-labels" tab */}
        {activeTabId === 'all-labels' && (
          <div className="space-y-3 flex-shrink-0">
            <p className="text-[10px] text-on-surface-muted font-mono uppercase tracking-widest mb-1">
              Detected System Components ({allHotspots.length})
            </p>

            <div className="space-y-2.5">
              {allHotspots.map((spot, idx) => {
                const isCurrentSpot = hotspot && spot.id === hotspot.id;
                return (
                  <motion.div
                    key={spot.id}
                    onClick={() => {
                      console.log('[ProductPanel] Label clicked, drilling into:', spot.title);
                      onDrillDown(spot);
                    }}
                    whileHover={{ scale: 1.01 }}
                    className={`glass-card rounded-xl border p-3.5 transition-all cursor-pointer ${
                      isCurrentSpot
                        ? 'border-primary bg-primary/5 hover:border-primary/80 shadow-[0_0_15px_rgba(0,229,255,0.08)]'
                        : 'border-white/5 hover:border-primary/40 hover:bg-white/3'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className={`font-mono text-[9px] font-bold tracking-wider shrink-0 ${
                            isCurrentSpot ? 'text-primary' : 'text-on-surface-muted'
                          }`}>
                            #{String(idx + 1).padStart(2, '0')}
                          </span>
                          <h3 className="font-sans text-xs font-bold text-on-surface truncate uppercase tracking-wide">
                            {spot.title}
                          </h3>
                        </div>
                        <p className="text-[11px] text-on-surface-muted leading-relaxed line-clamp-2 mb-2 font-sans font-light">
                          {spot.description}
                        </p>
                        <div className="flex items-center justify-between border-t border-white/5 pt-2">
                          <span className="text-[8px] font-mono text-on-surface-muted">COORDS: X:{Math.round(spot.x)}% Y:{Math.round(spot.y)}%</span>
                          <span className="text-[8px] font-mono text-primary uppercase font-bold tracking-widest">DRILl DOWN</span>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Persistent Bottom Action: Single Drill Down button */}
      <div className="p-6 border-t border-outline flex-shrink-0 bg-background/40">
        <AnimatedButton
          onClick={() => {
            console.log('[ProductPanel] Generate Drilldown button clicked for:', hotspot ? hotspot.title : 'custom position');
            onDrillDown(hotspot || undefined);
          }}
          className="w-full py-3 shadow-[0_0_20px_rgba(0,229,255,0.15)] flex items-center justify-center gap-2"
        >
          <ChevronRight className="w-4 h-4 shrink-0 text-primary" />
          <span>Generate Depth Drilldown</span>
        </AnimatedButton>
        <p className="text-[9px] text-on-surface-muted text-center mt-2.5 font-mono uppercase tracking-wider">
          {hotspot ? `INSPECT INNER RESOLUTION FOR: "${hotspot.title}"` : 'INSPECT Granular custom click position'}
        </p>
      </div>
    </aside>
  );
}
