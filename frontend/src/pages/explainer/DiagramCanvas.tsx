import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import type { ExplainerPage } from "../../services/explainer-api";
import { mapNormalizedToDisplay, normalizeContainedImageClick } from "../../utils/coords";
import { getColumnData, getDistributedY, LabelDetail } from "./label-layout";

function normalizeLabelDetail(d: LabelDetail): LabelDetail {
  const uncertain = d.positionUncertain ?? (d as { position_uncertain?: boolean }).position_uncertain;
  return { ...d, positionUncertain: uncertain };
}

type Props = {
  page: ExplainerPage;
  analyzing: boolean;
  busy: boolean;
  statusText?: string;
  lastClick?: { x: number; y: number } | null;
  onCanvasClick: (x: number, y: number) => void;
  onLabelClick: (x: number, y: number, label: string) => void;
};

export default function DiagramCanvas({
  page,
  analyzing,
  busy,
  statusText,
  lastClick,
  onCanvasClick,
  onLabelClick,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [dims, setDims] = useState({ width: 0, height: 0, naturalWidth: 0, naturalHeight: 0 });

  const updateDims = useCallback(() => {
    const wrap = wrapRef.current;
    const img = imgRef.current;
    if (!wrap) return;
    setDims({
      width: wrap.clientWidth,
      height: wrap.clientHeight,
      naturalWidth: img?.naturalWidth ?? wrap.clientWidth,
      naturalHeight: img?.naturalHeight ?? wrap.clientHeight,
    });
  }, []);

  useEffect(() => {
    updateDims();
    window.addEventListener("resize", updateDims);
    return () => window.removeEventListener("resize", updateDims);
  }, [page.imageUrl, page.id, updateDims]);

  const rawDetails: LabelDetail[] = (page.metadata?.granular_details ?? []).map(normalizeLabelDetail);
  const details = rawDetails.filter((d) => d.label);
  const positionedDetails = details.filter(
    (d) => d.point && d.point.length >= 2 && !d.positionUncertain
  );

  const showLabels = !page.isStreaming && !analyzing && details.length > 0;
  const showOverlay = page.isStreaming || analyzing || busy;

  const toDisplay = (nx: number, ny: number) =>
    mapNormalizedToDisplay(
      nx,
      ny,
      dims.width,
      dims.height,
      dims.naturalWidth,
      dims.naturalHeight
    );

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (page.isStreaming || busy) return;
    const img = imgRef.current;
    if (!img) return;
    const coords = normalizeContainedImageClick(e.clientX, e.clientY, img, { clamp: true });
    if (!coords) return;
    onCanvasClick(coords.x, coords.y);
  };

  const clickDisplay = lastClick
    ? toDisplay(lastClick.x, lastClick.y)
    : null;

  const entryClick = page.click && page.parentId ? page.click : null;
  const entryDisplay = entryClick ? toDisplay(entryClick.x, entryClick.y) : null;

  return (
    <div className="diagram-stage">
      <div className="diagram-canvas-wrap" ref={wrapRef} onClick={handleClick}>
        {page.imageUrl ? (
          <img
            ref={imgRef}
            src={page.imageUrl}
            alt="Explainer canvas"
            className="diagram-image"
            draggable={false}
            onLoad={updateDims}
          />
        ) : (
          <div className="explainer-placeholder" />
        )}

        {analyzing && (
          <>
            <div className="scan-overlay" />
            <div className="scan-line" />
          </>
        )}

        {showLabels && dims.width > 0 && (
          <svg
            className="diagram-svg"
            viewBox={`0 0 ${dims.width} ${dims.height}`}
            preserveAspectRatio="none"
          >
            <defs>
              <marker
                id="diagram-arrow"
                markerWidth="8"
                markerHeight="8"
                refX="8"
                refY="4"
                orient="auto"
              >
                <polygon points="0 0, 8 4, 0 8" fill="#ed6a2c" />
              </marker>
            </defs>
            {positionedDetails.map((detail, idx) => {
              const { isLeft, indexInCol } = getColumnData(positionedDetails, idx);
              const labelY = getDistributedY(positionedDetails, idx);
              const point = detail.point as [number, number];
              const px = point[0];
              const py = point[1];
              const { x: x2, y: y2 } = toDisplay(px, py);
              const staggerX = [12, 60, 110][indexInCol % 3];
              const x1 = isLeft ? -staggerX : dims.width + staggerX;
              const y1 = labelY * dims.height;
              return (
                <g key={`line-${detail.label}-${idx}`}>
                  <circle cx={x2} cy={y2} r="5" fill="#ed6a2c" />
                  <circle cx={x2} cy={y2} r="12" fill="none" stroke="#ed6a2c" strokeWidth="1" opacity="0.5">
                    <animate attributeName="r" from="5" to="16" dur="1.5s" repeatCount="indefinite" />
                    <animate attributeName="opacity" from="0.8" to="0" dur="1.5s" repeatCount="indefinite" />
                  </circle>
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke="#ed6a2c"
                    strokeWidth="2"
                    strokeDasharray="4 4"
                    opacity="0.9"
                    markerEnd="url(#diagram-arrow)"
                  />
                </g>
              );
            })}
          </svg>
        )}

        {showLabels &&
          details.map((detail, idx) => {
            const { isLeft, indexInCol } = getColumnData(details, idx);
            const labelY = getDistributedY(details, idx);
            const staggerX = [12, 60, 110][indexInCol % 3];
            const point = detail.point;
            const uncertain = detail.positionUncertain || !point || point.length < 2;
            const lx = uncertain ? 0.5 : point[0];
            const ly = uncertain ? 0.5 : point[1];
            return (
              <button
                key={`card-${detail.label}-${idx}`}
                type="button"
                className={`diagram-label-card ${isLeft ? "left" : "right"}${uncertain ? " uncertain" : ""}`}
                style={{
                  top: `${labelY * 100}%`,
                  ...(isLeft ? { right: `calc(100% + ${staggerX}px)` } : { left: `calc(100% + ${staggerX}px)` }),
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  if (!uncertain) onLabelClick(lx, ly, detail.label);
                }}
                disabled={uncertain}
                title={uncertain ? "Position uncertain — use canvas click to drill" : undefined}
              >
                <span className="diagram-label-title">{detail.label}</span>
                {uncertain && <span className="diagram-label-uncertain">Position uncertain</span>}
                {detail.description && (
                  <span className="diagram-label-desc">{detail.description}</span>
                )}
              </button>
            );
          })}

        {entryDisplay && !page.isStreaming && (
          <div
            className="entry-ring"
            style={{ left: `${entryDisplay.x}px`, top: `${entryDisplay.y}px` }}
            title="Entry point from parent layer"
          />
        )}

        {clickDisplay && !page.isStreaming && (
          <div
            className="click-ring"
            style={{ left: `${clickDisplay.x}px`, top: `${clickDisplay.y}px` }}
          />
        )}

        {showOverlay && (
          <div className="explainer-overlay">
            <Loader2 className="spin" size={32} />
            <span>
              {page.streamStatus ?? statusText ?? (analyzing ? "Scanning labels…" : "Working…")}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
