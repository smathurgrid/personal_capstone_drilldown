import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Upload, Wand2, Bot } from "lucide-react";
import {
  analyzeExplainerPage,
  cancelExplainerDrill,
  confirmExplainerDrill,
  fetchVisionHealth,
  streamExplainerPage,
  uploadExplainerImage,
  type ExplainerPage as ExplainerPageData,
  type GroundingMode,
  type VisionModelKey,
} from "../services/explainer-api";
import { imageUrlToB64, pickNextRegion } from "../services/agent-api";
import { useExplainerSession } from "../hooks/useExplainerSession";
import { getErrorMessage } from "../utils/errors";
import DiagramCanvas from "./explainer/DiagramCanvas";
import DrillBreadcrumb from "./explainer/DrillBreadcrumb";
import DrillConfirmModal, { type PendingDrill } from "./explainer/DrillConfirmModal";
import MetadataPanel from "./explainer/MetadataPanel";
import "../styles/explainer.css";

const STREAM_LABELS: Record<string, string> = {
  generating: "Generating…",
  grounding: "Isolating object…",
  vision: "Analyzing component…",
  generating_image: "Rendering next layer…",
  confirm: "Review drill target…",
};

function pageFromDrillResult(
  data: Record<string, unknown>,
  fallback: { parentId: string; x: number; y: number; groundingMode: string; visionModel: string; drillMode: string }
): ExplainerPageData {
  return {
    id: data.id as string,
    imageUrl: data.imageUrl as string,
    metadata: (data.metadata as ExplainerPageData["metadata"]) ?? {},
    context: data.context as string,
    parentId: (data.parentId as string) ?? fallback.parentId,
    click: (data.click as { x: number; y: number }) ?? { x: fallback.x, y: fallback.y },
    depth: data.depth as number | undefined,
    groundingMode: (data.groundingMode as string) ?? fallback.groundingMode,
    visionModel: (data.visionModel as string) ?? fallback.visionModel,
    drillMode: (data.drillMode as string) ?? fallback.drillMode,
    samConfidence: data.samConfidence as number | null | undefined,
    inputPrompt: data.inputPrompt as string | undefined,
    rawJson: data.rawJson as string | undefined,
    isStreaming: false,
  };
}

