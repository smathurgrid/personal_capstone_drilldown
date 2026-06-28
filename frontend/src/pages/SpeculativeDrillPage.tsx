import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";
import { Loader2, Upload, Wand2, Zap, Check, X, Square, ChevronLeft } from "lucide-react";
import {
  startSpecDrill,
  clickSpecDrill,
  clickPointSpecDrill,
  backSpecDrill,
  endSpecDrill,
  isAbortError,
  shortWorker,
  b64ToDataUrl,
  type Hotspot,
} from "../services/spec-drill-api";
import "../styles/spec-drill.css";

type Phase = "idle" | "starting" | "prefetching" | "ready" | "serving" | "complete";

/** Read a File into raw base64 (no data: prefix — backend decodes it directly). */
function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve((reader.result as string).split(",")[1] ?? "");
    reader.onerror = () => reject(new Error("Could not read file"));
    reader.readAsDataURL(file);
  });
}

export default function SpeculativeDrillPage() {
  const [topic, setTopic] = useState("");
  const [maxDepth, setMaxDepth] = useState(3);
  const [hotspotCount, setHotspotCount] = useState(5);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [parentImg, setParentImg] = useState<string | null>(null);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [depth, setDepth] = useState(0);
  const [path, setPath] = useState<string[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [lastServeMs, setLastServeMs] = useState<number | null>(null);
  const [lastWasInstant, setLastWasInstant] = useState(false);
  const [freeClick, setFreeClick] = useState<{ x: number; y: number } | null>(null);
  const [servingMode, setServingMode] = useState<"instant" | "onfly">("instant");
  const [lastWorker, setLastWorker] = useState<string | null>(null);

  const fileRef = useRef<HTMLInputElement>(null);
  const busy = phase === "starting" || phase === "serving";
  const readyCount = hotspots.filter((h) => h.status === "ready").length;

  // Cancellation: every new action aborts the previous in-flight request and
  // bumps a token so any late SSE events from the abandoned stream are ignored.
  const abortRef = useRef<AbortController | null>(null);
  const tokenRef = useRef(0);
  const sessionRef = useRef<string | null>(null); // latest id, for unmount cleanup

  const beginRequest = useCallback(() => {
    tokenRef.current += 1;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    return { token: tokenRef.current, signal: ctrl.signal };
  }, []);

  const rememberSession = useCallback((id: string | null) => {
    sessionRef.current = id;
    setSessionId(id);
  }, []);

  // Tab switch unmounts this page (App.tsx keys each mode) -> kill everything:
  // abort the open stream AND end the backend session (cancels in-flight prefetch).
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      const sid = sessionRef.current;
      if (sid) endSpecDrill(sid).catch(() => {});
    };
  }, []);

  const updateHotspot = useCallback((id: string, patch: Partial<Hotspot>) => {
    setHotspots((prev) => prev.map((h) => (h.hotspot_id === id ? { ...h, ...patch } : h)));
  }, []);

  /** Shared SSE handler for start / hotspot click / free click (token-guarded). */
  const drillEventHandler =
    (token: number, t0: number, instant: boolean) =>
    (type: string, d: Record<string, unknown>) => {
      if (token !== tokenRef.current) return; // stale stream — ignore
      if (type === "session") {
        rememberSession(d.session_id as string);
        if (d.parent_image_b64) setParentImg(b64ToDataUrl(d.parent_image_b64 as string));
      } else if (type === "back") {
        setParentImg(b64ToDataUrl(d.image_b64 as string));
        setDepth(d.depth as number);
        setPath((p) => p.slice(0, -1));
        setHotspots([]);
        setFreeClick(null);
        setLastServeMs(null);
      } else if (type === "chosen") {
        setParentImg(b64ToDataUrl(d.image_b64 as string));
        setPath((p) => [...p, d.label as string]);
        setHotspots([]);
        setFreeClick(null);
        setLastWorker((d.worker as string) ?? null);
        const ms = Math.round(performance.now() - t0);
        setLastServeMs(ms);
        setLastWasInstant(instant && ms < 1500);
      } else if (type === "hotspots") {
        setHotspots(d.regions as Hotspot[]);
        setDepth(d.depth as number);
        setPhase("prefetching");
      } else if (type === "prefetch_ready") {
        updateHotspot(d.hotspot_id as string, { status: d.status as Hotspot["status"] });
      } else if (type === "depth_ready") {
        setPhase("ready");
      } else if (type === "complete") {
        setPhase("complete");
      } else if (type === "error") {
        setError((d.message as string) ?? "Drill failed");
      }
    };

  /** Shared start flow — works the same whether seeded by a topic or an upload. */
  const runStart = async (seed: {
    topic?: string;
    parent_image_b64?: string;
    predict?: boolean;
  }) => {
    // Starting fresh: end any previous backend session, then a new request token.
    const prev = sessionRef.current;
    if (prev) endSpecDrill(prev).catch(() => {});
    rememberSession(null);
    const { token, signal } = beginRequest();
    setError(null);
    setPhase("starting");
    setHotspots([]);
    setPath([]);
    setDepth(0);
    setLastServeMs(null);
    setFreeClick(null);
    try {
      await startSpecDrill(
        { ...seed, max_depth: maxDepth, hotspots: hotspotCount },
        drillEventHandler(token, performance.now(), false),
        signal
      );
    } catch (e) {
      if (isAbortError(e)) return;
      setError(e instanceof Error ? e.message : "Start failed");
      setPhase("idle");
    }
  };

  const handleStart = () => {
    if (!topic.trim()) return;
    setParentImg(null);
    runStart({ topic: topic.trim() });
  };

  const handleUpload = async (file: File) => {
    try {
      // Show the uploaded image immediately; the engine confirms it via `session`.
      setParentImg(URL.createObjectURL(file));
      const b64 = await fileToBase64(file);
      // predict:false -> the uploaded parent has NO hotspots; user free-clicks first.
      await runStart({ parent_image_b64: b64, predict: false });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
      setPhase("idle");
    }
  };

  // Click a predicted hotspot -> served instantly from the prefetch cache.
  // While a generation is already running we ignore the click (use Cancel to stop
  // it) — we never auto-kill an in-flight generation.
  const handleClick = async (h: Hotspot) => {
    if (!sessionRef.current || phase === "serving") return;
    const wasReady = h.status === "ready";
    const { token, signal } = beginRequest();
    setServingMode("instant");
    setPhase("serving");
    setError(null);
    try {
      await clickSpecDrill(
        sessionRef.current,
        h.hotspot_id,
        drillEventHandler(token, performance.now(), wasReady),
        signal
      );
    } catch (e) {
      if (isAbortError(e)) return;
      setError(e instanceof Error ? e.message : "Click failed");
      setPhase("ready");
    }
  };

  // Click anywhere that's NOT a hotspot -> generate that child on the fly.
  // Ignored while a generation is already running (Cancel stops the current one).
  const handleFreeClick = async (x: number, y: number) => {
    if (!sessionRef.current || phase === "serving") return;
    const { token, signal } = beginRequest();
    setFreeClick({ x, y });
    setServingMode("onfly");
    setPhase("serving");
    setError(null);
    try {
      await clickPointSpecDrill(
        sessionRef.current,
        x,
        y,
        drillEventHandler(token, performance.now(), false),
        signal
      );
    } catch (e) {
      if (isAbortError(e)) return;
      setFreeClick(null);
      setError(e instanceof Error ? e.message : "Generation failed");
      setPhase("ready");
    }
  };

  const onCanvasClick = (e: ReactMouseEvent<HTMLDivElement>) => {
    if (!sessionRef.current || phase === "serving") return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    handleFreeClick(Math.min(1, Math.max(0, x)), Math.min(1, Math.max(0, y)));
  };

  // Explicit kill — stop the current (mistaken) generation, stay on this layer.
  const handleCancel = () => {
    abortRef.current?.abort();
    tokenRef.current += 1; // ignore any late events from the killed stream
    setFreeClick(null);
    setPhase("ready");
  };

  // Go back up to the previous depth and re-offer its hotspots.
  const handleBack = async () => {
    const sid = sessionRef.current;
    if (!sid || depth < 1 || phase === "serving") return;
    const { token, signal } = beginRequest();
    setError(null);
    setFreeClick(null);
    try {
      await backSpecDrill(sid, drillEventHandler(token, performance.now(), false), signal);
    } catch (e) {
      if (isAbortError(e)) return;
      setError(e instanceof Error ? e.message : "Back failed");
    }
  };

  const handleEnd = async () => {
    abortRef.current?.abort();
    tokenRef.current += 1; // invalidate any late events
    const sid = sessionRef.current;
    if (sid) endSpecDrill(sid).catch(() => {});
    rememberSession(null);
    setParentImg(null);
    setHotspots([]);
    setPath([]);
    setDepth(0);
    setPhase("idle");
    setLastServeMs(null);
    setFreeClick(null);
  };

  return (
    <div className="spec-mode">
      <aside className="spec-sidebar">
        <h2>Speculative Drill</h2>
        <p className="hint">
          Hotspots are pre-generated in parallel across worker Macs — click one for
          an instant drill, or click anywhere else to generate that point on the fly.
        </p>

        <div className="control-group">
          <label>Topic</label>
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. a wristwatch"
            onKeyDown={(e) => e.key === "Enter" && phase === "idle" && handleStart()}
            disabled={phase !== "idle"}
          />
        </div>

        <div className="spec-controls-row">
          <div className="control-group">
            <label>Max depth</label>
            <input
              type="number"
              min={1}
              max={6}
              value={maxDepth}
              onChange={(e) => setMaxDepth(Number(e.target.value))}
              disabled={phase !== "idle"}
            />
          </div>
          <div className="control-group">
            <label>Hotspots</label>
            <input
              type="number"
              min={2}
              max={8}
              value={hotspotCount}
              onChange={(e) => setHotspotCount(Number(e.target.value))}
              disabled={phase !== "idle"}
            />
          </div>
        </div>

        {phase === "idle" ? (
          <>
            <button className="spec-btn primary" onClick={handleStart} disabled={!topic.trim()}>
              <Wand2 size={16} /> Start from topic
            </button>
            <div className="spec-or">or</div>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              hidden
              onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
            />
            <button className="spec-btn" onClick={() => fileRef.current?.click()}>
              <Upload size={16} /> Upload an image
            </button>
          </>
        ) : (
          <button className="spec-btn" onClick={handleEnd}>
            <Square size={14} /> End session
          </button>
        )}

        {phase !== "idle" && (
          <div className="spec-stat-card">
            <div className="spec-stat-row">
              <span>Depth</span>
              <strong>
                {depth} / {maxDepth}
              </strong>
            </div>
            <div className="spec-stat-row">
              <span>Prefetched</span>
              <strong>
                {readyCount} / {hotspots.length || "—"} ready
              </strong>
            </div>
            {lastServeMs !== null && (
              <div className={`spec-serve-badge ${lastWasInstant ? "instant" : ""}`}>
                <Zap size={13} />
                {lastWasInstant
                  ? `Instant — main cache · from ${shortWorker(lastWorker)} (${lastServeMs} ms)`
                  : `On the fly · ${shortWorker(lastWorker)} (${lastServeMs} ms)`}
              </div>
            )}
            <div className="spec-action-row">
              <button
                className="spec-mini-btn"
                onClick={handleBack}
                disabled={depth < 1 || phase === "serving"}
                title="Go back to the previous depth"
              >
                <ChevronLeft size={14} /> Back
              </button>
              {phase === "serving" && (
                <button className="spec-mini-btn danger" onClick={handleCancel}>
                  <X size={14} /> Cancel
                </button>
              )}
            </div>
          </div>
        )}

        {path.length > 0 && (
          <div className="spec-path">
            <span className="spec-path-label">Path</span>
            <div className="spec-path-chips">
              {path.map((label, i) => (
                <span key={i} className="spec-chip">
                  {label}
                </span>
              ))}
            </div>
          </div>
        )}

        {error && <p className="spec-error">{error}</p>}

        <div className="spec-legend">
          <span><i className="dot pending" /> prefetching</span>
          <span><i className="dot ready" /> ready (instant)</span>
          <span><i className="dot error" /> failed</span>
        </div>
      </aside>

      <section className="spec-main">
        {!parentImg ? (
          <div className="spec-empty">
            {phase === "starting" ? (
              <>
                <Loader2 className="spin" size={28} />
                <p>Generating the first image…</p>
              </>
            ) : (
              <>
                <p>Enter a topic or upload an image to start.</p>
                <p className="hint">
                  Either way, the same pipeline runs: hotspots light up green as
                  they’re pre-generated in the background — then clicking one is instant.
                </p>
              </>
            )}
          </div>
        ) : (
          <div className="spec-stage">
            <div
              className={`spec-canvas ${sessionId && !busy ? "clickable" : ""}`}
              onClick={onCanvasClick}
              title="Click a hotspot for an instant drill, or anywhere else to generate on the fly"
            >
              <img src={parentImg} alt="current layer" className="spec-image" />
              {hotspots.map((h) => (
                <button
                  key={h.hotspot_id}
                  className={`spec-hotspot ${h.status}`}
                  style={{ left: `${h.x * 100}%`, top: `${h.y * 100}%` }}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleClick(h);
                  }}
                  title={`${h.label} — ${h.status}`}
                >
                  <span className="spec-hotspot-dot">
                    {h.status === "ready" ? (
                      <Check size={12} />
                    ) : h.status === "error" ? (
                      <X size={12} />
                    ) : (
                      h.rank
                    )}
                  </span>
                  <span className="spec-hotspot-label">{h.label}</span>
                </button>
              ))}
              {freeClick && (
                <span
                  className="spec-freeclick-ring"
                  style={{ left: `${freeClick.x * 100}%`, top: `${freeClick.y * 100}%` }}
                />
              )}
              {phase === "serving" && (
                <div className="spec-overlay">
                  <Loader2 className="spin" size={24} />
                  {servingMode === "onfly" ? "generating on the fly…" : "serving…"}
                </div>
              )}
            </div>
            {phase === "complete" && (
              <div className="spec-complete">Reached max depth — session complete.</div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
