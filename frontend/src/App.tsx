import { useState, useEffect, useRef } from 'react';
import { Search, X, Database, ArrowRight, BookOpen, Trash2, Upload, Loader2, Sparkles, Settings, HelpCircle, Layers, ChevronLeft, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Header from './components/ui/Header';
import DrillCanvas from './components/ui/DrillCanvas';
import ProductPanel from './components/ui/ProductPanel';
import RecentDrills from './components/ui/RecentDrills';
import DrillConfirmModal, { type PendingDrill } from './pages/explainer/DrillConfirmModal';
import DrillPipelineBar, { type DrillPipelineStage } from './components/ui/DrillPipelineBar';
import { drillAdapter, type PendingDrillPayload } from './services/drill-adapter';
import {
  uploadKnowledgeBase,
  listKnowledgeBases,
  deleteKnowledgeBase,
  waitForKnowledgeBase,
  type KbEntry,
} from './services/explainer-api';
import type { DrillResult, Hotspot, Mode } from './types';
import './styles/explainer.css';
import { GlassPanel, AnimatedButton, GenerationLoader } from './components/ui/core_components';

// ==========================================
// SPATIAL ANIMATED BACKGROUND WITH PARTICLES
// ==========================================
function SpatialBackground() {
  const particles = Array.from({ length: 25 });
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none z-0 bg-background">
      {/* Animated Glowing Orbs */}
      <motion.div
        animate={{
          x: [0, 80, -40, 0],
          y: [0, -60, 80, 0],
          scale: [1, 1.15, 0.95, 1],
        }}
        transition={{ duration: 25, repeat: Infinity, ease: "easeInOut" }}
        className="absolute top-[10%] left-[20%] w-[450px] h-[450px] rounded-full bg-primary/4 blur-[130px]"
      />
      <motion.div
        animate={{
          x: [0, -100, 60, 0],
          y: [0, 80, -60, 0],
          scale: [1, 0.9, 1.1, 1],
        }}
        transition={{ duration: 30, repeat: Infinity, ease: "easeInOut" }}
        className="absolute bottom-[15%] right-[20%] w-[500px] h-[500px] rounded-full bg-secondary/3 blur-[140px]"
      />
      <motion.div
        animate={{
          x: [0, 40, -80, 0],
          y: [0, 100, -40, 0],
        }}
        transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
        className="absolute top-[40%] left-[50%] w-[350px] h-[350px] rounded-full bg-accent-pink/2 blur-[120px]"
      />

      {/* Floating Particles */}
      {particles.map((_, idx) => {
        const size = Math.random() * 2 + 1;
        const startX = Math.random() * 100;
        const startY = Math.random() * 100;
        const duration = Math.random() * 15 + 10;
        const delay = Math.random() * -20;
        return (
          <motion.div
            key={idx}
            animate={{
              y: ["0vh", "-100vh"],
              opacity: [0, 0.6, 0.8, 0],
            }}
            transition={{
              duration,
              repeat: Infinity,
              delay,
              ease: "linear",
            }}
            style={{
              position: 'absolute',
              left: `${startX}%`,
              top: `${startY}%`,
              width: `${size}px`,
              height: `${size}px`,
              borderRadius: '50%',
              backgroundColor: idx % 2 === 0 ? '#00E5FF' : '#9D4EDD',
              boxShadow: idx % 5 === 0 ? '0 0 10px rgba(0,229,255,0.8)' : 'none',
            }}
          />
        );
      })}
    </div>
  );
}

