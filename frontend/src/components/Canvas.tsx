import React, { useEffect, useMemo, useRef, useState } from 'react';

interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface AnchorPoint {
  x: number;
  y: number;
}

interface Garment {
  id: string;
  label: string;
  description?: string;
  anchorPoint?: AnchorPoint;
  boundingBox: BoundingBox;
}

interface CanvasProps {
  imageUrl: string;
  garments: Garment[];
  isDetecting: boolean;
  detectionError?: string | null;
  onRetryDetection?: () => void;
  onLabelClick: (garment: Garment) => void;
  selectedGarmentId?: string;
}

interface ImageMetrics {
  left: number;
  top: number;
  width: number;
  height: number;
  containerWidth: number;
  containerHeight: number;
  scaleX: number;
  scaleY: number;
}

interface LabelLayout {
  left: number;
  top: number;
  anchorX: number;
  anchorY: number;
  side: 'left' | 'right';
}

const CARD_WIDTH = 214;
const CARD_HEIGHT = 78;
const CARD_GAP = 12;

const Canvas: React.FC<CanvasProps> = ({
  imageUrl,
  garments,
  isDetecting,
  detectionError,
  onRetryDetection,
  onLabelClick,
  selectedGarmentId,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const [metrics, setMetrics] = useState<ImageMetrics | null>(null);

  useEffect(() => {
    const calculateMetrics = () => {
      if (!containerRef.current || !imageRef.current || !imageRef.current.naturalWidth) return;

      const containerRect = containerRef.current.getBoundingClientRect();
      const el = imageRef.current.getBoundingClientRect();
      const naturalW = imageRef.current.naturalWidth;
      const naturalH = imageRef.current.naturalHeight;
      const elW = el.width;
      const elH = el.height;

      // object-contain: find the actual rendered content area within the element box
      const naturalAspect = naturalW / naturalH;
      const elAspect = elW / elH;
      let renderedW: number, renderedH: number;
      if (naturalAspect > elAspect) {
        // wider than container slot → clamped by width
        renderedW = elW;
        renderedH = elW / naturalAspect;
      } else {
        // taller than container slot → clamped by height
        renderedH = elH;
        renderedW = elH * naturalAspect;
      }
      const renderedLeft = el.left - containerRect.left + (elW - renderedW) / 2;
      const renderedTop  = el.top  - containerRect.top  + (elH - renderedH) / 2;

      setMetrics({
        left: renderedLeft,
        top: renderedTop,
        width: renderedW,
        height: renderedH,
        containerWidth: containerRect.width,
        containerHeight: containerRect.height,
        scaleX: renderedW / naturalW,
        scaleY: renderedH / naturalH,
      });
    };

    calculateMetrics();
    window.addEventListener('resize', calculateMetrics);
    return () => window.removeEventListener('resize', calculateMetrics);
  }, [imageUrl, garments.length]);

  const labelLayouts = useMemo(() => {
    if (!metrics) return new Map<string, LabelLayout>();

    const clampTop = (top: number) => (
      Math.max(14, Math.min(top, metrics.containerHeight - CARD_HEIGHT - 14))
    );
    const sideBuckets: Record<'left' | 'right', Array<{ garment: Garment; layout: LabelLayout }>> = {
      left: [],
      right: [],
    };

    garments.forEach((garment, index) => {
      const { boundingBox: box } = garment;
      const rawAnchorX = garment.anchorPoint?.x ?? ((box.x1 + box.x2) / 2);
      const rawAnchorY = garment.anchorPoint?.y ?? ((box.y1 + box.y2) / 2);
      const anchorX = metrics.left + rawAnchorX * metrics.scaleX;
      const anchorY = metrics.top + rawAnchorY * metrics.scaleY;
      const hasLeftGutter = metrics.left >= CARD_WIDTH + 28;
      const hasRightGutter = metrics.containerWidth - (metrics.left + metrics.width) >= CARD_WIDTH + 28;
      let side: 'left' | 'right' = anchorX < metrics.left + metrics.width / 2 ? 'left' : 'right';

      if (side === 'left' && !hasLeftGutter && hasRightGutter) side = 'right';
      if (side === 'right' && !hasRightGutter && hasLeftGutter) side = 'left';
      if (!hasLeftGutter && !hasRightGutter) side = index % 2 === 0 ? 'left' : 'right';

      const gutterLeft = side === 'left'
        ? Math.max(14, metrics.left - CARD_WIDTH - 24)
        : Math.min(metrics.containerWidth - CARD_WIDTH - 14, metrics.left + metrics.width + 24);

      sideBuckets[side].push({
        garment,
        layout: {
          left: gutterLeft,
          top: clampTop(anchorY - CARD_HEIGHT / 2),
          anchorX,
          anchorY,
          side,
        },
      });
    });

    const layouts = new Map<string, LabelLayout>();
    (Object.keys(sideBuckets) as Array<'left' | 'right'>).forEach((side) => {
      const bucket = sideBuckets[side].sort((a, b) => a.layout.top - b.layout.top);
      bucket.forEach((item, index) => {
        if (index > 0) {
          const previous = bucket[index - 1].layout;
          item.layout.top = Math.max(item.layout.top, previous.top + CARD_HEIGHT + CARD_GAP);
        }
      });

      const overflow = bucket.length
        ? bucket[bucket.length - 1].layout.top + CARD_HEIGHT + 14 - metrics.containerHeight
        : 0;
      if (overflow > 0) {
        bucket.forEach((item) => {
          item.layout.top = Math.max(14, item.layout.top - overflow);
        });
      }

      bucket.forEach((item) => layouts.set(item.garment.id, item.layout));
    });

    return layouts;
  }, [garments, metrics]);

  return (
    <div
      ref={containerRef}
      className="relative h-[88vh] w-full max-w-6xl overflow-hidden border border-white/10 bg-[#111] shadow-2xl"
    >
      {isDetecting && (
        <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-[#111]/90 backdrop-blur-md">
          <div className="mb-6 h-14 w-14 animate-spin rounded-full border-4 border-white/10 border-t-luxury-gold" />
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-luxury-gold">
            Analyzing Image
          </p>
          <p className="mt-3 max-w-xs text-center text-xs leading-relaxed text-white/45">
            Qwen2.5-VL is detecting visible garments and accessories.
          </p>
        </div>
      )}

      {!isDetecting && detectionError && (
        <div className="absolute left-1/2 top-6 z-50 w-[min(520px,calc(100%-48px))] -translate-x-1/2 rounded-md border border-red-400/60 bg-red-950/85 px-4 py-3 text-sm text-red-50 shadow-2xl backdrop-blur-md">
          <div className="font-semibold uppercase tracking-[0.14em] text-red-200">Detection failed</div>
          <div className="mt-1 leading-relaxed text-red-50/85">{detectionError}</div>
          {onRetryDetection && (
            <button
              type="button"
              onClick={onRetryDetection}
              className="mt-3 rounded-md border border-red-200/50 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-red-50 hover:bg-red-200/10"
            >
              Retry detection
            </button>
          )}
        </div>
      )}

      {!isDetecting && !detectionError && garments.length === 0 && (
        <div className="absolute left-1/2 top-6 z-50 -translate-x-1/2 rounded-md border border-white/10 bg-black/75 px-4 py-3 text-sm text-white/70 shadow-2xl backdrop-blur-md">
          No garment labels returned yet.
        </div>
      )}

      <img
        ref={imageRef}
        src={imageUrl}
        alt="Uploaded outfit"
        onLoad={() => {
          const event = new Event('resize');
          window.dispatchEvent(event);
        }}
        className={`h-full w-full object-contain transition-opacity duration-500 ${isDetecting ? 'opacity-20' : 'opacity-100'}`}
      />

      {metrics && !isDetecting && (
        <svg className="pointer-events-none absolute inset-0 z-20 h-full w-full">
          {garments.map((garment) => {
            const position = labelLayouts.get(garment.id);
            if (!position) return null;
            const cardEdgeX = position.side === 'left' ? position.left + CARD_WIDTH : position.left;
            const cardEdgeY = position.top + 25;
            return (
              <g key={`${garment.id}-connector`}>
                <line
                  x1={position.anchorX}
                  y1={position.anchorY}
                  x2={cardEdgeX}
                  y2={cardEdgeY}
                  stroke={selectedGarmentId === garment.id ? '#f8fafc' : '#f97316'}
                  strokeWidth="1.8"
                  strokeDasharray="4 5"
                />
                <circle
                  cx={position.anchorX}
                  cy={position.anchorY}
                  r="6"
                  fill="rgba(249,115,22,0.24)"
                  stroke={selectedGarmentId === garment.id ? '#f8fafc' : '#f97316'}
                  strokeWidth="2"
                />
                <circle cx={cardEdgeX} cy={cardEdgeY} r="3" fill="#f97316" />
              </g>
            );
          })}
        </svg>
      )}

      {metrics && !isDetecting && garments.map((garment) => {
        const isSelected = selectedGarmentId === garment.id;
        const position = labelLayouts.get(garment.id);
        if (!position) return null;
        const description = garment.description || `A visible ${garment.label.toLowerCase()} from the uploaded outfit.`;

        return (
          <button
            key={garment.id}
            type="button"
            onClick={() => onLabelClick(garment)}
            className={`absolute z-30 min-h-[78px] w-[214px] rounded-md border px-3 py-2.5 text-left shadow-xl backdrop-blur-md transition-all ${
              isSelected
                ? 'border-white bg-[#18120d] text-white shadow-[0_0_0_1px_rgba(249,115,22,0.7)]'
                : 'border-orange-500/55 bg-[#07111f]/88 text-white hover:border-orange-300 hover:bg-[#081827]'
            }`}
            style={{ left: position.left, top: position.top }}
          >
            <span className="block truncate text-[11px] font-black uppercase tracking-[0.12em] text-orange-500">
              {garment.label}
            </span>
            <span className="mt-1.5 block line-clamp-2 text-[12px] leading-snug text-slate-200/85">
              {description}
            </span>
          </button>
        );
      })}
    </div>
  );
};

export default Canvas;
