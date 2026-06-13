import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Upload, Wand2, Bot } from "lucide-react";
import {
  analyzeExplainerPage,
  fetchVisionHealth,
  streamExplainerPage,
  uploadExplainerImage,
  type ExplainerPage as ExplainerPageData,
  type GroundingMode,
  type VisionModelKey,
} from "../services/explainer-api";
import { streamAutoDrill } from "../services/agent-api";
import { getErrorMessage } from "../utils/errors";
import DiagramCanvas from "./explainer/DiagramCanvas";
import MetadataPanel from "./explainer/MetadataPanel";
import "../styles/explainer.css";

const STREAM_LABELS: Record<string, string> = {
  generating: "Generating…",
  grounding: "Isolating object…",
  vision: "Analyzing component…",
  generating_image: "Rendering next layer…",
};

export default function ExplainerPage() {
  const [pages, setPages] = useState<ExplainerPageData[]>([]);
  const [currentIndex, setCurrentIndex] = useState(-1);
  const [topic, setTopic] = useState("");
  const [phase, setPhase] = useState<"idle" | "loading" | "streaming">("idle");
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [groundingMode, setGroundingMode] = useState<GroundingMode>("red_ring");
  const [visionModel, setVisionModel] = useState<VisionModelKey>("qwen3.5");
  const [sam2Available, setSam2Available] = useState(false);
  const [lastClick, setLastClick] = useState<{ x: number; y: number } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const currentPage = currentIndex >= 0 ? pages[currentIndex] : null;
  const analyzing = analyzingId === currentPage?.id;

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
    async (page: ExplainerPageData) => {
      if (!page.id || page.isStreaming || page.id.startsWith("streaming_")) return;
      setAnalyzingId(page.id);
      try {
        const result = await analyzeExplainerPage(page.id, visionModel);
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
      setPages([data]);
      setCurrentIndex(0);
      await runAnalyze(data);
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

  const triggerDrill = async (x: number, y: number, customTopic?: string) => {
    if (!currentPage || currentPage.isStreaming || phase !== "idle") return;
    setLastClick({ x, y });
    setPhase("streaming");
    setError(null);
    setStatus("");
    const parentId = currentPage.id;
    const streamingPage: ExplainerPageData = {
      id: "streaming_drill",
      imageUrl: currentPage.imageUrl,
      isStreaming: true,
      streamStatus: "Drilling…",
    };
    setPages((prev) => [...prev.slice(0, currentIndex + 1), streamingPage]);
    setCurrentIndex(currentIndex + 1);

    try {
      await streamExplainerPage(
        { parentId, x, y, customTopic, visionModel, groundingMode },
        (eventType, data) => {
          setPages((prev) => {
            const next = [...prev];
            const idx = next.length - 1;
            if (eventType === "complete") {
              next[idx] = {
                id: data.id as string,
                imageUrl: data.imageUrl as string,
                metadata: (data.metadata as ExplainerPageData["metadata"]) ?? {},
                context: data.context as string,
                groundingMode: (data.groundingMode as string) ?? groundingMode,
                samConfidence: data.samConfidence as number | null | undefined,
                inputPrompt: data.inputPrompt as string | undefined,
                rawJson: (data.rawJson as string) ?? next[idx].rawJson,
                isStreaming: false,
              };
              setPhase("idle");
              setStatus("");
              runAnalyze(next[idx]);
            } else if (eventType === "error") {
              setError((data.message as string) ?? "Drill failed");
              next.pop();
              setCurrentIndex((i) => Math.max(0, i - 1));
              setPhase("idle");
              setStatus("");
            } else {
              const label = (data.message as string) ?? STREAM_LABELS[eventType] ?? eventType;
              next[idx] = { ...next[idx], streamStatus: label };
              setStatus(label);
            }
            return next;
          });
        }
      );
    } catch (err) {
      setError(getErrorMessage(err, "Drill failed"));
      setPhase("idle");
      setStatus("");
    }
  };

  const handleAutoDrill = async () => {
    if (!currentPage?.imageUrl || currentPage.isStreaming || phase !== "idle") return;
    setPhase("streaming");
    setError(null);
    setStatus("Agent auto-drill…");
    try {
      const imgRes = await fetch(currentPage.imageUrl);
      const blob = await imgRes.blob();
      const reader = new FileReader();
      const parentB64 = await new Promise<string>((resolve, reject) => {
        reader.onload = () => {
          const dataUrl = reader.result as string;
          resolve(dataUrl.split(",")[1] ?? "");
        };
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });

      const chain: ExplainerPageData[] = [currentPage];
      await streamAutoDrill(
        { parent_image_b64: parentB64, max_depth: 3, mode: "deterministic" },
        (eventType, data) => {
          if (eventType === "status") {
            setStatus(`${data.phase} (depth ${data.depth})`);
          } else if (eventType === "complete_depth" && typeof data.image_b64 === "string") {
            const depth = data.depth as number;
            chain.push({
              id: `agent_depth_${depth}`,
              imageUrl: `data:image/png;base64,${data.image_b64}`,
              metadata: {
                editorial_headline: (data.label as string) ?? `Auto depth ${depth}`,
              },
              context: data.label as string,
            });
            setPages([...chain]);
            setCurrentIndex(chain.length - 1);
          } else if (eventType === "error") {
            throw new Error((data.message as string) ?? "Auto-drill failed");
          }
        }
      );
    } catch (err) {
      setError(getErrorMessage(err, "Auto-drill failed"));
    } finally {
      setPhase("idle");
      setStatus("");
    }
  };

  const activeGrounding = currentPage?.groundingMode ?? groundingMode;
  const groundingLabel = activeGrounding === "sam2" ? "SAM2 cutout" : "Red marker";

  return (
    <div className="explainer-mode">
      <aside className="explainer-sidebar">
        <h2>Explainer</h2>
        <p className="hint">Vision analysis + image generation</p>

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
          <div className="page-strip">
            <span className="page-strip-label">Layers</span>
            {pages.map((p, i) => (
              <button
                key={p.id + i}
                type="button"
                className={i === currentIndex ? "active" : ""}
                onClick={() => {
                  setCurrentIndex(i);
                  setLastClick(null);
                }}
                title={p.metadata?.editorial_headline ?? `Layer ${i + 1}`}
              >
                {i + 1}
              </button>
            ))}
          </div>
        )}

        {currentPage && !currentPage.isStreaming && (
          <>
            <button
              type="button"
              className="explainer-btn"
              disabled={analyzing || phase !== "idle"}
              onClick={() => runAnalyze(currentPage)}
            >
              {analyzing ? <Loader2 className="spin" size={14} /> : null}
              Re-scan labels
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
              busy={phase === "loading"}
              statusText={status}
              lastClick={lastClick}
              onCanvasClick={(x, y) => triggerDrill(x, y)}
              onLabelClick={(x, y, label) => triggerDrill(x, y, label)}
            />
            <MetadataPanel page={currentPage} groundingLabel={groundingLabel} />
          </>
        )}
      </section>
    </div>
  );
}