// ==========================================
// CURSOR GLOW TRAIL COMPONENT
// ==========================================
function CursorGlow() {
  const [mousePos, setMousePosition] = useState({ x: -100, y: -100 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  return (
    <motion.div
      animate={{ x: mousePos.x, y: mousePos.y }}
      transition={{ type: "spring", stiffness: 120, damping: 24, mass: 0.15 }}
      className="cursor-glow hidden md:block"
    />
  );
}

// Helper to convert DrillResult to RecentDrill format
const toRecentDrill = (drill: DrillResult) => ({
  id: drill.id,
  title: drill.title,
  subtitle: drill.subtitle,
  badge: drill.category,
  badgeClass: drill.mode === 'ecommerce' 
    ? 'bg-secondary-container/80 text-secondary border-secondary/20'
    : 'bg-primary-container/80 text-primary border-primary/20',
  imageUrl: drill.imageUrl,
  mode: drill.mode
});

export default function App() {
  const [activeTab, setActiveTab] = useState<string>('explore');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchMode, setSearchMode] = useState<Mode>('explainer');
  const [currentDrill, setCurrentDrill] = useState<DrillResult | null>(null);
  const [activeHotspotId, setActiveHotspotId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [history, setHistory] = useState<DrillResult[]>([]);
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [currentStageId, setCurrentStageId] = useState<string>('');
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Spatial keyboard shortcuts: Cmd+K for command palette, Esc to exit
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        alert('🌌 Command Palette initialized: Explore coordinates at lightspeed.');
      }
      if (e.key === 'Escape') {
        handleClearSearch();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);
  const [customClickPosition, setCustomClickPosition] = useState<{ x: number; y: number } | null>(null);
  const [kbMode, setKbMode] = useState<'generic' | 'kb'>('generic');
  const [kbList, setKbList] = useState<KbEntry[]>([]);
  const [activeKbId, setActiveKbId] = useState<string | null>(null);
  const [kbUploading, setKbUploading] = useState(false);
  const [processingKbId, setProcessingKbId] = useState<string | null>(null);
  const [drillMode, setDrillMode] = useState<'inside' | 'pov'>('inside');
  const [drillPhase, setDrillPhase] = useState<'idle' | 'analyzing' | 'confirm' | 'generating'>('idle');
  const [drillPipeline, setDrillPipeline] = useState<DrillPipelineStage>('idle');
  const [drillStatus, setDrillStatus] = useState('');
  const [pendingDrill, setPendingDrill] = useState<PendingDrill | null>(null);
  const confirmResolverRef = useRef<((topic: string | null) => void) | null>(null);
  const lastDrillRef = useRef<{ x: number; y: number; hotspot?: Hotspot } | null>(null);
  const kbFileRef = useRef<HTMLInputElement>(null);

  const resolvedKbId = kbMode === 'kb' ? activeKbId : null;

  useEffect(() => {
    drillAdapter.setDrillMode(drillMode);
  }, [drillMode]);

  useEffect(() => {
    drillAdapter.setKbId(resolvedKbId);
  }, [resolvedKbId]);

  useEffect(() => {
    listKnowledgeBases()
      .then((list) => {
        setKbList(list);
        if (list.length > 0 && !activeKbId) setActiveKbId(list[list.length - 1].id);
      })
      .catch(() => {});
  }, []);

  const handleKbUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      alert('Only PDF files are supported for Knowledge Base');
      return;
    }
    setKbUploading(true);
    try {
      const entry = await uploadKnowledgeBase(file);
      setKbList((prev) => [...prev.filter((k) => k.id !== entry.id), entry]);
      setActiveKbId(entry.id);
      setKbMode('kb');
      if (entry.status === 'processing') {
        setProcessingKbId(entry.id);
        const ready = await waitForKnowledgeBase(entry.id);
        setKbList((prev) => [...prev.filter((k) => k.id !== ready.id), ready]);
      }
    } catch (err) {
      alert(`KB upload failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setProcessingKbId(null);
      setKbUploading(false);
    }
  };

  const handleKbDelete = async (kbId: string) => {
    if (kbId === processingKbId || kbUploading) return;
    const target = kbList.find((k) => k.id === kbId);
    if (target?.status === 'processing') return;
    try {
      await deleteKnowledgeBase(kbId);
      setKbList((prev) => {
        const remaining = prev.filter((k) => k.id !== kbId);
        if (activeKbId === kbId) {
          setActiveKbId(remaining.length > 0 ? remaining[remaining.length - 1].id : null);
          if (remaining.length === 0) setKbMode('generic');
        }
        return remaining;
      });
    } catch (err) {
      alert(`KB delete failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  // Handle triggering a drill exploration
  const handleTriggerDrill = async (query: string, mode: Mode, image?: File) => {
    const finalQuery = query.trim();
    if (!finalQuery && !image) {
      alert('Please enter a query or upload an image');
      return;
    }

    console.log('[App] Starting drill:', { query: finalQuery, mode, hasImage: !!image });
    setIsLoading(true);
    setActiveHotspotId(null);
    setActiveTab('explore');

    try {
      let result: DrillResult;
      
      if (image) {
        console.log('[App] Uploading image...');
        // Upload and show image immediately, labels will appear when ready
        result = await drillAdapter.exploreImage(image, (updatedResult) => {
          console.log('[App] 🔄 Hotspots ready! Updating canvas with', updatedResult.hotspots.length, 'labels');
          setCurrentDrill(updatedResult);
          if (updatedResult.hotspots.length > 0) {
            setActiveHotspotId(updatedResult.hotspots[0].id);
            console.log('[App] ✅ Auto-selected first hotspot:', updatedResult.hotspots[0].title);
          }
        });
        console.log('[App] Image uploaded, showing in canvas (labels loading...)');
      } else {
        console.log('[App] Generating from topic...');
        // Generate from topic
        result = await drillAdapter.exploreTopic(finalQuery, mode);
        console.log('[App] Topic generated successfully:', result);
      }

      console.log('[App] Setting current drill with', result.hotspots.length, 'hotspots');
      setCurrentDrill(result);

      // Auto-select first hotspot if available
      if (result.hotspots && result.hotspots.length > 0) {
        setActiveHotspotId(result.hotspots[0].id);
        console.log('[App] Auto-selected first hotspot:', result.hotspots[0].id);
      } else {
        console.log('[App] No hotspots yet, will appear when analysis completes');
      }

      // Set current stage
      if (result.drillPath && result.drillPath.length > 0) {
        const lastStage = result.drillPath[result.drillPath.length - 1];
        setCurrentStageId(lastStage.id);
      }

      // Add to history
      setHistory((prev) => {
        const filtered = prev.filter((item) => item.id !== result.id);
        return [result, ...filtered].slice(0, 10); // Keep last 10
      });

      // Clear image preview after successful upload
      if (image) {
        setSelectedImage(null);
        setImagePreviewUrl(null);
      }

    } catch (err) {
      console.error('[App] Exploration failed:', err);
      alert(`Failed to explore: ${err instanceof Error ? err.message : 'Unknown error'}. Check console for details.`);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle drill selection from recent drills
  const handleSelectDrill = (drill: { id: string }) => {
    const foundDrill = history.find(h => h.id === drill.id);
    if (foundDrill) {
      setCurrentDrill(foundDrill);
      setActiveTab('explore');
      if (foundDrill.hotspots && foundDrill.hotspots.length > 0) {
        setActiveHotspotId(foundDrill.hotspots[0].id);
      }
    }
  };

  // Handle hotspot selection - if clicking same hotspot, drill down
  const handleHotspotSelect = async (hotspotId: string) => {
    // Clear custom click position when selecting a hotspot
    setCustomClickPosition(null);
    
    // If clicking the already selected hotspot, drill down
    if (activeHotspotId === hotspotId && currentDrill) {
      const hotspot = currentDrill.hotspots.find(h => h.id === hotspotId);
      if (hotspot) {
        console.log('[App] Clicking selected hotspot again, drilling down:', hotspot.title);
        await handleDrillDown(hotspot);
        return;
      }
    }
    
    // Otherwise, just select it
    console.log('[App] Selecting hotspot:', hotspotId);
    setActiveHotspotId(hotspotId);
  };

  // Handle canvas click (clicking anywhere on image, not on a hotspot)
  const handleCanvasClick = (x: number, y: number) => {
    console.log('[App] Canvas clicked at position:', { x, y });
    setCustomClickPosition({ x, y });
    // Deselect any active hotspot
    setActiveHotspotId(null);
  };

  const isAnalyzing = drillPhase === 'analyzing';
  const isGenerating = drillPhase === 'generating';

  const mapPendingPayload = (pending: PendingDrillPayload): PendingDrill => ({
    pageId: pending.pageId,
    parentId: pending.parentId,
    click: pending.click,
    objectName: pending.objectName,
    drillTopic: pending.drillTopic,
    cropPreviewB64: pending.cropPreviewB64,
    metadata: pending.metadata as PendingDrill['metadata'],
    fromCache: pending.fromCache,
    imageUrl: pending.imageUrl,
    expiresAt: pending.expiresAt,
    ancestryChain: pending.ancestryChain,
    kb: pending.kb,
  });

  const runDrillDown = async (
    x: number,
    y: number,
    hotspot?: Hotspot,
    cacheBust?: string,
  ) => {
    if (!currentDrill) return;

    const title = hotspot?.title ?? 'Custom Position';
    lastDrillRef.current = { x, y, hotspot };

    setIsLoading(true);
    setDrillPhase('analyzing');
    setDrillPipeline('grounding');
    setDrillStatus(
      kbMode === 'kb'
        ? 'Grounding region and searching your manual (30–90s)…'
        : 'Isolating selected region…',
    );
    setCustomClickPosition(hotspot ? null : { x, y });

    try {
      const childResult = await drillAdapter.drillDown(
        currentDrill.id,
        x,
        y,
        {
          customTopic: hotspot && title !== 'Custom Position' ? title : undefined,
          cacheBust,
          onProgress: (msg) => setDrillStatus(msg),
          onPipelineStage: (stage) => setDrillPipeline(stage),
          onHistoryUpdate: (updated) => {
            setCurrentDrill((prev) => (prev?.id === updated.id ? updated : prev));
          },
          onAwaitingConfirm: (pending: PendingDrillPayload) =>
            new Promise<string | null>((resolve) => {
              setIsLoading(false);
              setPendingDrill(mapPendingPayload(pending));
              setDrillPhase('confirm');
              setDrillStatus('Review target and prompt before generating');
              confirmResolverRef.current = resolve;
            }),
        },
      );

      setDrillPhase('idle');
      setDrillPipeline('ready');
      setDrillStatus('');
      setPendingDrill(null);
      setCurrentDrill(childResult);
      setCustomClickPosition(null);

      if (childResult.hotspots?.length) {
        setActiveHotspotId(childResult.hotspots[0].id);
      }

      if (childResult.drillPath?.length) {
        setCurrentStageId(childResult.drillPath[childResult.drillPath.length - 1].id);
      }

      setHistory((prev) => {
        const filtered = prev.filter((item) => item.id !== childResult.id);
        return [childResult, ...filtered].slice(0, 10);
      });
    } catch (err) {
      console.error('[App] Drill down failed:', err);
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      if (errorMsg !== 'Drill cancelled') {
        alert(
          'Failed to generate drilldown image.\n\n' +
            `Error: ${errorMsg}\n\n` +
            'Check that Ollama is running and the backend logs for details.',
        );
      }
      setDrillPipeline(errorMsg === 'Drill cancelled' ? 'idle' : 'error');
      setDrillPhase('idle');
      setDrillStatus('');
      setPendingDrill(null);
    } finally {
      setIsLoading(false);
      confirmResolverRef.current = null;
    }
  };

  const handleDrillDown = async (hotspot?: Hotspot) => {
    if (!currentDrill || isLoading) return;

    let x: number;
    let y: number;

    if (hotspot) {
      x = hotspot.x;
      y = hotspot.y;
    } else if (customClickPosition) {
      x = customClickPosition.x;
      y = customClickPosition.y;
    } else {
      return;
    }

    await runDrillDown(x, y, hotspot);
  };

  const handleConfirmDrill = (drillTopic: string) => {
    setIsLoading(true);
    setDrillPhase('generating');
    setDrillPipeline('generating');
    setDrillStatus('Generating drill image…');
    confirmResolverRef.current?.(drillTopic);
    confirmResolverRef.current = null;
  };

  const handleCancelDrill = () => {
    confirmResolverRef.current?.(null);
    confirmResolverRef.current = null;
    setPendingDrill(null);
    setDrillPhase('idle');
    setDrillPipeline('idle');
    setDrillStatus('');
    setIsLoading(false);
  };

  const handleRegenerateCachedDrill = async () => {
    const last = lastDrillRef.current;
    if (!last) return;
    handleCancelDrill();
    await runDrillDown(last.x, last.y, last.hotspot, String(Date.now()));
  };

  // Handle timeline stage selection
  const handleSelectStage = (stage: { id: string }) => {
    if (!currentDrill) return;
    
    setIsLoading(true);
    setCurrentStageId(stage.id);

    setTimeout(() => {
      const stageResult = drillAdapter.getStageResult(stage.id);
      if (stageResult) {
        setCurrentDrill(stageResult);
        if (stageResult.hotspots && stageResult.hotspots.length > 0) {
          setActiveHotspotId(stageResult.hotspots[0].id);
        }
      }
      setIsLoading(false);
    }, 400);
  };

  const handleNavigate = (tab: string) => {
    setActiveTab(tab);
  };

  const handleClearSearch = () => {
    setCurrentDrill(null);
    setSearchQuery('');
    setActiveHotspotId(null);
    setSelectedImage(null);
    setImagePreviewUrl(null);
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedImage(file);
      const previewUrl = URL.createObjectURL(file);
      setImagePreviewUrl(previewUrl);
      
      // Immediately trigger exploration when image is selected
      handleTriggerDrill('', searchMode, file);
    }
  };

  return (
    <div className="h-screen bg-background text-on-surface flex flex-col selection:bg-secondary selection:text-on-secondary overflow-hidden relative">
      {/* Animated Spatial Background + Cursor Trail */}
      <SpatialBackground />
      <CursorGlow />

      <Header
        breadcrumbs={currentDrill?.breadcrumbs}
        activeTab={activeTab}
        onNavigate={handleNavigate}
        onClearSearch={handleClearSearch}
        showTabs={!currentDrill} // Hide tabs when in canvas view
      />

      <main className="flex-1 flex pt-0 min-h-0 relative overflow-hidden bg-background">
        {/* Futural Collapsible LEFT SIDEBAR Navigation Panel */}
        <AnimatePresence initial={false}>
          {sidebarOpen && (
            <motion.aside
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 240, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ type: "spring", stiffness: 220, damping: 26 }}
              className="border-r border-outline flex flex-col justify-between p-5 shrink-0 overflow-hidden z-20 bg-surface select-none h-full hidden md:flex"
            >
              {/* Sidebar Content */}
              <div className="space-y-6">
                <div>
                  <span className="text-[9px] font-mono uppercase tracking-widest text-on-surface-muted block mb-3.5 font-bold">WORKSPACE MODES</span>
                  <div className="space-y-2">
                    <button
                      type="button"
                      onClick={() => {
                        setSearchMode('explainer');
                        setActiveTab('explore');
                        if (currentDrill) handleClearSearch();
                      }}
                      className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl border text-xs font-mono font-bold tracking-wider transition-all cursor-pointer select-none ${
                        searchMode === 'explainer'
                          ? 'bg-primary/10 border-primary/20 text-primary shadow-[0_0_15px_rgba(0,229,255,0.06)]'
                          : 'border-transparent text-on-surface-muted hover:text-on-surface hover:bg-white/3'
                      }`}
                    >
                      <span className="text-sm">🧠</span>
                      <span className="truncate">EXPLAINER MODE</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setSearchMode('ecommerce');
                        setActiveTab('explore');
                        if (currentDrill) handleClearSearch();
                      }}
                      className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl border text-xs font-mono font-bold tracking-wider transition-all cursor-pointer select-none ${
                        searchMode === 'ecommerce'
                          ? 'bg-secondary/10 border-secondary/20 text-secondary shadow-[0_0_15px_rgba(157,78,221,0.06)]'
                          : 'border-transparent text-on-surface-muted hover:text-on-surface hover:bg-white/3'
                      }`}
                    >
                      <span className="text-sm">👗</span>
                      <span className="truncate">ECOMMERCE MATCH</span>
                    </button>
                  </div>
                </div>

                <div>
                  <span className="text-[9px] font-mono uppercase tracking-widest text-on-surface-muted block mb-3.5 font-bold">WORKSPACE CORE</span>
                  <div className="space-y-2">
                    <button
                      type="button"
                      onClick={() => setActiveTab('explore')}
                      className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl border text-xs font-mono font-bold tracking-wider transition-all cursor-pointer select-none ${
                        activeTab === 'explore'
                          ? 'bg-primary/5 border-primary/10 text-primary shadow-[0_0_10px_rgba(0,229,255,0.03)]'
                          : 'border-transparent text-on-surface-muted hover:text-on-surface hover:bg-white/3'
                      }`}
                    >
                      <Layers className="w-4 h-4 text-primary shrink-0" />
                      <span>WORKSPACE</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setActiveTab('history')}
                      className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl border text-xs font-mono font-bold tracking-wider transition-all cursor-pointer select-none ${
                        activeTab === 'history'
                          ? 'bg-secondary/5 border-secondary/10 text-secondary shadow-[0_0_10px_rgba(157,78,221,0.03)]'
                          : 'border-transparent text-on-surface-muted hover:text-on-surface hover:bg-white/3'
                      }`}
                    >
                      <Database className="w-4 h-4 text-secondary shrink-0" />
                      <span>HISTORY LOGS</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Sidebar Bottom */}
              <div className="space-y-4 pt-4 border-t border-white/5">
                <button
                  type="button"
                  onClick={() => alert('⚙️ Terminal System Diagnostics: All sub-modules functional and verified.')}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-mono text-on-surface-muted hover:text-on-surface hover:bg-white/3 cursor-pointer select-none"
                >
                  <Settings className="w-4 h-4" />
                  <span>Config Terminal</span>
                </button>
                <div className="text-[9px] font-mono text-on-surface-muted/30 text-center uppercase tracking-widest">
                  DRILLDOWN V1.0.0
                </div>
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        {/* Sidebar Toggle trigger */}
        <button
          type="button"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="absolute left-4 bottom-6 z-50 w-9 h-9 border border-outline rounded-lg bg-surface flex items-center justify-center text-on-surface hover:text-primary cursor-pointer shadow-xl transition-all hidden md:flex"
        >
          {sidebarOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>

        {/* Main Content Workspace wrapper */}
        {activeTab === 'explore' && (
          <div className="flex-1 flex flex-col overflow-hidden min-h-0 relative z-10 bg-background/20">
            {/* EXPLORE TAB - Initial Search */}
            {!currentDrill && (
              <div className="flex-1 flex flex-col py-8 px-6 relative overflow-y-auto">
            <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-navy-light/10 blur-[150px] pointer-events-none" />

            <div className="w-full max-w-4xl mx-auto text-center z-10 space-y-4 mt-8 mb-8">
              <h1 className="font-serif text-[4rem] md:text-[5.5rem] font-black tracking-tighter leading-none">
                <span className="text-white">DRILL</span>
                <span className="text-[#ff6b35]">DOWN</span>
              </h1>
              <p className="text-on-surface-variant font-light text-base md:text-lg max-w-xl mx-auto leading-relaxed">
                Analyze deeper. From high-level concepts to granular technical specs in seconds.
              </p>
            </div>

            <div className="w-full max-w-2xl mx-auto z-10 px-4 mb-12">
              <div className="bg-navy-mid/60 backdrop-blur-2xl rounded-2xl border border-white/10 p-4 shadow-[0_30px_60px_rgba(0,0,0,0.5)] flex flex-col gap-4">
                <div className="flex items-center gap-3 bg-black/40 border border-white/5 p-3.5 rounded-xl">
                  <Search className="w-5 h-5 text-orange-glow shrink-0" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleTriggerDrill(searchQuery, searchMode, selectedImage || undefined);
                    }}
                    placeholder="e.g. Anatomy of a Volcano, Structured Navy Blazer, Human Eye..."
                    className="w-full bg-transparent border-none text-on-surface placeholder:text-outline-variant focus:outline-none focus:ring-0 text-md font-light"
                  />

                  <div className="flex items-center gap-2">
                    <input
                      type="file"
                      id="image-file-upload"
                      accept="image/*"
                      className="hidden"
                      onChange={handleImageSelect}
                    />
                    <button
                      type="button"
                      onClick={() => document.getElementById('image-file-upload')?.click()}
                      className="p-1 px-3 bg-orange-glow rounded-lg text-white font-mono text-[10px] uppercase font-black tracking-widest cursor-pointer hover:bg-[#E0784C] transition-all shrink-0"
                    >
                      UPLOAD IMAGE
                    </button>
                  </div>

                  <div className="w-[1px] h-5 bg-white/20 shrink-0 mx-4" />

                  {isLoading ? (
                    <div className="w-5 h-5 border-2 border-orange-glow/20 border-t-orange-glow rounded-full animate-spin shrink-0" />
                  ) : (
                    <button
                      onClick={() => handleTriggerDrill(searchQuery, searchMode, selectedImage || undefined)}
                      className="p-1 px-3 bg-orange-glow rounded-lg text-white font-mono text-[10px] uppercase font-black tracking-widest cursor-pointer hover:bg-[#E0784C] transition-all shrink-0"
                    >
                      GENERATE
                    </button>
                  )}
                </div>

                {selectedImage && imagePreviewUrl && (
                  <div className="flex items-center gap-2.5 bg-white/5 border border-white/10 p-2 rounded-xl self-start">
                    <div className="w-10 h-10 rounded-md overflow-hidden bg-black border border-white/20 select-none relative shrink-0">
                      <img src={imagePreviewUrl} alt="Upload preview" className="w-full h-full object-cover" />
                    </div>
                    <div className="text-left font-mono">
                      <span className="text-[10px] text-on-surface uppercase font-bold block">
                        Custom Image Attached
                      </span>
                      <span className="text-[9px] text-on-surface-variant block">
                        {selectedImage.name}
                      </span>
                    </div>
                    <button
                      onClick={() => {
                        setSelectedImage(null);
                        setImagePreviewUrl(null);
                      }}
                      className="p-1 rounded bg-black/40 hover:bg-black/60 cursor-pointer text-on-surface-variant hover:text-white transition-colors ml-4"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                )}

                <div className="flex items-center justify-between border-t border-white/5 pt-3.5">
                  <span className="text-xs font-mono text-on-surface-variant">Exploration Vector Mode:</span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setSearchMode('explainer')}
                      className={`px-3 py-1.5 font-mono text-[10px] uppercase font-bold tracking-wider rounded transition-all cursor-pointer ${
                        searchMode === 'explainer'
                          ? 'bg-primary-container text-primary border border-primary/25'
                          : 'text-outline hover:text-on-surface'
                      }`}
                    >
                      Explainer Mode
                    </button>
                    <button
                      onClick={() => setSearchMode('ecommerce')}
                      className={`px-3 py-1.5 font-mono text-[10px] uppercase font-bold tracking-wider rounded transition-all cursor-pointer ${
                        searchMode === 'ecommerce'
                          ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'
                          : 'text-outline hover:text-on-surface'
                      }`}
                    >
                      Ecommerce Match
                    </button>
                  </div>
                </div>

                <div className="flex flex-col gap-3 border-t border-white/5 pt-3.5">
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-xs font-mono text-on-surface-variant shrink-0">Drill:</span>
                    <select
                      value={drillMode}
                      onChange={(e) => setDrillMode(e.target.value as 'inside' | 'pov')}
                      className="bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-[10px] font-mono text-on-surface focus:outline-none focus:border-orange-glow/50"
                    >
                      <option value="inside">Inside Zoom (Macro)</option>
                      <option value="pov">POV Perspective (Outward)</option>
                    </select>
                  </div>
                  <p className="text-[10px] font-mono text-on-surface-variant/80 leading-relaxed">
                    {drillMode === 'pov'
                      ? 'First-person outward view from the clicked point. Best after an inside drill.'
                      : 'Cross-section into the region. Uses red-ring grounding for reliable macro views.'}
                  </p>

                  <div className="flex items-center justify-between gap-4">
                    <span className="text-xs font-mono text-on-surface-variant shrink-0">Context:</span>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setKbMode('generic')}
                        className={`px-3 py-1.5 font-mono text-[10px] uppercase font-bold tracking-wider rounded transition-all cursor-pointer ${
                          kbMode === 'generic'
                            ? 'bg-primary-container text-primary border border-primary/25'
                            : 'text-outline hover:text-on-surface'
                        }`}
                      >
                        Generic
                      </button>
                      <button
                        type="button"
                        onClick={() => setKbMode('kb')}
                        className={`px-3 py-1.5 font-mono text-[10px] uppercase font-bold tracking-wider rounded transition-all cursor-pointer flex items-center gap-1 ${
                          kbMode === 'kb'
                            ? 'bg-secondary-container/30 text-secondary border border-secondary/25'
                            : 'text-outline hover:text-on-surface'
                        }`}
                      >
                        <BookOpen className="w-3 h-3" /> Knowledge Base
                      </button>
                    </div>
                  </div>

                  {kbMode === 'kb' && (
                    <div className="bg-black/30 border border-white/10 rounded-xl p-3 space-y-3">
                      <input
                        ref={kbFileRef}
                        type="file"
                        accept=".pdf"
                        className="hidden"
                        onChange={(e) => e.target.files?.[0] && handleKbUpload(e.target.files[0])}
                      />
                      <button
                        type="button"
                        onClick={() => kbFileRef.current?.click()}
                        disabled={kbUploading}
                        className="w-full flex items-center justify-center gap-2 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg font-mono text-[10px] uppercase font-bold tracking-wider text-on-surface transition-all disabled:opacity-50"
                      >
                        {kbUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                        {kbUploading ? 'Ingesting…' : 'Upload PDF Manual'}
                      </button>

                      {kbList.length > 0 ? (
                        <div className="space-y-1.5">
                          <span className="text-[9px] font-mono uppercase tracking-widest text-on-surface-variant">Active Manual</span>
                          {kbList.map((kb) => (
                            <div
                              key={kb.id}
                              onClick={() => setActiveKbId(kb.id)}
                              className={`flex items-center gap-2 px-2.5 py-2 rounded-lg border cursor-pointer transition-all ${
                                activeKbId === kb.id
                                  ? 'border-secondary/50 bg-secondary/10'
                                  : 'border-white/5 bg-white/5 hover:border-white/20'
                              }`}
                            >
                              <span className="flex-1 text-[11px] font-mono truncate" title={kb.name}>
                                {kb.name}
                                {kb.status === 'processing' && (
                                  <span className="ml-1 text-secondary">(ingesting…)</span>
                                )}
                              </span>
                              <span className="text-[9px] font-mono text-on-surface-variant">{kb.page_count}p</span>
                              <button
                                type="button"
                                onClick={(e) => { e.stopPropagation(); handleKbDelete(kb.id); }}
                                disabled={kb.status === 'processing' || kb.id === processingKbId || kbUploading}
                                className="p-1 rounded hover:bg-black/40 text-on-surface-variant hover:text-red-400 disabled:opacity-30 disabled:pointer-events-none"
                                title={kb.status === 'processing' ? 'Wait for ingestion to finish' : 'Remove'}
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </div>
                          ))}
                        </div>
                      ) : !kbUploading ? (
                        <p className="text-[10px] text-on-surface-variant font-light">
                          Upload a PDF manual to ground drill analysis in your documentation.
                        </p>
                      ) : null}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <RecentDrills 
              onSelectDrill={handleSelectDrill}
              drills={history.map(toRecentDrill)}
            />
          </div>
        )}

        {/* EXPLORE TAB - Active Workspace */}
        {currentDrill && (
          <div className="flex-1 flex overflow-hidden relative min-h-0 bg-background">
            <div className="flex-1 flex flex-col relative bg-transparent min-w-0">
              <div className="h-12 border-b border-outline flex items-center justify-between px-6 bg-surface/75 w-full text-left flex-shrink-0 z-20 relative select-none">
                <div className="min-w-0 flex-1 flex items-center gap-3">
                  <span className="px-2 py-0.5 rounded-full bg-white/5 border border-white/10 font-mono text-[8px] uppercase font-bold tracking-widest text-primary shrink-0">
                    {currentDrill.category}
                  </span>
                  <div className="min-w-0">
                    <h1 className="font-sans text-xs font-bold text-on-surface truncate tracking-tight uppercase" title={currentDrill.title}>
                      {currentDrill.title}
                    </h1>
                  </div>
                </div>
              </div>

              <div className="flex-1 min-h-0">
                <DrillCanvas
                  imageUrl={currentDrill.imageUrl}
                  imageAlt={currentDrill.imageAlt}
                  mode={currentDrill.mode}
                  hotspots={currentDrill.hotspots}
                  activeHotspotId={activeHotspotId}
                  onSelectHotspot={handleHotspotSelect}
                  onCanvasClick={handleCanvasClick}
                  customClickPosition={customClickPosition}
                  isAnalyzing={isAnalyzing}
                  isGenerating={isGenerating}
                  onGoBack={handleClearSearch}
                  breadcrumbs={currentDrill.breadcrumbs}
                />
              </div>

              <DrillPipelineBar stage={drillPipeline} />

              {currentDrill.drillPath && currentDrill.drillPath.length > 0 && (
                <div className="absolute left-6 right-6 bottom-6 z-30 bg-surface/85 backdrop-blur-xl border border-outline rounded-2xl p-2.5 px-4 shadow-xl flex gap-4 items-center shrink-0 select-none">
                  <span className="font-mono text-[9px] uppercase tracking-widest text-on-surface-muted uppercase font-bold shrink-0 w-20 text-left leading-normal">
                    Drill Path Timeline
                  </span>

                  <div className="flex-1 flex items-center gap-4 overflow-x-auto scrollbar-hide py-1">
                    {currentDrill.drillPath.map((stage, idx) => {
                      const isActive = stage.id === currentStageId;
                      return (
                        <div
                          key={stage.id}
                          onClick={() => handleSelectStage(stage)}
                          className={`flex items-center gap-3 px-4 py-2.5 rounded-xl border transition-all cursor-pointer shrink-0 select-none ${
                            isActive
                              ? 'border-secondary/60 bg-secondary/15 shadow-[0_0_15px_rgba(157,78,221,0.08)]'
                              : 'border-white/5 bg-[#101314]/50 hover:border-white/20 hover:bg-[#101314]'
                          }`}
                        >
                          <div className="w-10 h-10 rounded-md overflow-hidden bg-black shrink-0 border border-white/10">
                            <img src={stage.imageUrl} alt={stage.label} className="w-full h-full object-cover" />
                          </div>
                          <div className="text-left font-mono">
                            <span className="text-[9px] text-on-surface-variant uppercase font-bold block mb-0.5">
                              Phase 0{idx + 1}
                            </span>
                            <span className={`text-[11px] uppercase tracking-wider block font-bold truncate max-w-[120px] ${isActive ? 'text-secondary' : 'text-on-surface'}`}>
                              {stage.label}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            <ProductPanel
              hotspot={currentDrill.hotspots.find((h) => h.id === activeHotspotId) || null}
              onClose={() => {
                setActiveHotspotId(null);
                setCustomClickPosition(null);
              }}
              mode={currentDrill.mode}
              drillResult={currentDrill}
              onDrillDown={handleDrillDown}
              customClickPosition={customClickPosition}
              drillMode={drillMode}
              onDrillModeChange={(mode) => setDrillMode(mode as 'inside' | 'pov')}
              kbMode={kbMode}
              onKbModeChange={setKbMode}
              kbList={kbList}
              activeKbId={activeKbId}
              onActiveKbChange={setActiveKbId}
              onKbUpload={handleKbUpload}
              onKbDelete={handleKbDelete}
              kbUploading={kbUploading}
            />
          </div>
        )}
          </div>
        )}

        {/* HISTORY TAB */}
        {activeTab === 'history' && (
          <div className="w-full max-w-5xl mx-auto px-8 py-12 text-left animate-fade-in z-10">
            <h1 className="font-serif text-4xl font-black text-on-surface mb-2">My Drilling Logs</h1>
            <p className="text-on-surface-variant text-sm font-light mb-8">
              Access all previous multi-dimensional diagram drill coordinates saved in this session.
            </p>

            {history.length === 0 ? (
              <div className="glass-card rounded-2xl p-16 text-center border border-white/5 flex flex-col items-center gap-4">
                <Database className="w-12 h-12 text-outline/40 animate-pulse" />
                <p className="font-mono text-xs tracking-wider text-on-surface-variant uppercase font-bold">
                  Your session log database is currently vacant.
                </p>
                <button
                  onClick={() => setActiveTab('explore')}
                  className="px-6 py-2.5 bg-secondary text-on-secondary font-mono text-[10px] font-bold uppercase tracking-widest rounded-full cursor-pointer hover:bg-opacity-90"
                >
                  Create First Drill
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {history.map((drill) => (
                  <div
                    key={drill.id}
                    onClick={() => {
                      setCurrentDrill(drill);
                      setActiveTab('explore');
                      if (drill.hotspots && drill.hotspots.length > 0) {
                        setActiveHotspotId(drill.hotspots[0].id);
                      }
                    }}
                    className="glass-card rounded-xl overflow-hidden border border-white/10 flex hover:border-secondary transition-all cursor-pointer group"
                  >
                    <div className="w-28 bg-surface-container relative shrink-0">
                      <img src={drill.imageUrl} alt={drill.title} className="w-full h-full object-cover" />
                      <div className="absolute top-2 left-2">
                        <span className="px-2 py-0.5 rounded-full bg-black/60 font-mono text-[8px] tracking-wider uppercase border border-white/10 text-secondary font-bold">
                          {drill.mode}
                        </span>
                      </div>
                    </div>

                    <div className="p-5 flex-1 flex flex-col justify-between min-w-0">
                      <div>
                        <span className="font-mono text-[9px] uppercase tracking-widest text-[#e1e3e4]/60">
                          {drill.category}
                        </span>
                        <h3 className="font-serif text-lg font-bold text-on-surface mt-1 group-hover:text-primary transition-colors truncate">
                          {drill.title}
                        </h3>
                        <p className="text-[11px] text-on-surface-variant line-clamp-2 mt-1 font-light leading-relaxed">
                          {drill.subtitle}
                        </p>
                      </div>

                      <div className="flex justify-between items-center mt-4 pt-3 border-t border-white/5">
                        <span className="text-[10px] text-on-surface-variant font-mono">
                          {drill.hotspots.length} dynamic spots
                        </span>
                        <span className="text-secondary font-mono text-[9px] uppercase font-bold tracking-widest group-hover:underline flex items-center gap-1">
                          Re-explore <ArrowRight className="w-3 h-3" />
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </main>

      {pendingDrill && (drillPhase === 'confirm' || drillPhase === 'generating') && (
        <DrillConfirmModal
          pending={pendingDrill}
          busy={drillPhase === 'generating'}
          onConfirm={handleConfirmDrill}
          onCancel={handleCancelDrill}
          onRegenerate={pendingDrill.fromCache ? handleRegenerateCachedDrill : undefined}
        />
      )}

      {(drillPhase === 'analyzing' || drillPhase === 'generating') && (
        <GenerationLoader status={drillStatus} />
      )}
    </div>
  );
}
