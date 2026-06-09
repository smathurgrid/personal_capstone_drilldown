import { ChangeEvent, MouseEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Crosshair,
  Download,
  ImagePlus,
  Loader2,
  RefreshCcw,
  Sparkles,
  UploadCloud,
  WandSparkles
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8001";

type HealthState = "checking" | "online" | "offline";
type Phase = "idle" | "generating-initial" | "analyzing" | "generating";

interface Point {
  x: number;
  y: number;
  displayX: number;
  displayY: number;
}

interface AnalysisResponse {
  analysis: string;
  image_prompt: string;
  local_crop_b64: string;
  marked_image_b64: string;
}

interface GeneratedFromTextResponse {
  image_b64: string;
  image_prompt: string;
}

function b64ToDataUrl(b64: string) {
  return `data:image/png;base64,${b64}`;
}

async function dataUrlToFile(dataUrl: string, fileName: string) {
  const response = await fetch(dataUrl);
  const blob = await response.blob();
  return new File([blob], fileName, { type: blob.type || "image/png" });
}

async function readFileUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Could not read selected image."));
    reader.readAsDataURL(file);
  });
}

function statusLabel(health: HealthState) {
  if (health === "online") return "Backend online";
  if (health === "offline") return "Backend offline";
  return "Checking backend";
}

