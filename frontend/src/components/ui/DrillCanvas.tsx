import React, { useState, useRef, useCallback, useEffect } from 'react';
import { ArrowLeft, RefreshCw, ZoomIn, ZoomOut, Cpu, Eye, MapPin } from 'lucide-react';
import { Hotspot, Mode } from '../../types';
import { mapNormalizedToDisplay, normalizeContainedImageClick } from '../../utils/coords';

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
  onSelectHotspot,
  onCanvasClick,
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

  /** Map normalized image coords (0–1) to overlay pixel position (object-fit: contain). */
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

    // Parent expects 0–100 percentages aligned to full image (not letterbox container)
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
    }, 600);
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
    <div className="w-full h-full flex items-center justify-center p-6 relative select-none overflow-hidden">
      <div
        ref={wrapRef}
        onClick={handleCanvasClick}
        className="relative w-full h-full max-w-[1100px] max-h-full min-h-[280px] bg-surface-container-lowest shadow-[0_40px_80px_rgba(0,0,0,0.4)] rounded-xl overflow-hidden border border-orange-glow/10 group cursor-crosshair transition-all"
      >
        {analyzing && (
          <div className="absolute inset-0 bg-background/30 pointer-events-none z-[100]" />
        )}
        <div
          className="relative w-full h-full"
          style={{
            transform: `scale(${zoom}) translate(${offset.x}px, ${offset.y}px)`,
          }}
        >
          <img
            ref={imgRef}
            src={imageUrl}
            alt={imageAlt}
            className="w-full h-full object-contain select-none pointer-events-none"
            draggable={false}
            onLoad={updateDims}
          />

          {/* Hotspot + marker overlay — shares zoom transform with image */}
          <div className="absolute inset-0 pointer-events-none">
            {activeDisplay && !blockClicks && (
              <div
                className="absolute rounded-full bg-orange-glow/10 blur-[45px] transition-all duration-500"
                style={{
                  left: `${activeDisplay.x}px`,
                  top: `${activeDisplay.y}px`,
                  transform: 'translate(-50%, -50%)',
                  width: '260px',
                  height: '260px',
                }}
              />
            )}

            {ripples.map((ripple) => (
              <span
                key={ripple.id}
                className="absolute bg-white/30 rounded-full animate-ping pointer-events-none"
                style={{
                  left: `${ripple.x}px`,
                  top: `${ripple.y}px`,
                  width: '80px',
                  height: '80px',
                  transform: 'translate(-50%, -50%)',
                  animationDuration: '600ms',
                }}
              />
            ))}

            {!blockClicks &&
              hotspots.map((spot) => {
                const isActive = spot.id === activeHotspotId;
                const { x: px, y: py } = toDisplay(spot.x / 100, spot.y / 100);

                if (mode === 'ecommerce') {
                  return (
                    <div
                      key={spot.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectHotspot(spot.id);
                      }}
                      className={`absolute rounded-xl border transition-all cursor-pointer z-40 p-2 flex flex-col justify-end pointer-events-auto ${
                        isActive
                          ? 'border-orange-glow bg-orange-glow/10 shadow-[0_0_15px_rgba(255,140,66,0.35)]'
                          : 'border-white/20 border-dashed bg-black/10 hover:border-primary/60 hover:bg-white/5'
                      }`}
                      style={{
                        left: `${px}px`,
                        top: `${py}px`,
                        width: spot.width ? `${spot.width}px` : '60px',
                        height: spot.height ? `${spot.height}px` : '80px',
                        transform: 'translate(-50%, -50%)',
                      }}
                    >
                      <div className="flex justify-between items-center bg-black/60 backdrop-blur-md px-1.5 py-0.5 rounded border border-white/5">
                        <span className="text-[9px] font-bold text-on-surface truncate tracking-tight uppercase">
                          {spot.title}
                        </span>
                      </div>
                      {isActive && (
                        <div className="absolute top-[3px] right-[3px] w-2.5 h-2.5 bg-orange-glow rounded-full animate-ping pointer-events-none" />
                      )}
                    </div>
                  );
                }

                return (
                  <div
                    key={spot.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectHotspot(spot.id);
                    }}
                    style={{
                      left: `${px}px`,
                      top: `${py}px`,
                      transform: 'translate(-50%, -50%)',
                    }}
                    className="absolute z-40 p-3 group/indicator cursor-pointer pointer-events-auto"
                  >
                    {isActive ? (
                      <div className="relative w-14 h-14 flex items-center justify-center">
                        <div className="absolute w-14 h-14 rounded-full border-2 border-orange-glow/50 pulse-ring-custom pointer-events-none" />
                        <div className="w-4 h-4 bg-orange-glow rounded-full shadow-[0_0_15px_rgba(255,140,66,0.9)] z-10" />
                      </div>
                    ) : (
                      <div className="relative w-10 h-10 flex items-center justify-center hover:scale-110 transition-transform">
                        <div className="absolute w-10 h-10 rounded-full border border-primary/30 group-hover/indicator:border-primary/85 transition-colors" />
                        <div className="w-2.5 h-2.5 bg-primary/80 rounded-full group-hover/indicator:bg-primary transition-colors" />
                      </div>
                    )}

                    <div className="absolute top-12 left-1/2 -translate-x-1/2 w-56 p-3 bg-navy-mid/95 backdrop-blur-md border border-outline-variant/30 rounded-lg shadow-2xl opacity-0 group-hover/indicator:opacity-100 group-hover/indicator:translate-y-1 transition-all duration-300 pointer-events-none z-50 text-left">
                      <h4 className="font-mono text-xs font-bold text-secondary mb-1">{spot.title}</h4>
                      <p className="text-[11px] text-on-surface-variant flex gap-1 items-center leading-relaxed mb-2">
                        <Eye className="w-3 h-3 text-secondary shrink-0" />
                        <span className="line-clamp-2">{spot.description}</span>
                      </p>
                      <p className="text-[9px] text-orange-glow/80 font-mono flex gap-1 items-center">
                        <MapPin className="w-3 h-3 shrink-0" />
                        Position: {spot.x.toFixed(1)}%, {spot.y.toFixed(1)}%
                      </p>
                    </div>
                  </div>
                );
              })}

            {!blockClicks && customDisplay && (
              <div
                style={{
                  left: `${customDisplay.x}px`,
                  top: `${customDisplay.y}px`,
                  transform: 'translate(-50%, -50%)',
                }}
                className="absolute z-50 p-3 group/custom cursor-pointer pointer-events-auto"
              >
                <div className="relative w-14 h-14 flex items-center justify-center">
                  <div className="absolute w-14 h-14 rounded-full border-2 border-orange-glow/50 pulse-ring-custom pointer-events-none" />
                  <div className="w-4 h-4 bg-orange-glow rounded-full shadow-[0_0_15px_rgba(255,140,66,0.9)] z-10" />
                </div>
                <div className="absolute top-12 left-1/2 -translate-x-1/2 w-56 p-3 bg-navy-mid/95 backdrop-blur-md border border-outline-variant/30 rounded-lg shadow-2xl opacity-0 group-hover/custom:opacity-100 group-hover/custom:translate-y-1 transition-all duration-300 pointer-events-none z-50 text-left">
                  <h4 className="font-mono text-xs font-bold text-secondary mb-1">Custom Position</h4>
                  <p className="text-[11px] text-on-surface-variant leading-relaxed mb-2">
                    Click &quot;Generate Drilldown&quot; to explore this area
                  </p>
                  <p className="text-[9px] text-orange-glow/80 font-mono flex gap-1 items-center">
                    <MapPin className="w-3 h-3 shrink-0" />
                    Position: {customClickPosition!.x.toFixed(1)}%, {customClickPosition!.y.toFixed(1)}%
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {generating && (
          <div className="absolute inset-0 bg-background/60 backdrop-blur-[4px] flex flex-col items-center justify-center z-[500] animate-fade-in pointer-events-none">
            <div className="bg-navy-mid/95 backdrop-blur-xl border border-orange-glow/30 px-8 py-6 rounded-2xl flex flex-col items-center gap-3 shadow-2xl">
              <Cpu className="w-8 h-8 text-orange-glow animate-pulse" />
              <p className="font-mono text-sm tracking-wide text-orange-glow">
                Rendering next layer…
              </p>
            </div>
          </div>
        )}

        {!blockClicks && hotspots.length === 0 && (
          <div className="absolute top-6 right-6 bg-navy-mid/90 backdrop-blur-xl border border-orange-glow/30 px-4 py-2 rounded-xl flex items-center gap-2 shadow-2xl z-40 animate-pulse">
            <div className="w-2 h-2 bg-orange-glow rounded-full animate-ping" />
            <p className="font-mono text-[10px] tracking-wider text-secondary uppercase font-bold">
              Generating Labels...
            </p>
          </div>
        )}

        <div className="absolute right-6 top-1/2 -translate-y-1/2 flex flex-col gap-3 z-40">
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleReset();
            }}
            className="w-12 h-12 rounded-full bg-surface-container-high/80 backdrop-blur-md border border-outline-variant/20 flex items-center justify-center text-primary hover:text-orange-glow hover:bg-surface-container-highest transition-all shadow-lg cursor-pointer hover:scale-105 active:scale-95 group"
            title="Reset View"
          >
            <RefreshCw className="w-5 h-5 group-hover:rotate-180 transition-transform duration-500" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleZoomIn();
            }}
            className="w-12 h-12 rounded-full bg-surface-container-high/80 backdrop-blur-md border border-outline-variant/20 flex items-center justify-center text-primary hover:text-secondary transition-all shadow-lg cursor-pointer hover:scale-105 active:scale-95"
            title="Zoom In"
          >
            <ZoomIn className="w-5 h-5" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleZoomOut();
            }}
            className="w-12 h-12 rounded-full bg-surface-container-high/80 backdrop-blur-md border border-outline-variant/20 flex items-center justify-center text-primary hover:text-secondary transition-all shadow-lg cursor-pointer hover:scale-105 active:scale-95"
            title="Zoom Out"
          >
            <ZoomOut className="w-5 h-5" />
          </button>
        </div>

        <div className="absolute left-6 top-6 z-40">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onGoBack();
            }}
            className="flex items-center gap-2 px-4 py-2 rounded-full bg-surface-container-high/75 backdrop-blur-md border border-outline-variant/30 text-on-surface hover:text-secondary hover:bg-surface-container-highest transition-all shadow-lg hover:scale-105 active:scale-95 cursor-pointer text-xs font-bold tracking-widest uppercase font-mono"
          >
            <ArrowLeft className="w-4 h-4 text-secondary" />
            <span>{breadcrumbs && breadcrumbs.length > 1 ? breadcrumbs[breadcrumbs.length - 2] : 'Explore'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