export default function ExplainerPage() {
  const [pages, setPages] = useState<ExplainerPageData[]>([]);
  const [currentIndex, setCurrentIndex] = useState(-1);
  const [topic, setTopic] = useState("");
  const [phase, setPhase] = useState<"idle" | "loading" | "streaming" | "confirm" | "generating">("idle");
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [groundingMode, setGroundingMode] = useState<GroundingMode>("red_ring");
  const [visionModel, setVisionModel] = useState<VisionModelKey>("qwen3.5");
  const [drillMode, setDrillMode] = useState<string>("inside");
  const [sam2Available, setSam2Available] = useState(false);
  const [lastClick, setLastClick] = useState<{ x: number; y: number } | null>(null);
  const [pendingDrill, setPendingDrill] = useState<PendingDrill | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const autoDrillRef = useRef<{ depth: number; maxDepth: number } | null>(null);

  const currentPage = currentIndex >= 0 ? pages[currentIndex] : null;
  const analyzing = analyzingId === currentPage?.id;

  const { navigateToIndex } = useExplainerSession(pages, currentIndex, setPages, setCurrentIndex);

  useEffect(() => {
    fetchVisionHealth()
      .then((checks) => {
        const available = Boolean(checks.sam2_available);
        setSam2Available(available);
        setGroundingMode(checks.default_grounding_mode ?? (available ? "sam2" : "red_ring"));
      })
      .catch(() => setGroundingMode("red_ring"));
  }, []);

  const runAnalyze = useCallback(
    async (page: ExplainerPageData, scanMode: "global" | "focus" = "global") => {
      if (!page.id || page.isStreaming || page.id.startsWith("streaming_")) return;
      const depth = page.depth ?? 0;
      if (scanMode === "global" && (page.parentId || depth > 0 || page.context)) return;
      if (scanMode === "focus" && depth < 1) return;
      setAnalyzingId(page.id);
      try {
        const result = await analyzeExplainerPage(page.id, visionModel, scanMode, depth);
        setPages((prev) =>
          prev.map((p) =>
            p.id === page.id ? { ...p, metadata: result.metadata, rawJson: result.rawJson } : p
          )
        );
      } catch (err) {
        console.warn("Analyze failed:", err);
      } finally {
        setAnalyzingId(null);
      }
    },
    [visionModel]
  );

  const handleUpload = async (file: File) => {
    setPhase("loading");
    setError(null);
    setLastClick(null);
    try {
      const data = await uploadExplainerImage(file);
      setPages([{ ...data, depth: 0 }]);
      setCurrentIndex(0);
      await runAnalyze({ ...data, depth: 0 });
    } catch (err) {
      setError(getErrorMessage(err, "Upload failed"));
    } finally {
      setPhase("idle");
    }
  };

  const handleTopicStart = async () => {
    if (!topic.trim()) return;
    setPhase("streaming");
    setError(null);
    setStatus("Generating overview…");
    setLastClick(null);
    const temp: ExplainerPageData = {
      id: "streaming_temp",
      imageUrl: "",
      isStreaming: true,
      streamStatus: "Starting…",
    };
    setPages([temp]);
    setCurrentIndex(0);
    try {
      await streamExplainerPage({ query: topic.trim() }, (eventType, data) => {
        if (eventType === "complete") {
          const page: ExplainerPageData = {
            id: data.id as string,
            imageUrl: data.imageUrl as string,
            metadata: (data.metadata as ExplainerPageData["metadata"]) ?? {},
            depth: 0,
            isStreaming: false,
          };
          setPages([page]);
          setCurrentIndex(0);
          runAnalyze(page);
          setPhase("idle");
          setStatus("");
        } else if (eventType === "error") {
          throw new Error((data.message as string) ?? "Generation failed");
        } else {
          setStatus((data.message as string) ?? STREAM_LABELS[eventType] ?? eventType);
        }
      });
    } catch (err) {
      setError(getErrorMessage(err, "Topic generation failed"));
      setPages([]);
      setCurrentIndex(-1);
      setPhase("idle");
      setStatus("");
    }
  };

  const finalizeDrillPage = useCallback(
    (page: ExplainerPageData) => {
      setPages((prev) => {
        const next = [...prev];
        next[next.length - 1] = page;
        return next;
      });
      setPhase("idle");
      setStatus("");
      setPendingDrill(null);
      if ((page.depth ?? 0) >= 1) {
        runAnalyze(page, "focus");
      }
      return page;
    },
    [runAnalyze]
  );

  const handleConfirmDrill = async (drillTopic: string) => {
    if (!pendingDrill) return;
    setPhase("generating");
    setStatus("Rendering next layer…");
    try {
      const data = await confirmExplainerDrill(pendingDrill.pageId, drillTopic);
      const completed = finalizeDrillPage(
        pageFromDrillResult(data as unknown as Record<string, unknown>, {
          parentId: pendingDrill.parentId,
          x: pendingDrill.click.x,
          y: pendingDrill.click.y,
          groundingMode,
          visionModel,
          drillMode,
        })
      );
      const auto = autoDrillRef.current;
      if (auto && auto.depth < auto.maxDepth) {
        autoDrillRef.current = { depth: auto.depth + 1, maxDepth: auto.maxDepth };
        void runAutoPickAndDrill(completed);
      } else {
        autoDrillRef.current = null;
      }
    } catch (err) {
      setError(getErrorMessage(err, "Generation failed"));
      setPhase("confirm");
    }
  };

  const handleCancelDrill = async () => {
    if (pendingDrill) {
      try {
        await cancelExplainerDrill(pendingDrill.pageId);
      } catch {
        /* ignore */
      }
    }
    setPendingDrill(null);
    autoDrillRef.current = null;
    setPages((prev) => {
      const next = [...prev];
      if (next[next.length - 1]?.isStreaming) next.pop();
      return next;
    });
    setCurrentIndex((i) => Math.max(0, i - 1));
    setPhase("idle");
    setStatus("");
  };

  const triggerDrill = async (
    x: number,
    y: number,
    customTopic?: string,
    cacheBust?: string,
    parentOverride?: ExplainerPageData
  ) => {
    const drillParent = parentOverride ?? currentPage;
    if (!drillParent || drillParent.isStreaming || (phase !== "idle" && phase !== "confirm")) return;
    setLastClick({ x, y });
    setPhase("streaming");
    setError(null);
    setStatus("");
    setPendingDrill(null);
    const parentId = drillParent.id;
    const streamingPage: ExplainerPageData = {
      id: "streaming_drill",
      imageUrl: drillParent.imageUrl,
      isStreaming: true,
      streamStatus: "Drilling…",
    };
    setPages((prev) => {
      const parentIdx = parentOverride
        ? prev.findIndex((p) => p.id === parentOverride.id)
        : currentIndex;
      const baseIdx = parentIdx >= 0 ? parentIdx : currentIndex;
      setCurrentIndex(baseIdx + 1);
      return [...prev.slice(0, baseIdx + 1), streamingPage];
    });

    try {
      await streamExplainerPage(
        { parentId, x, y, customTopic, visionModel, groundingMode, cacheBust, drillMode },
        (eventType, data) => {
          if (eventType === "complete") {
            finalizeDrillPage(
              pageFromDrillResult(data, {
                parentId,
                x,
                y,
                groundingMode,
                visionModel,
                drillMode,
              })
            );
          } else if (eventType === "confirm") {
            setPendingDrill({
              pageId: data.pageId as string,
              parentId: (data.parentId as string) ?? parentId,
              click: (data.click as { x: number; y: number }) ?? { x, y },
              objectName: (data.objectName as string) ?? "Selected region",
              drillTopic: (data.drillTopic as string) ?? "",
              cropPreviewB64: data.cropPreviewB64 as string | undefined,
              metadata: data.metadata as ExplainerPageData["metadata"],
            });
            setPhase("confirm");
            setStatus("Review drill target before generating");
            setPages((prev) => {
              const next = [...prev];
              const idx = next.length - 1;
              next[idx] = {
                ...next[idx],
                streamStatus: "Awaiting confirmation…",
                isStreaming: false,
              };
              return next;
            });
          } else if (eventType === "error") {
            setError((data.message as string) ?? "Drill failed");
            setPages((prev) => {
              const next = [...prev];
              next.pop();
              return next;
            });
            setCurrentIndex((i) => Math.max(0, i - 1));
            setPhase("idle");
            setStatus("");
          } else {
            const label = (data.message as string) ?? STREAM_LABELS[eventType] ?? eventType;
            setStatus(label);
            setPages((prev) => {
              const next = [...prev];
              const idx = next.length - 1;
              next[idx] = { ...next[idx], streamStatus: label };
              return next;
            });
          }
        }
      );
    } catch (err) {
      setError(getErrorMessage(err, "Drill failed"));
      setPhase("idle");
      setStatus("");
    }
  };

  const runAutoPickAndDrill = useCallback(
    async (parentPage: ExplainerPageData) => {
      const state = autoDrillRef.current;
      if (!state) return;
      setPhase("streaming");
      setError(null);
      try {
        const b64 = await imageUrlToB64(parentPage.imageUrl);
        const pick = await pickNextRegion(b64);
        setStatus(
          `Auto drill ${state.depth}/${state.maxDepth}: ${(pick.label as string) ?? "region"}`
        );
        await triggerDrill(pick.x, pick.y, undefined, undefined, parentPage);
      } catch (err) {
        setError(getErrorMessage(err, "Auto-drill failed"));
        autoDrillRef.current = null;
        setPhase("idle");
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [visionModel, groundingMode, currentIndex, phase]
  );

  const handleAutoDrill = async () => {
    if (!currentPage?.id || currentPage.isStreaming || phase !== "idle") return;
    if (currentPage.id.startsWith("streaming_")) return;
    autoDrillRef.current = { depth: 1, maxDepth: 3 };
    await runAutoPickAndDrill(currentPage);
  };

  const handleRegenerate = () => {
    if (!currentPage?.parentId || !currentPage.click) return;
    const parentPage = pages.find((p) => p.id === currentPage.parentId);
    if (!parentPage) return;
    const bust = crypto.randomUUID();
    setPages((prev) => prev.slice(0, currentIndex));
    setCurrentIndex((i) => Math.max(0, i - 1));
    void triggerDrill(
      currentPage.click.x,
      currentPage.click.y,
      currentPage.metadata?.object,
      bust,
      parentPage
    );
  };

  const activeGrounding = currentPage?.groundingMode ?? groundingMode;
  const groundingLabel = activeGrounding === "sam2" ? "SAM2 cutout" : "Red marker";

  return (
    <div className="explainer-mode">
      <div className="bg-blobs-container">
        <div className="bg-grid" />
        <div className="bg-stars" />
        <div className="bg-blob blob-orange" />
        <div className="bg-blob blob-teal" />
        <div className="bg-blob blob-purple" />
      </div>

      <aside className="explainer-sidebar">
        <div className="sidebar-header">
          <h2>Explainer</h2>
          <p className="hint">Vision analysis + image generation</p>
        </div>

        <div className="control-group">
          <label htmlFor="vision-model">Vision model</label>
          <select
            id="vision-model"
            value={visionModel}
            onChange={(e) => setVisionModel(e.target.value as VisionModelKey)}
            disabled={phase !== "idle"}
          >
            <option value="qwen3.5">Qwen 3.5 VL (Ollama)</option>
            <option value="none">Skip vision (direct zoom)</option>
          </select>
        </div>

        <div className="control-group">
          <label htmlFor="grounding-mode">Grounding</label>
          <select
            id="grounding-mode"
            value={groundingMode}
            onChange={(e) => setGroundingMode(e.target.value as GroundingMode)}
            disabled={phase !== "idle"}
          >
            <option value="sam2" disabled={!sam2Available}>
              SAM2 segment{sam2Available ? "" : " (unavailable)"}
            </option>
            <option value="red_ring">Red ring marker</option>
          </select>
        </div>

        <div className="control-group">
          <label htmlFor="drill-mode">Drill mode</label>
          <select
            id="drill-mode"
            value={drillMode}
            onChange={(e) => setDrillMode(e.target.value)}
            disabled={phase !== "idle"}
          >
            <option value="inside">Inside Zoom (Macro)</option>
            <option value="pov">POV Perspective (Outward)</option>
          </select>
        </div>

        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
        />
        <button
          type="button"
          className="explainer-btn"
          onClick={() => fileRef.current?.click()}
          disabled={phase !== "idle"}
        >
          <Upload size={16} /> Upload image
        </button>

        <div className="topic-row">
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Or enter a topic…"
            onKeyDown={(e) => e.key === "Enter" && handleTopicStart()}
            disabled={phase !== "idle"}
          />
          <button
            type="button"
            className="explainer-btn primary"
            onClick={handleTopicStart}
            disabled={phase !== "idle"}
          >
            <Wand2 size={16} />
          </button>
        </div>

        {status && <p className="status-text">{status}</p>}
        {error && <p className="error-text">{error}</p>}

        {pages.length > 0 && (
          <DrillBreadcrumb
            pages={pages.filter((p) => !p.isStreaming)}
            currentIndex={Math.min(currentIndex, pages.length - 1)}
            onNavigate={(i) => {
              navigateToIndex(i);
              setLastClick(null);
            }}
          />
        )}

        {currentPage && !currentPage.isStreaming && (
          <>
            <button
              type="button"
              className="explainer-btn"
              disabled={
                analyzing ||
                phase !== "idle" ||
                Boolean(currentPage.parentId || (currentPage.depth ?? 0) > 0)
              }
              onClick={() => runAnalyze(currentPage)}
            >
              {analyzing ? <Loader2 className="spin" size={14} /> : null}
              Re-scan labels
            </button>
            <button
              type="button"
              className="explainer-btn"
              disabled={phase !== "idle" || !currentPage.parentId || !currentPage.click}
              onClick={handleRegenerate}
            >
              Try again
            </button>
            <button
              type="button"
              className="explainer-btn primary"
              disabled={phase !== "idle"}
              onClick={handleAutoDrill}
            >
              <Bot size={16} /> Auto drill (F7)
            </button>
          </>
        )}
      </aside>

      <section className="explainer-main">
        {!currentPage ? (
          <div className="explainer-empty">
            <p>Upload an image or enter a topic to begin.</p>
            <p className="hint">Click the canvas or a label to drill into the next illustrated layer.</p>
          </div>
        ) : (
          <>
            <DiagramCanvas
              page={currentPage}
              analyzing={analyzing}
              busy={phase === "loading" || phase === "generating"}
              statusText={status}
              lastClick={lastClick}
              onCanvasClick={(x, y) => triggerDrill(x, y)}
              onLabelClick={(x, y, label) => triggerDrill(x, y, label)}
            />
            <MetadataPanel page={currentPage} groundingLabel={groundingLabel} />
          </>
        )}
      </section>

      {pendingDrill && (phase === "confirm" || phase === "generating") && (
        <DrillConfirmModal
          pending={pendingDrill}
          busy={phase === "generating"}
          onConfirm={handleConfirmDrill}
          onCancel={handleCancelDrill}
        />
      )}
    </div>
  );
}