export default function App() {
  const imageRef = useRef<HTMLImageElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [health, setHealth] = useState<HealthState>("checking");
  const [phase, setPhase] = useState<Phase>("idle");
  const [topic, setTopic] = useState("A cutaway explainer of how a city subway tunnel works");
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState("");
  const [point, setPoint] = useState<Point | null>(null);
  const [radius, setRadius] = useState(90);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [generatedUrl, setGeneratedUrl] = useState("");
  const [initialPrompt, setInitialPrompt] = useState("");
  const [error, setError] = useState("");

  const busy = phase !== "idle";
  const canAnalyze = Boolean(sourceFile && point && !busy);
  const canGenerate = Boolean(analysis && !busy);

  const workflowText = useMemo(() => {
    if (phase === "generating-initial") return "Generating first image from topic";
    if (phase === "analyzing") return "Analyzing selected region with backend";
    if (phase === "generating") return "Generating new drill-down image";
    if (analysis && generatedUrl) return "Generated image ready";
    if (analysis) return "Analysis ready for generation";
    if (sourceFile && point) return "Region selected";
    if (sourceFile) return "Image loaded";
    return "Awaiting image or topic";
  }, [analysis, generatedUrl, phase, point, sourceFile]);

  useEffect(() => {
    checkHealth();
  }, []);

  async function checkHealth() {
    setHealth("checking");
    try {
      const response = await fetch(`${API_BASE}/api/health`);
      const data = await response.json();
      setHealth(response.ok && data.ollama ? "online" : "offline");
    } catch {
      setHealth("offline");
    }
  }

  function resetDerivedState() {
    setPoint(null);
    setAnalysis(null);
    setGeneratedUrl("");
    setInitialPrompt("");
    setError("");
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const url = await readFileUrl(file);
      setSourceFile(file);
      setSourceUrl(url);
      resetDerivedState();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load image.");
    }
  }

  function handleImageClick(event: MouseEvent<HTMLImageElement>) {
    if (!imageRef.current || busy) return;
    const img = imageRef.current;
    const rect = img.getBoundingClientRect();
    const displayX = event.clientX - rect.left;
    const displayY = event.clientY - rect.top;
    const scaleX = img.naturalWidth / rect.width;
    const scaleY = img.naturalHeight / rect.height;

    setPoint({
      x: Math.round(displayX * scaleX),
      y: Math.round(displayY * scaleY),
      displayX,
      displayY
    });
    setAnalysis(null);
    setGeneratedUrl("");
    setError("");
  }

  function selectCenterPoint() {
    if (!imageRef.current || busy) return;
    const img = imageRef.current;
    const rect = img.getBoundingClientRect();
    setPoint({
      x: Math.round(img.naturalWidth / 2),
      y: Math.round(img.naturalHeight / 2),
      displayX: rect.width / 2,
      displayY: rect.height / 2
    });
    setAnalysis(null);
    setGeneratedUrl("");
    setError("");
  }

  async function generateInitialImage() {
    const cleanTopic = topic.trim();
    if (!cleanTopic) return;

    setPhase("generating-initial");
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/generate-from-text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: cleanTopic })
      });
      if (!response.ok) throw new Error(await response.text());
      const data = (await response.json()) as GeneratedFromTextResponse;
      const url = b64ToDataUrl(data.image_b64);
      const file = await dataUrlToFile(url, "generated-overview.png");
      setSourceUrl(url);
      setSourceFile(file);
      setInitialPrompt(data.image_prompt);
      setPoint(null);
      setAnalysis(null);
      setGeneratedUrl("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Initial image generation failed.");
    } finally {
      setPhase("idle");
    }
  }

  async function analyzeRegion() {
    if (!sourceFile || !point) return;

    setPhase("analyzing");
    setError("");
    try {
      const body = new FormData();
      body.append("image", sourceFile);
      body.append("x", String(point.x));
      body.append("y", String(point.y));
      body.append("radius", String(radius));

      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: "POST",
        body
      });
      if (!response.ok) throw new Error(await response.text());
      const data = (await response.json()) as AnalysisResponse;
      setAnalysis(data);
      setGeneratedUrl("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Region analysis failed.");
    } finally {
      setPhase("idle");
    }
  }

  async function generateDrillImage() {
    if (!analysis) return;

    setPhase("generating");
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: analysis.image_prompt,
          local_crop_b64: analysis.local_crop_b64,
          global_b64: analysis.marked_image_b64
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const data = (await response.json()) as { image_b64: string };
      setGeneratedUrl(b64ToDataUrl(data.image_b64));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Image generation failed.");
    } finally {
      setPhase("idle");
    }
  }

  async function useGeneratedAsSource() {
    if (!generatedUrl) return;
    const file = await dataUrlToFile(generatedUrl, "drilldown-generated.png");
    setSourceFile(file);
    setSourceUrl(generatedUrl);
    setPoint(null);
    setAnalysis(null);
    setGeneratedUrl("");
    setInitialPrompt("");
    setError("");
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => fileInputRef.current?.click()}>
          <span className="brand-mark">
            <Sparkles size={20} />
          </span>
          <span>DrillDown</span>
        </button>

        <div className="topbar-actions">
          <div className={`health-pill ${health}`}>
            {health === "checking" ? <Loader2 size={14} className="spin" /> : health === "online" ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
            {statusLabel(health)}
          </div>
          <button className="icon-button" onClick={checkHealth} title="Refresh backend health">
            <RefreshCcw size={18} />
          </button>
        </div>
      </header>

      <main className="workspace">
        <section className="left-rail">
          <div className="section-title">
            <span>Input</span>
            <small>{workflowText}</small>
          </div>

          <label className="upload-zone">
            <UploadCloud size={28} />
            <strong>Upload source image</strong>
            <span>PNG, JPG, JPEG</span>
            <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileChange} disabled={busy} />
          </label>

          <div className="topic-card">
            <div className="card-heading">
              <ImagePlus size={18} />
              <span>Generate source from topic</span>
            </div>
            <textarea value={topic} onChange={(event) => setTopic(event.target.value)} disabled={busy} />
            <button className="primary-button" onClick={generateInitialImage} disabled={busy || !topic.trim()}>
              {phase === "generating-initial" ? <Loader2 size={16} className="spin" /> : <WandSparkles size={16} />}
              Generate New Image
            </button>
          </div>

          <div className="control-card">
            <div className="card-heading">
              <Crosshair size={18} />
              <span>Region control</span>
            </div>
            <label>
              Crop radius
              <input type="range" min="40" max="180" value={radius} onChange={(event) => setRadius(Number(event.target.value))} disabled={busy} />
              <b>{radius}px</b>
            </label>
            <button className="secondary-button" onClick={selectCenterPoint} disabled={!sourceFile || busy}>
              Select Center
            </button>
            <button className="primary-button" onClick={analyzeRegion} disabled={!canAnalyze}>
              {phase === "analyzing" ? <Loader2 size={16} className="spin" /> : <Activity size={16} />}
              Analyze Region
            </button>
            <button className="primary-button" onClick={generateDrillImage} disabled={!canGenerate}>
              {phase === "generating" ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
              Generate Drill Image
            </button>
          </div>
        </section>

        <section className="image-stage">
          <div className="stage-header">
            <div>
              <p>Source Viewer</p>
              <h1>Upload, select a region, generate the next image.</h1>
            </div>
            {point && (
              <code>
                x:{point.x} y:{point.y}
              </code>
            )}
          </div>

          <div className="viewer-card">
            {sourceUrl ? (
              <div className="image-wrap">
                <img ref={imageRef} src={sourceUrl} alt="Source for drill-down analysis" onClick={handleImageClick} />
                {point && (
                  <span
                    className="selection-ring"
                    style={{ left: `${point.displayX}px`, top: `${point.displayY}px` }}
                    aria-hidden="true"
                  />
                )}
              </div>
            ) : (
              <div className="empty-state">
                <ImagePlus size={44} />
                <h2>No image loaded</h2>
                <p>Upload an image or generate one from a topic to start the backend workflow.</p>
              </div>
            )}
          </div>

          {error && (
            <div className="error-banner">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}
        </section>

        <aside className="right-rail">
          <div className="section-title">
            <span>Backend Output</span>
            <small>Dynamic response data</small>
          </div>

          {initialPrompt && (
            <article className="result-card">
              <h3>Initial Image Prompt</h3>
              <p>{initialPrompt}</p>
            </article>
          )}

          <article className="result-card grow">
            <h3>Analysis</h3>
            {analysis ? <p>{analysis.analysis}</p> : <p className="muted">Select a point and run analysis to see the backend vision response.</p>}
          </article>

          {analysis && (
            <article className="result-card">
              <h3>Generated Prompt</h3>
              <p>{analysis.image_prompt}</p>
            </article>
          )}

          {analysis && (
            <div className="preview-grid">
              <div>
                <span>Local crop</span>
                <img src={b64ToDataUrl(analysis.local_crop_b64)} alt="Local crop from backend" />
              </div>
              <div>
                <span>Marked source</span>
                <img src={b64ToDataUrl(analysis.marked_image_b64)} alt="Marked image from backend" />
              </div>
            </div>
          )}

          {generatedUrl && (
            <article className="generated-card">
              <div className="generated-header">
                <h3>Generated Image</h3>
                <a href={generatedUrl} download="drilldown-generated.png" title="Download generated image">
                  <Download size={17} />
                </a>
              </div>
              <img src={generatedUrl} alt="Generated drill-down output" />
              <button className="secondary-button" onClick={useGeneratedAsSource}>
                Use As New Source
              </button>
            </article>
          )}
        </aside>
      </main>

      <footer className="statusbar">
        <span>API: {API_BASE}</span>
        <span>Flow: upload/text to analyze to generate</span>
      </footer>
    </div>
  );
}
