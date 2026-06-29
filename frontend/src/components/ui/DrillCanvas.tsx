import React, { useState, useRef, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, RefreshCw, ZoomIn, ZoomOut, Eye, MapPin, Scan, Sliders, ShieldCheck } from 'lucide-react';
import { Hotspot, Mode } from '../../types';
import { mapNormalizedToDisplay, normalizeContainedImageClick } from '../../utils/coords';
import { CanvasToolbar } from './core_components';

interface DrillCanvasProps {
  imageUrl: string;
  imageAlt: string;
  mode: Mode;
  hotspots: Hotspot[];
  activeHotspotId: string | null;
  onSelectHotspot: (id: string) => void;
  onCanvasClick: (x: number, y: number) => void;
  customClickPosition: { x: number; y: number } | null;
  isAnalyzing?: boolean;
  isGenerating?: boolean;
  /** @deprecated use isAnalyzing / isGenerating */
  isLoading?: boolean;
  onGoBack: () => void;
  breadcrumbs: string[];
}

export default function DrillCanvas({
  imageUrl,
  imageAlt,
  mode,
  hotspots,
  activeHotspotId,
  onCanvasClick,
  onSelectHotspot,
  customClickPosition,
  isAnalyzing = false,
  isGenerating = false,
  isLoading = false,
  onGoBack,
  breadcrumbs,
}: DrillCanvasProps) {
  const analyzing = isAnalyzing || (isLoading && !isGenerating);
  const generating = isGenerating;
  const blockClicks = analyzing || generating;
  
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [ripples, setRipples] = useState<Array<{ id: number; x: number; y: number }>>([]);
  const [hoveredHotspot, setHoveredHotspot] = useState<string | null>(null);
  
  const wrapRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const rippleIdCounter = useRef(0);
  const [dims, setDims] = useState({ width: 0, height: 0, naturalWidth: 0, naturalHeight: 0 });

  const updateDims = useCallback(() => {
    const wrap = wrapRef.current;
    const img = imgRef.current;
    if (!wrap) return;
    setDims({
      width: wrap.clientWidth,
      height: wrap.clientHeight,
      naturalWidth: img?.naturalWidth ?? 0,
      naturalHeight: img?.naturalHeight ?? 0,
    });
  }, []);

  useEffect(() => {
    updateDims();
    window.addEventListener('resize', updateDims);
    return () => window.removeEventListener('resize', updateDims);
  }, [imageUrl, updateDims]);

  /** Map normalized image coords (0–1) to display overlay coordinates. */
  const toDisplay = useCallback(
    (nx: number, ny: number) =>
      mapNormalizedToDisplay(
        nx,
        ny,
        dims.width,
        dims.height,
        dims.naturalWidth,
        dims.naturalHeight,
      ),
    [dims],
  );

  const handleCanvasClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!wrapRef.current || blockClicks) return;
    const img = imgRef.current;
    if (!img || !img.naturalWidth) return;

    const coords = normalizeContainedImageClick(e.clientX, e.clientY, img, { clamp: true });
    if (!coords) return;

    onCanvasClick(coords.x * 100, coords.y * 100);

    const display = toDisplay(coords.x, coords.y);
    const newRipple = {
      id: rippleIdCounter.current++,
      x: display.x,
      y: display.y,
    };

    setRipples((prev) => [...prev, newRipple]);
    setTimeout(() => {
      setRipples((prev) => prev.filter((r) => r.id !== newRipple.id));
    }, 700);
  };

  const handleZoomIn = () => setZoom((z) => Math.min(z + 0.25, 2.5));
  const handleZoomOut = () => setZoom((z) => Math.max(z - 0.25, 1));
  const handleReset = () => {
    setZoom(1);
    setOffset({ x: 0, y: 0 });
  };

  const activeHotspot = hotspots.find((h) => h.id === activeHotspotId);
  const activeDisplay = activeHotspot
    ? toDisplay(activeHotspot.x / 100, activeHotspot.y / 100)
    : null;

  const customDisplay = customClickPosition
    ? toDisplay(customClickPosition.x / 100, customClickPosition.y / 100)
    : null;

  return (
    <div className="w-full h-full flex flex-col items-center justify-center p-6 relative select-none overflow-hidden bg-background">
      {/* Absolute Glow Background Grid */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.01)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.01)_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none opacity-40" />

      {/* Outer Spatial Containment Frame */}
      <div
        ref={wrapRef}
        onClick={handleCanvasClick}
        className="relative w-full h-full max-w-[1200px] bg-[#020306]/80 backdrop-blur-2xl shadow-[0_30px_100px_rgba(0,0,0,0.8)] rounded-3xl overflow-hidden border border-outline group cursor-crosshair transition-all"
      >
        {/* Analyzing Overlay Cover */}
        {analyzing && (
          <div className="absolute inset-0 bg-background/50 backdrop-blur-[2px] pointer-events-none z-[10] flex items-center justify-center animate-fade-in">
            <div className="flex items-center gap-3 bg-black/60 border border-primary/20 px-5 py-3 rounded-2xl shadow-xl">
              <div className="w-4 h-4 border-2 border-primary/20 border-t-primary rounded-full animate-spin" />
              <span className="font-mono text-xs uppercase tracking-widest text-primary font-bold">Scanning coordinates...</span>
            </div>
          </div>
        )}

        {/* Scaled/Panned Interactive Layer */}
        <motion.div
          className="relative w-full h-full flex items-center justify-center"
          animate={{
            scale: zoom,
            x: offset.x,
            y: offset.y,
          }}
          transition={{ type: "spring", stiffness: 220, damping: 26 }}
        >
          <img
            ref={imgRef}
            src={imageUrl}
            alt={imageAlt}
            className="w-full h-full object-contain select-none pointer-events-none rounded-2xl"
            draggable={false}
            onLoad={updateDims}
          />

          {/* Interactive Core Targets Overlay */}
          <div className="absolute inset-0 pointer-events-none">
            {/* Soft Ambient Gloving Spot behind Active Area */}
            {activeDisplay && !blockClicks && (
              <motion.div
                layoutId="activeGlow"
                className="absolute rounded-full bg-primary/5 blur-[50px] pointer-events-none"
                style={{
                  left: `${activeDisplay.x}px`,
                  top: `${activeDisplay.y}px`,
                  transform: 'translate(-50%, -50%)',
                  width: '320px',
                  height: '320px',
                }}
              />
            )}

            {/* Tap Ripples */}
            {ripples.map((ripple) => (
              <motion.span
                key={ripple.id}
                initial={{ scale: 0.1, opacity: 0.8 }}
                animate={{ scale: 1.5, opacity: 0 }}
                transition={{ duration: 0.7, ease: "easeOut" }}
                className="absolute border border-primary rounded-full pointer-events-none"
                style={{
                  left: `${ripple.x}px`,
                  top: `${ripple.y}px`,
                  width: '90px',
                  height: '90px',
                  transform: 'translate(-50%, -50%)',
                }}
              />
            ))}

            {/* AI Hotspot Marks */}
            {!blockClicks &&
              hotspots.map((spot) => {
                const isActive = spot.id === activeHotspotId;
                const isHovered = spot.id === hoveredHotspot;
                const { x: px, y: py } = toDisplay(spot.x / 100, spot.y / 100);

                if (mode === 'ecommerce') {
                  return (
                    <motion.div
                      key={spot.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectHotspot(spot.id);
                      }}
                      onMouseEnter={() => setHoveredHotspot(spot.id)}
                      onMouseLeave={() => setHoveredHotspot(null)}
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ type: "spring", stiffness: 300, damping: 20 }}
                      className={`absolute rounded-2xl border transition-all cursor-pointer z-40 p-2.5 flex flex-col justify-end pointer-events-auto ${
                        isActive
                          ? 'border-primary bg-primary/10 shadow-[0_0_20px_rgba(0,229,255,0.25)]'
                          : 'border-white/10 border-dashed bg-black/30 hover:border-primary/50 hover:bg-white/5'
                      }`}
                      style={{
                        left: `${px}px`,
                        top: `${py}px`,
                        width: spot.width ? `${spot.width}px` : '70px',
                        height: spot.height ? `${spot.height}px` : '90px',
                        transform: 'translate(-50%, -50%)',
                      }}
                    >
                      <div className="flex justify-between items-center bg-[#05070D]/80 backdrop-blur-md px-2 py-1 rounded-lg border border-white/5">
                        <span className="text-[9px] font-mono font-bold text-on-surface truncate tracking-tight uppercase">
                          {spot.title}
                        </span>
                      </div>
                      {isActive && (
                        <div className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-primary rounded-full ai-pulse-ring" />
                      )}
                    </motion.div>
                  );
                }

                // Explainer Mode Hotspot Marks (Connected spatial points)
                return (
                  <div
                    key={spot.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectHotspot(spot.id);
                    }}
                    onMouseEnter={() => setHoveredHotspot(spot.id)}
                    onMouseLeave={() => setHoveredHotspot(null)}
                    style={{
                      left: `${px}px`,
                      top: `${py}px`,
                      transform: 'translate(-50%, -50%)',
                    }}
                    className="absolute z-40 p-4 group/indicator cursor-pointer pointer-events-auto"
                  >
                    {/* Glowing spatial node rings — every predicted spot renders in
                        the prominent "active" style so all hotspots are equally visible. */}
                    <div className="relative flex items-center justify-center">
                      <div className="w-14 h-14 flex items-center justify-center hover:scale-110 transition-transform duration-300">
                        <div className="absolute w-12 h-12 rounded-full bg-primary/10 border border-primary/40 ai-pulse-ring pointer-events-none" />
                        {/* Selected spot gets a solid inner ring; the rest a slightly softer one. */}
                        <div className={`absolute w-6 h-6 rounded-full border ${isActive ? 'border-primary' : 'border-primary/70'}`} />
                        <div className="w-2.5 h-2.5 bg-primary rounded-full shadow-[0_0_15px_#00E5FF] z-10" />
                      </div>
                    </div>

                    {/* Glowing AI Floating Hover Card */}
                    <AnimatePresence>
                      {(isHovered || isActive) && (
                        <motion.div
                          initial={{ opacity: 0, y: 15, scale: 0.95 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: 10, scale: 0.95 }}
                          transition={{ duration: 0.25, ease: "easeOut" }}
                          className="absolute top-14 left-1/2 -translate-x-1/2 w-64 p-3 bg-background/95 backdrop-blur-xl border border-outline rounded-2xl shadow-3xl z-50 text-left pointer-events-none"
                        >
                          <div className="flex items-center gap-1.5 mb-1">
                            <span className="w-1 h-1 rounded-full bg-primary" />
                            <h4 className="font-sans text-xs font-bold text-on-surface uppercase tracking-wide">{spot.title}</h4>
                          </div>
                          
                          <p className="text-[10px] text-on-surface-muted flex gap-1.5 leading-relaxed mb-2 font-sans">
                            <Eye className="w-3.5 h-3.5 text-primary shrink-0 mt-0.5" />
                            <span className="line-clamp-2">{spot.description}</span>
                          </p>

                          <div className="flex items-center justify-between border-t border-white/5 pt-2">
                            <span className="text-[8px] text-primary/80 font-mono uppercase tracking-widest flex items-center gap-1">
                              <Scan className="w-3 h-3" /> CLICK TO EXPLORE
                            </span>
                            <span className="text-[8px] text-on-surface-muted font-mono">
                              X:{spot.x.toFixed(0)} Y:{spot.y.toFixed(0)}
                            </span>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })}

            {/* Custom Tap Target Marker */}
            {!blockClicks && customDisplay && (
              <div
                style={{
                  left: `${customDisplay.x}px`,
                  top: `${customDisplay.y}px`,
                  transform: 'translate(-50%, -50%)',
                }}
                className="absolute z-50 p-4 group/custom cursor-pointer pointer-events-auto"
              >
                <div className="relative w-14 h-14 flex items-center justify-center">
                  <div className="absolute w-12 h-12 rounded-full border border-accent-pink/40 ai-pulse-ring pointer-events-none" />
                  <div className="absolute w-6 h-6 rounded-full border border-accent-pink/80" />
                  <div className="w-2.5 h-2.5 bg-accent-pink rounded-full shadow-[0_0_15px_#FF007A] z-10 animate-ping" />
                </div>
                <div className="absolute top-14 left-1/2 -translate-x-1/2 w-64 p-3 bg-background/95 backdrop-blur-xl border border-outline rounded-2xl shadow-3xl z-50 text-left pointer-events-none">
                  <h4 className="font-sans text-xs font-bold text-accent-pink uppercase tracking-wide mb-1">Target Coordinates</h4>
                  <p className="text-[10px] text-on-surface-muted leading-relaxed mb-2 font-sans">
                    Tap &quot;Generate Drilldown&quot; to inspect this granular section
                  </p>
                  <div className="flex justify-between items-center border-t border-white/5 pt-2">
                    <span className="text-[8px] text-accent-pink font-mono uppercase tracking-widest">READY FOR DEPTH ANALYSIS</span>
                    <span className="text-[8px] text-on-surface-muted font-mono">
                      X:{customClickPosition!.x.toFixed(0)} Y:{customClickPosition!.y.toFixed(0)}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </motion.div>

        {/* Hotspots empty loader/tag */}
        {!blockClicks && hotspots.length === 0 && (
          <div className="absolute top-6 right-6 bg-background/85 backdrop-blur-md border border-primary/20 px-3.5 py-2 rounded-xl flex items-center gap-2 shadow-2xl z-40 animate-pulse">
            <div className="w-1.5 h-1.5 bg-primary rounded-full animate-ping" />
            <p className="font-mono text-[9px] tracking-wider text-primary uppercase font-bold">
              Extracting Labels...
            </p>
          </div>
        )}

        {/* Back navigation controller */}
        <div className="absolute left-6 top-6 z-40">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onGoBack();
            }}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-background/60 backdrop-blur-md border border-white/5 text-on-surface hover:text-primary hover:border-primary/20 hover:bg-[#05070D]/90 transition-all shadow-xl hover:scale-102 active:scale-98 cursor-pointer text-[10px] font-bold tracking-widest uppercase font-mono"
          >
            <ArrowLeft className="w-3.5 h-3.5 text-primary" />
            <span>{breadcrumbs && breadcrumbs.length > 1 ? breadcrumbs[breadcrumbs.length - 2] : 'Back'}</span>
          </button>
        </div>

        {/* Canvas Toolbar Integration */}
        <CanvasToolbar
          onZoomIn={handleZoomIn}
          onZoomOut={handleZoomOut}
          onReset={handleReset}
        />
      </div>
    </div>
  );
}
