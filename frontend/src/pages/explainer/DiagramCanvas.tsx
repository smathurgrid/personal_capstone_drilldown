import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import type { ExplainerPage } from "../../services/explainer-api";
import { normalizeElementClick } from "../../utils/coords";
import { getColumnData, getDistributedY, LabelDetail } from "./label-layout";

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
  const [dims, setDims] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const update = () => {
      if (wrapRef.current) {
        setDims({
          width: wrapRef.current.clientWidth,
          height: wrapRef.current.clientHeight,
        });
      }
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [page.imageUrl, page.id]);

  const details: LabelDetail[] = (page.metadata?.granular_details ?? []).filter(
    (d) => d.point && d.point.length >= 2
  ) as LabelDetail[];

  const showLabels = !page.isStreaming && !analyzing && details.length > 0;
  const showOverlay = page.isStreaming || analyzing || busy;

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (page.isStreaming || busy) return;
    const img = e.currentTarget.querySelector("img");
    if (!img) return;
    const { x, y } = normalizeElementClick(e, img, { clamp: true });
    if (x < 0 || x > 1 || y < 0 || y > 1) return;
    onCanvasClick(x, y);
  };

  return (
    <div className="diagram-stage">
      <div className="diagram-canvas-wrap" ref={wrapRef} onClick={handleClick}>
        {page.imageUrl ? (
          <img
            src={page.imageUrl}
            alt="Explainer canvas"
            className="diagram-image"
            draggable={false}
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
            {details.map((detail, idx) => {
              const { isLeft, indexInCol } = getColumnData(details, idx);
              const labelY = getDistributedY(details, idx);
              const [px, py] = detail.point;
              const staggerX = [12, 60, 110][indexInCol % 3];
              const x1 = isLeft ? -staggerX : dims.width + staggerX;
              const y1 = labelY * dims.height;
              const x2 = px * dims.width;
              const y2 = py * dims.height;
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
            const [lx, ly] = detail.point;
            return (
              <button
                key={`card-${detail.label}-${idx}`}
                type="button"
                className={`diagram-label-card ${isLeft ? "left" : "right"}`}
                style={{
                  top: `${labelY * 100}%`,
                  ...(isLeft ? { right: `calc(100% + ${staggerX}px)` } : { left: `calc(100% + ${staggerX}px)` }),
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  onLabelClick(lx, ly, detail.label);
                }}
              >
                <span className="diagram-label-title">{detail.label}</span>
                {detail.description && (
                  <span className="diagram-label-desc">{detail.description}</span>
                )}
              </button>
            );
          })}

        {lastClick && !page.isStreaming && (
          <div
            className="click-ring"
            style={{ left: `${lastClick.x * 100}%`, top: `${lastClick.y * 100}%` }}
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
