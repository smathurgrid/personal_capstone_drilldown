// // App.jsx
// // ─────────────────────────────────────────────────────────────
// // REACT BEGINNER GUIDE:
// //
// // In React, a "component" is just a JavaScript function that
// // returns HTML-like code called JSX. This file is your whole app.
// //
// // Key concepts used here:
// //  • useState  — stores values that can change (like variables
// //                that automatically re-render the UI when updated)
// //  • useRef    — gets a direct reference to a real DOM element
// //                (like document.getElementById but the React way)
// //  • useEffect — runs code AFTER the component renders
// //                (used here for the canvas drawing and health check)
// // ─────────────────────────────────────────────────────────────

// import { useState, useRef, useEffect } from 'react'
// import './App.css'

// // The URL of your FastAPI backend. Change the port if needed.
// const API = 'http://localhost:8001'

// // ─── Helper: draw the scanning reticle on the canvas ─────────
// function drawReticle(canvas, img, dx, dy) {
//   const rect = img.getBoundingClientRect()
//   canvas.width  = rect.width
//   canvas.height = rect.height
//   const ctx = canvas.getContext('2d')
//   ctx.clearRect(0, 0, canvas.width, canvas.height)

//   const R = 44   // outer ring radius

//   // Outer dashed ring
//   ctx.strokeStyle = '#ff2d55'
//   ctx.lineWidth   = 2
//   ctx.setLineDash([7, 4])
//   ctx.beginPath()
//   ctx.arc(dx, dy, R, 0, Math.PI * 2)
//   ctx.stroke()

//   // Four crosshair arms (gaps near center so the dot is visible)
//   ctx.setLineDash([])
//   ctx.lineWidth = 1.5
//   const GAP = 10
//   const ARM = 22
//   ;[
//     [dx - R - ARM, dy, dx - R - GAP, dy],
//     [dx + R + GAP, dy, dx + R + ARM, dy],
//     [dx, dy - R - ARM, dx, dy - R - GAP],
//     [dx, dy + R + GAP, dx, dy + R + ARM],
//   ].forEach(([x1, y1, x2, y2]) => {
//     ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke()
//   })

//   // Corner ticks inside the ring (top-left, top-right, etc.)
//   const TICK = 14
//   const ANGLE_OFFSETS = [0.15, Math.PI / 2 - 0.15]
//   const corners = [
//     [0.15,                  Math.PI / 2 - 0.15],
//     [Math.PI / 2 + 0.15,   Math.PI     - 0.15],
//     [Math.PI + 0.15,       (3 * Math.PI) / 2 - 0.15],
//     [(3 * Math.PI) / 2 + 0.15, Math.PI * 2 - 0.15],
//   ]
//   ctx.lineWidth = 2.5
//   corners.forEach(([a1, a2]) => {
//     const ix1 = dx + R * Math.cos(a1)
//     const iy1 = dy + R * Math.sin(a1)
//     const ix2 = dx + R * Math.cos(a2)
//     const iy2 = dy + R * Math.sin(a2)
//     ctx.beginPath(); ctx.moveTo(ix1, iy1)
//     ctx.arc(dx, dy, R, a1, a2); ctx.stroke()
//   })

//   // Center dot
//   ctx.fillStyle = '#ff2d55'
//   ctx.beginPath()
//   ctx.arc(dx, dy, 4, 0, Math.PI * 2)
//   ctx.fill()

//   // Coordinate label
//   ctx.font      = '11px JetBrains Mono, monospace'
//   ctx.fillStyle = '#ff2d5599'
//   ctx.fillText(`${Math.round(dx)}, ${Math.round(dy)}`, dx + R + 8, dy - 4)
// }
// // ── ADD THIS ENTIRE FUNCTION ABOVE export default function App() ──
// async function compressImage(file, maxSizePx = 1200) {
//   return new Promise((resolve) => {
//     const img = new Image()
//     img.onload = () => {
//       const canvas = document.createElement("canvas")
//       let w = img.naturalWidth
//       let h = img.naturalHeight
//       if (w > maxSizePx || h > maxSizePx) {
//         if (w > h) { h = Math.round(h * maxSizePx / w); w = maxSizePx }
//         else       { w = Math.round(w * maxSizePx / h); h = maxSizePx }
//       }
//       canvas.width  = w
//       canvas.height = h
//       canvas.getContext("2d").drawImage(img, 0, 0, w, h)
//       canvas.toBlob(resolve, "image/jpeg", 0.85)
//     }
//     img.src = URL.createObjectURL(file)
//   })
// }



// // ─── Main App Component ───────────────────────────────────────
// export default function App() {

//   // ── STATE ──────────────────────────────────────────────────
//   // useState(initialValue) returns [currentValue, setterFunction]
//   // Calling the setter re-renders the UI automatically.

//   const [ollamaOk,    setOllamaOk]    = useState(null)    // null=checking, true=ok, false=error
//   const [imageFile,   setImageFile]   = useState(null)    // the File object from <input>
//   const [imageUrl,    setImageUrl]    = useState(null)    // object URL to display the image
//   const [clickPoint,  setClickPoint]  = useState(null)    // {x,y} in actual image pixels
//   const [displayPt,   setDisplayPt]   = useState(null)    // {x,y} in displayed pixels
//   const [phase,       setPhase]       = useState('upload') // current step in the flow
//   const [analysis,    setAnalysis]    = useState(null)    // response from /api/analyze
//   const [generated,   setGenerated]   = useState(null)    // base64 of the generated image
//   const [error,       setError]       = useState(null)    // error message string or null

//   // ── REFS ────────────────────────────────────────────────────
//   // useRef gives you a "pointer" to a real DOM element.
//   // ref.current is the actual element (like document.getElementById).

//   const imgRef       = useRef(null)   // points to the <img> element
//   const canvasRef    = useRef(null)   // points to the <canvas> on top of the image
//   const fileInputRef = useRef(null)   // points to the hidden <input type="file">

//   // ── EFFECTS ─────────────────────────────────────────────────
//   // useEffect(fn, [deps]) runs fn after render.
//   // The [] means "run only once, on first mount" (like componentDidMount).

//   // Check if Ollama is running when the page first loads
//   useEffect(() => {
//     fetch(`${API}/api/health`)
//       .then(r => r.json())
//       .then(d => setOllamaOk(d.ollama))
//       .catch(() => setOllamaOk(false))
//   }, [])

//   // Redraw the canvas marker whenever the display coordinates change
//   useEffect(() => {
//     if (!displayPt || !canvasRef.current || !imgRef.current) return
//     drawReticle(canvasRef.current, imgRef.current, displayPt.x, displayPt.y)
//   }, [displayPt])


//   // ── EVENT HANDLERS ───────────────────────────────────────────

//   // Called when the user picks a file from the file input
//   function handleFileChange(e) {
//     const file = e.target.files[0]
//     if (!file) return

//     // Create a temporary URL to display the image in the browser
//     const url = URL.createObjectURL(file)

//     setImageFile(file)
//     setImageUrl(url)
//     setClickPoint(null)
//     setDisplayPt(null)
//     setAnalysis(null)
//     setGenerated(null)
//     setError(null)
//     setPhase('select')

//     // Clear any old canvas drawing
//     if (canvasRef.current) {
//       const ctx = canvasRef.current.getContext('2d')
//       ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height)
//     }
//   }

//   // Called when the user clicks on the displayed image
//   function handleImageClick(e) {
//     // Don't allow re-clicking while processing
//     if (phase === 'analyzing' || phase === 'generating') return

//     const img  = imgRef.current
//     const rect = img.getBoundingClientRect()

//     // Where the user clicked in the DISPLAYED image (pixels on screen)
//     const displayX = e.clientX - rect.left
//     const displayY = e.clientY - rect.top

//     // Scale to the ACTUAL image dimensions (the image may be scaled down to fit)
//     const scaleX  = img.naturalWidth  / rect.width
//     const scaleY  = img.naturalHeight / rect.height
//     const actualX = Math.round(displayX * scaleX)
//     const actualY = Math.round(displayY * scaleY)

//     setClickPoint({ x: actualX,  y: actualY  })   // actual coords → sent to backend
//     setDisplayPt( { x: displayX, y: displayY })    // display coords → drawn on canvas
//     setPhase('point-selected')
//     setAnalysis(null)
//     setGenerated(null)
//     setError(null)
//   }

//   // Called when the user clicks "Analyze Region"
//   async function handleAnalyze() {
//     if (!imageFile || !clickPoint) return
//     setPhase('analyzing')
//     setError(null)

//     // FormData is how you send files + text fields together in one request
//     const fd = new FormData()
//     fd.append('image',  imageFile)
//     fd.append('x',      clickPoint.x)
//     fd.append('y',      clickPoint.y)
//     fd.append('radius', 80)

//     try {
//       const res  = await fetch(`${API}/api/analyze`, { method: 'POST', body: fd })
//       if (!res.ok) throw new Error(`Server error: ${await res.text()}`)
//       const data = await res.json()
//       setAnalysis(data)
//       setPhase('analyzed')
//     } catch (e) {
//       setError(e.message)
//       setPhase('point-selected')
//     }
//   }

//   // Called when the user clicks "Generate Drill-Down"
//   async function handleGenerate() {
//     if (!analysis) return
//     setPhase('generating')
//     setError(null)

//     const fd = new FormData()
//     fd.append('prompt',         analysis.image_prompt)
//     fd.append('local_crop_b64', analysis.local_crop_b64)
//     fd.append('global_b64',     analysis.marked_image_b64)

//     try {
//       const res  = await fetch(`${API}/api/generate`, { method: 'POST', body: fd })
//       if (!res.ok) throw new Error(`Server error: ${await res.text()}`)
//       const data = await res.json()
//       setGenerated(data.image_b64)
//       setPhase('done')
//     } catch (e) {
//       setError(e.message)
//       setPhase('analyzed')
//     }
//   }

//   // Reset everything back to start
//   function handleReset() {
//     setImageFile(null)
//     setImageUrl(null)
//     setClickPoint(null)
//     setDisplayPt(null)
//     setAnalysis(null)
//     setGenerated(null)
//     setError(null)
//     setPhase('upload')
//   }

//   // ── RENDER ──────────────────────────────────────────────────
//   // JSX looks like HTML but it's actually JavaScript.
//   // Rules:
//   //  • className instead of class
//   //  • {expression} to embed JS values
//   //  • onClick, onChange etc. for event handlers

//   return (
//     <div className="app">

//       {/* ── Header ── */}
//       <header className="header">
//         <div className="header-inner">
//           <div className="logo">
//             <span className="logo-icon">◎</span>
//             <span className="logo-text">SEMANTIC<span className="logo-accent"> DRILL DOWN</span></span>
//           </div>

//           {/* Ollama status badge */}
//           <div className={`status-badge ${ollamaOk === true ? 'ok' : ollamaOk === false ? 'err' : 'checking'}`}>
//             <span className="status-dot" />
//             {ollamaOk === null  && 'Connecting…'}
//             {ollamaOk === true  && 'Ollama ready'}
//             {ollamaOk === false && 'Ollama offline'}
//           </div>
//         </div>

//         {/* Step tracker */}
//         <StepTracker phase={phase} />
//       </header>

//       {/* ── Main layout: left panel + right panel ── */}
//       <main className="main">

//         {/* ═══ LEFT PANEL ═══ */}
//         <section className="panel left-panel">
//           <div className="panel-label">INPUT</div>

//           {/* Hidden file input — triggered by the button below */}
//           <input
//             ref={fileInputRef}
//             type="file"
//             accept="image/png,image/jpeg,image/webp"
//             onChange={handleFileChange}
//             style={{ display: 'none' }}
//           />

//           {/* Upload drop zone (or "change image" button) */}
//           {!imageUrl ? (
//             <div className="dropzone" onClick={() => fileInputRef.current.click()}>
//               <div className="dropzone-icon">⊕</div>
//               <p className="dropzone-title">Upload Image</p>
//               <p className="dropzone-hint">PNG, JPG, WEBP supported</p>
//             </div>
//           ) : (
//             <button className="btn-ghost small" onClick={() => fileInputRef.current.click()}>
//               ↺ Change Image
//             </button>
//           )}

//           {/* Image display + canvas overlay */}
//           {imageUrl && (
//             <div className="image-container">
//               {/* Instruction banner */}
//               <div className="image-hint">
//                 {phase === 'select' && '↓ Click anywhere on the image to select a region'}
//                 {phase === 'point-selected' && `✓ Region selected at (${clickPoint?.x}, ${clickPoint?.y})`}
//                 {phase === 'analyzing'  && '⟳ Analyzing region…'}
//                 {phase === 'analyzed'   && '✓ Analysis complete — generate below'}
//                 {phase === 'generating' && '⟳ Generating drill-down…'}
//                 {phase === 'done'       && '✓ Done! See result on the right'}
//               </div>

//               {/* Wrapper so canvas can be positioned on top of img */}
//               <div className="img-wrapper">
//                 <img
//                   ref={imgRef}
//                   src={imageUrl}
//                   alt="Uploaded"
//                   className={`main-img ${phase === 'select' || phase === 'point-selected' ? 'clickable' : ''}`}
//                   onClick={handleImageClick}
//                   draggable={false}
//                 />
//                 {/* Canvas overlaid on the image — pointer-events:none lets clicks pass through */}
//                 <canvas ref={canvasRef} className="reticle-canvas" />
//               </div>

//               {/* Show the local crop preview after analysis */}
//               {analysis?.local_crop_b64 && (
//                 <div className="crop-preview">
//                   <span className="crop-label">LOCAL CROP</span>
//                   <img
//                     src={`data:image/png;base64,${analysis.local_crop_b64}`}
//                     alt="Cropped region"
//                     className="crop-img"
//                   />
//                 </div>
//               )}
//             </div>
//           )}

//           {/* ── Action buttons ── */}
//           <div className="action-row">
//             {phase === 'point-selected' && (
//               <button className="btn-primary" onClick={handleAnalyze}>
//                 <span>⬡</span> Analyze Region
//               </button>
//             )}
//             {phase === 'analyzing' && (
//               <button className="btn-primary loading" disabled>
//                 <span className="spinner" /> Analyzing…
//               </button>
//             )}
//             {phase === 'analyzed' && (
//               <button className="btn-primary" onClick={handleGenerate}>
//                 <span>✦</span> Generate Drill-Down
//               </button>
//             )}
//             {phase === 'generating' && (
//               <button className="btn-primary loading" disabled>
//                 <span className="spinner" /> Generating…
//               </button>
//             )}
//             {(phase === 'done' || analysis) && (
//               <button className="btn-ghost" onClick={handleReset}>
//                 ← Start Over
//               </button>
//             )}
//           </div>

//           {/* Error display */}
//           {error && (
//             <div className="error-box">
//               <span className="error-icon">⚠</span>
//               <span>{error}</span>
//             </div>
//           )}
//         </section>

//         {/* ═══ RIGHT PANEL ═══ */}
//         <section className="panel right-panel">
//           <div className="panel-label">OUTPUT</div>

//           {/* Empty state */}
//           {!analysis && !generated && (
//             <div className="empty-state">
//               <div className="empty-icon">◎</div>
//               <p>Upload an image and click a region<br />to begin semantic exploration</p>
//             </div>
//           )}

//           {/* Analysis result */}
//           {analysis && (
//             <div className="result-block">
//               <div className="result-section">
//                 <h3 className="result-title">
//                   <span className="result-dot" style={{background:'var(--teal)'}} />
//                   SEMANTIC ANALYSIS
//                 </h3>
//                 <p className="result-text">{analysis.analysis}</p>
//               </div>

//               <div className="result-section">
//                 <h3 className="result-title">
//                   <span className="result-dot" style={{background:'var(--amber)'}} />
//                   IMAGE PROMPT
//                 </h3>
//                 <p className="prompt-text">{analysis.image_prompt}</p>
//               </div>
//             </div>
//           )}

//           {/* Generated image */}
//           {generated && (
//             <div className="generated-block">
//               <div className="result-section">
//                 <h3 className="result-title">
//                   <span className="result-dot" style={{background:'var(--red)'}} />
//                   DRILL-DOWN IMAGE
//                 </h3>
//               </div>
//               <img
//                 src={`data:image/png;base64,${generated}`}
//                 alt="Generated drill-down"
//                 className="generated-img"
//               />
//               {/* Download button */}
//               <a
//                 href={`data:image/png;base64,${generated}`}
//                 download="drilldown.png"
//                 className="btn-download"
//               >
//                 ⬇ Download Image
//               </a>
//             </div>
//           )}
//         </section>
//       </main>
//     </div>
//   )
// }


// // ─── StepTracker Sub-component ────────────────────────────────
// // A small component just for the step progress bar.
// // Defining it here keeps things simple for a beginner project.

// const STEPS = [
//   { key: 'upload',         label: '01 Upload'  },
//   { key: 'select',         label: '02 Select'  },
//   { key: 'point-selected', label: '02 Select'  },   // same visual step
//   { key: 'analyzing',      label: '03 Analyze' },
//   { key: 'analyzed',       label: '03 Analyze' },
//   { key: 'generating',     label: '04 Generate'},
//   { key: 'done',           label: '04 Generate'},
// ]

// // Map each phase to its numbered step (0-indexed)
// const PHASE_STEP = {
//   upload: 0, select: 1, 'point-selected': 1,
//   analyzing: 2, analyzed: 2, generating: 3, done: 3,
// }

// function StepTracker({ phase }) {
//   const current = PHASE_STEP[phase] ?? 0
//   const labels  = ['Upload', 'Select Region', 'Analyze', 'Generate']

//   return (
//     <div className="step-tracker">
//       {labels.map((label, i) => (
//         <div
//           key={i}
//           className={`step ${i < current ? 'done' : i === current ? 'active' : 'pending'}`}
//         >
//           <div className="step-dot">
//             {i < current ? '✓' : <span>{i + 1}</span>}
//           </div>
//           <span className="step-label">{label}</span>
//           {i < labels.length - 1 && <div className="step-line" />}
//         </div>
//       ))}
//     </div>
//   )
// }
// ------attempt 2----
// // App.jsx
// import { useState, useRef, useEffect } from 'react'
// import './App.css'

// const API = 'http://localhost:8001'

// function drawReticle(canvas, img, dx, dy) {
//   const rect = img.getBoundingClientRect()
//   canvas.width  = rect.width
//   canvas.height = rect.height
//   const ctx = canvas.getContext('2d')
//   ctx.clearRect(0, 0, canvas.width, canvas.height)

//   const R = 44

//   ctx.strokeStyle = '#ff2d55'
//   ctx.lineWidth   = 2
//   ctx.setLineDash([7, 4])
//   ctx.beginPath()
//   ctx.arc(dx, dy, R, 0, Math.PI * 2)
//   ctx.stroke()

//   ctx.setLineDash([])
//   ctx.lineWidth = 1.5
//   const GAP = 10
//   const ARM = 22
//   ;[
//     [dx - R - ARM, dy, dx - R - GAP, dy],
//     [dx + R + GAP, dy, dx + R + ARM, dy],
//     [dx, dy - R - ARM, dx, dy - R - GAP],
//     [dx, dy + R + GAP, dx, dy + R + ARM],
//   ].forEach(([x1, y1, x2, y2]) => {
//     ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke()
//   })

//   const corners = [
//     [0.15,                      Math.PI / 2 - 0.15],
//     [Math.PI / 2 + 0.15,        Math.PI     - 0.15],
//     [Math.PI + 0.15,            (3 * Math.PI) / 2 - 0.15],
//     [(3 * Math.PI) / 2 + 0.15,  Math.PI * 2 - 0.15],
//   ]
//   ctx.lineWidth = 2.5
//   corners.forEach(([a1, a2]) => {
//     ctx.beginPath()
//     ctx.arc(dx, dy, R, a1, a2)
//     ctx.stroke()
//   })

//   ctx.fillStyle = '#ff2d55'
//   ctx.beginPath()
//   ctx.arc(dx, dy, 4, 0, Math.PI * 2)
//   ctx.fill()

//   ctx.font      = '11px JetBrains Mono, monospace'
//   ctx.fillStyle = '#ff2d5599'
//   ctx.fillText(`${Math.round(dx)}, ${Math.round(dy)}`, dx + R + 8, dy - 4)
// }

// // ── Compress image before sending to backend ──
// async function compressImage(file, maxSizePx = 1200) {
//   return new Promise((resolve) => {
//     const img = new Image()
//     img.onload = () => {
//       const canvas = document.createElement('canvas')
//       let w = img.naturalWidth
//       let h = img.naturalHeight
//       if (w > maxSizePx || h > maxSizePx) {
//         if (w > h) { h = Math.round(h * maxSizePx / w); w = maxSizePx }
//         else       { w = Math.round(w * maxSizePx / h); h = maxSizePx }
//       }
//       canvas.width  = w
//       canvas.height = h
//       canvas.getContext('2d').drawImage(img, 0, 0, w, h)
//       canvas.toBlob(resolve, 'image/jpeg', 0.85)
//     }
//     img.src = URL.createObjectURL(file)
//   })
// }

// export default function App() {

//   const [ollamaOk,    setOllamaOk]    = useState(null)
//   const [imageFile,   setImageFile]   = useState(null)
//   const [imageUrl,    setImageUrl]    = useState(null)
//   const [clickPoint,  setClickPoint]  = useState(null)
//   const [displayPt,   setDisplayPt]   = useState(null)
//   const [phase,       setPhase]       = useState('upload')
//   const [analysis,    setAnalysis]    = useState(null)
//   const [generated,   setGenerated]   = useState(null)
//   const [error,       setError]       = useState(null)

//   const imgRef       = useRef(null)
//   const canvasRef    = useRef(null)
//   const fileInputRef = useRef(null)

//   useEffect(() => {
//     fetch(`${API}/api/health`)
//       .then(r => r.json())
//       .then(d => setOllamaOk(d.ollama))
//       .catch(() => setOllamaOk(false))
//   }, [])

//   useEffect(() => {
//     if (!displayPt || !canvasRef.current || !imgRef.current) return
//     drawReticle(canvasRef.current, imgRef.current, displayPt.x, displayPt.y)
//   }, [displayPt])

//   function handleFileChange(e) {
//     const file = e.target.files[0]
//     if (!file) return
//     const url = URL.createObjectURL(file)
//     setImageFile(file)
//     setImageUrl(url)
//     setClickPoint(null)
//     setDisplayPt(null)
//     setAnalysis(null)
//     setGenerated(null)
//     setError(null)
//     setPhase('select')
//     if (canvasRef.current) {
//       const ctx = canvasRef.current.getContext('2d')
//       ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height)
//     }
//   }

//   function handleImageClick(e) {
//     if (phase === 'analyzing' || phase === 'generating') return
//     const img  = imgRef.current
//     const rect = img.getBoundingClientRect()
//     const displayX = e.clientX - rect.left
//     const displayY = e.clientY - rect.top
//     const scaleX  = img.naturalWidth  / rect.width
//     const scaleY  = img.naturalHeight / rect.height
//     const actualX = Math.round(displayX * scaleX)
//     const actualY = Math.round(displayY * scaleY)
//     setClickPoint({ x: actualX,  y: actualY  })
//     setDisplayPt( { x: displayX, y: displayY })
//     setPhase('point-selected')
//     setAnalysis(null)
//     setGenerated(null)
//     setError(null)
//   }

//   // ── CHANGED: compress image before sending ──
//   async function handleAnalyze() {
//     if (!imageFile || !clickPoint) return
//     setPhase('analyzing')
//     setError(null)

//     // ← NEW: compress before sending so it stays under the size limit
//     const compressed = await compressImage(imageFile)

//     const fd = new FormData()
//     fd.append('image',  compressed, 'image.jpg')  // ← CHANGED: was imageFile
//     fd.append('x',      clickPoint.x)
//     fd.append('y',      clickPoint.y)
//     fd.append('radius', 80)

//     try {
//       const res  = await fetch(`${API}/api/analyze`, { method: 'POST', body: fd })
//       if (!res.ok) throw new Error(`Server error: ${await res.text()}`)
//       const data = await res.json()
//       setAnalysis(data)
//       setPhase('analyzed')
//     } catch (e) {
//       setError(e.message)
//       setPhase('point-selected')
//     }
//   }

//   // handleGenerate unchanged — it sends base64 strings not a file
//   async function handleGenerate() {
//     if (!analysis) return
//     setPhase('generating')
//     setError(null)

//     const fd = new FormData()
//     fd.append('prompt',         analysis.image_prompt)
//     fd.append('local_crop_b64', analysis.local_crop_b64)
//     fd.append('global_b64',     analysis.marked_image_b64)

//     try {
//       const res  = await fetch(`${API}/api/generate`, { method: 'POST', body: fd })
//       if (!res.ok) throw new Error(`Server error: ${await res.text()}`)
//       const data = await res.json()
//       setGenerated(data.image_b64)
//       setPhase('done')
//     } catch (e) {
//       setError(e.message)
//       setPhase('analyzed')
//     }
//   }

//   function handleReset() {
//     setImageFile(null)
//     setImageUrl(null)
//     setClickPoint(null)
//     setDisplayPt(null)
//     setAnalysis(null)
//     setGenerated(null)
//     setError(null)
//     setPhase('upload')
//   }
// // async function handleGenerate() {
// //   if (!analysis || !imageFile || !clickPoint) return
// //   setPhase('generating')
// //   setError(null)

// //   // Compress before sending
// //   const compressed = await compressImage(imageFile)

// //   const fd = new FormData()
// //   fd.append('image',  compressed, 'image.jpg')  // file, not base64
// //   fd.append('x',      clickPoint.x)
// //   fd.append('y',      clickPoint.y)
// //   fd.append('prompt', analysis.image_prompt)

// //   try {
// //     const res  = await fetch(`${API}/api/generate`, { method: 'POST', body: fd })
// //     if (!res.ok) throw new Error(`Server error: ${await res.text()}`)
// //     const data = await res.json()
// //     setGenerated(data.image_b64)
// //     setPhase('done')
// //   } catch (e) {
// //     setError(e.message)
// //     setPhase('analyzed')
// //   }
// // }
//   return (
//     <div className="app">

//       <header className="header">
//         <div className="header-inner">
//           <div className="logo">
//             <span className="logo-icon">◎</span>
//             <span className="logo-text">SEMANTIC<span className="logo-accent"> DRILL DOWN</span></span>
//           </div>
//           <div className={`status-badge ${ollamaOk === true ? 'ok' : ollamaOk === false ? 'err' : 'checking'}`}>
//             <span className="status-dot" />
//             {ollamaOk === null  && 'Connecting…'}
//             {ollamaOk === true  && 'Ollama ready'}
//             {ollamaOk === false && 'Ollama offline'}
//           </div>
//         </div>
//         <StepTracker phase={phase} />
//       </header>

//       <main className="main">

//         <section className="panel left-panel">
//           <div className="panel-label">INPUT</div>

//           <input
//             ref={fileInputRef}
//             type="file"
//             accept="image/png,image/jpeg,image/webp"
//             onChange={handleFileChange}
//             style={{ display: 'none' }}
//           />

//           {!imageUrl ? (
//             <div className="dropzone" onClick={() => fileInputRef.current.click()}>
//               <div className="dropzone-icon">⊕</div>
//               <p className="dropzone-title">Upload Image</p>
//               <p className="dropzone-hint">PNG, JPG, WEBP supported</p>
//             </div>
//           ) : (
//             <button className="btn-ghost small" onClick={() => fileInputRef.current.click()}>
//               ↺ Change Image
//             </button>
//           )}

//           {imageUrl && (
//             <div className="image-container">
//               <div className="image-hint">
//                 {phase === 'select'         && '↓ Click anywhere on the image to select a region'}
//                 {phase === 'point-selected' && `✓ Region selected at (${clickPoint?.x}, ${clickPoint?.y})`}
//                 {phase === 'analyzing'      && '⟳ Compressing and analyzing region…'}
//                 {phase === 'analyzed'       && '✓ Analysis complete — generate below'}
//                 {phase === 'generating'     && '⟳ Generating drill-down…'}
//                 {phase === 'done'           && '✓ Done! See result on the right'}
//               </div>

//               <div className="img-wrapper">
//                 <img
//                   ref={imgRef}
//                   src={imageUrl}
//                   alt="Uploaded"
//                   className={`main-img ${phase === 'select' || phase === 'point-selected' ? 'clickable' : ''}`}
//                   onClick={handleImageClick}
//                   draggable={false}
//                 />
//                 <canvas ref={canvasRef} className="reticle-canvas" />
//               </div>

//               {analysis?.local_crop_b64 && (
//                 <div className="crop-preview">
//                   <span className="crop-label">LOCAL CROP</span>
//                   <img
//                     src={`data:image/png;base64,${analysis.local_crop_b64}`}
//                     alt="Cropped region"
//                     className="crop-img"
//                   />
//                 </div>
//               )}
//             </div>
//           )}

//           <div className="action-row">
//             {phase === 'point-selected' && (
//               <button className="btn-primary" onClick={handleAnalyze}>
//                 <span>⬡</span> Analyze Region
//               </button>
//             )}
//             {phase === 'analyzing' && (
//               <button className="btn-primary loading" disabled>
//                 <span className="spinner" /> Analyzing…
//               </button>
//             )}
//             {phase === 'analyzed' && (
//               <button className="btn-primary" onClick={handleGenerate}>
//                 <span>✦</span> Generate Drill-Down
//               </button>
//             )}
//             {phase === 'generating' && (
//               <button className="btn-primary loading" disabled>
//                 <span className="spinner" /> Generating…
//               </button>
//             )}
//             {(phase === 'done' || analysis) && (
//               <button className="btn-ghost" onClick={handleReset}>
//                 ← Start Over
//               </button>
//             )}
//           </div>

//           {error && (
//             <div className="error-box">
//               <span className="error-icon">⚠</span>
//               <span>{error}</span>
//             </div>
//           )}
//         </section>

//         <section className="panel right-panel">
//           <div className="panel-label">OUTPUT</div>

//           {!analysis && !generated && (
//             <div className="empty-state">
//               <div className="empty-icon">◎</div>
//               <p>Upload an image and click a region<br />to begin semantic exploration</p>
//             </div>
//           )}

//           {analysis && (
//             <div className="result-block">
//               <div className="result-section">
//                 <h3 className="result-title">
//                   <span className="result-dot" style={{background:'var(--teal)'}} />
//                   SEMANTIC ANALYSIS
//                 </h3>
//                 <p className="result-text">{analysis.analysis}</p>
//               </div>
//               <div className="result-section">
//                 <h3 className="result-title">
//                   <span className="result-dot" style={{background:'var(--amber)'}} />
//                   IMAGE PROMPT
//                 </h3>
//                 <p className="prompt-text">{analysis.image_prompt}</p>
//               </div>
//             </div>
//           )}

//           {generated && (
//             <div className="generated-block">
//               <div className="result-section">
//                 <h3 className="result-title">
//                   <span className="result-dot" style={{background:'var(--red)'}} />
//                   DRILL-DOWN IMAGE
//                 </h3>
//               </div>
//               <img
//                 src={`data:image/png;base64,${generated}`}
//                 alt="Generated drill-down"
//                 className="generated-img"
//               />
//               <a
//                 href={`data:image/png;base64,${generated}`}
//                 download="drilldown.png"
//                 className="btn-download"
//               >
//                 ⬇ Download Image
//               </a>
//             </div>
//           )}
//         </section>

//       </main>
//     </div>
//   )
// }

// const PHASE_STEP = {
//   upload: 0, select: 1, 'point-selected': 1,
//   analyzing: 2, analyzed: 2, generating: 3, done: 3,
// }

// function StepTracker({ phase }) {
//   const current = PHASE_STEP[phase] ?? 0
//   const labels  = ['Upload', 'Select Region', 'Analyze', 'Generate']
//   return (
//     <div className="step-tracker">
//       {labels.map((label, i) => (
//         <div
//           key={i}
//           className={`step ${i < current ? 'done' : i === current ? 'active' : 'pending'}`}
//         >
//           <div className="step-dot">
//             {i < current ? '✓' : <span>{i + 1}</span>}
//           </div>
//           <span className="step-label">{label}</span>
//           {i < labels.length - 1 && <div className="step-line" />}
//         </div>
//       ))}
//     </div>
//   )
// }


//------attempt 3----

// import { useState, useRef, useEffect } from 'react'
// import './App.css'

// const API = 'http://localhost:8000'

// function drawReticle(canvas, img, dx, dy) {
//   const rect = img.getBoundingClientRect()
//   canvas.width  = rect.width
//   canvas.height = rect.height
//   const ctx = canvas.getContext('2d')
//   ctx.clearRect(0, 0, canvas.width, canvas.height)

//   const R = 44

//   ctx.strokeStyle = '#ff2d55'
//   ctx.lineWidth   = 2
//   ctx.setLineDash([7, 4])
//   ctx.beginPath()
//   ctx.arc(dx, dy, R, 0, Math.PI * 2)
//   ctx.stroke()

//   ctx.setLineDash([])
//   ctx.lineWidth = 1.5
//   const GAP = 10
//   const ARM = 22
//   ;[
//     [dx - R - ARM, dy, dx - R - GAP, dy],
//     [dx + R + GAP, dy, dx + R + ARM, dy],
//     [dx, dy - R - ARM, dx, dy - R - GAP],
//     [dx, dy + R + GAP, dx, dy + R + ARM],
//   ].forEach(([x1, y1, x2, y2]) => {
//     ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke()
//   })

//   const corners = [
//     [0.15,                     Math.PI / 2 - 0.15],
//     [Math.PI / 2 + 0.15,       Math.PI     - 0.15],
//     [Math.PI + 0.15,           (3 * Math.PI) / 2 - 0.15],
//     [(3 * Math.PI) / 2 + 0.15, Math.PI * 2 - 0.15],
//   ]
//   ctx.lineWidth = 2.5
//   corners.forEach(([a1, a2]) => {
//     ctx.beginPath()
//     ctx.arc(dx, dy, R, a1, a2)
//     ctx.stroke()
//   })

//   ctx.fillStyle = '#ff2d55'
//   ctx.beginPath()
//   ctx.arc(dx, dy, 4, 0, Math.PI * 2)
//   ctx.fill()

//   ctx.font      = '11px JetBrains Mono, monospace'
//   ctx.fillStyle = '#ff2d5599'
//   ctx.fillText(`${Math.round(dx)}, ${Math.round(dy)}`, dx + R + 8, dy - 4)
// }

// // ── FIX: returns { blob, scaleX, scaleY } so the caller can remap
// // click coordinates from original-image space → compressed-image space.
// async function compressImage(file, maxSizePx = 1200) {
//   return new Promise((resolve) => {
//     const img = new Image()
//     img.onload = () => {
//       const canvas = document.createElement('canvas')
//       const origW  = img.naturalWidth
//       const origH  = img.naturalHeight
//       let w = origW
//       let h = origH
//       if (w > maxSizePx || h > maxSizePx) {
//         if (w > h) { h = Math.round(h * maxSizePx / w); w = maxSizePx }
//         else       { w = Math.round(w * maxSizePx / h); h = maxSizePx }
//       }
//       canvas.width  = w
//       canvas.height = h
//       canvas.getContext('2d').drawImage(img, 0, 0, w, h)
//       canvas.toBlob(
//         (blob) => resolve({ blob, scaleX: w / origW, scaleY: h / origH }),
//         'image/jpeg',
//         0.85,
//       )
//     }
//     img.src = URL.createObjectURL(file)
//   })
// }

// export default function App() {

//   const [ollamaOk,   setOllamaOk]   = useState(null)
//   const [imageFile,  setImageFile]  = useState(null)
//   const [imageUrl,   setImageUrl]   = useState(null)
//   const [clickPoint, setClickPoint] = useState(null)   // coords in ORIGINAL image pixels
//   const [displayPt,  setDisplayPt]  = useState(null)   // coords in CSS display pixels
//   const [phase,      setPhase]      = useState('upload')
//   const [analysis,   setAnalysis]   = useState(null)
//   const [generated,  setGenerated]  = useState(null)
//   const [error,      setError]      = useState(null)

//   const imgRef       = useRef(null)
//   const canvasRef    = useRef(null)
//   const fileInputRef = useRef(null)

//   useEffect(() => {
//     fetch(`${API}/api/health`)
//       .then(r => r.json())
//       .then(d => setOllamaOk(d.ollama))
//       .catch(() => setOllamaOk(false))
//   }, [])

//   useEffect(() => {
//     if (!displayPt || !canvasRef.current || !imgRef.current) return
//     drawReticle(canvasRef.current, imgRef.current, displayPt.x, displayPt.y)
//   }, [displayPt])

//   function handleFileChange(e) {
//     const file = e.target.files[0]
//     if (!file) return
//     setImageFile(file)
//     setImageUrl(URL.createObjectURL(file))
//     setClickPoint(null)
//     setDisplayPt(null)
//     setAnalysis(null)
//     setGenerated(null)
//     setError(null)
//     setPhase('select')
//     if (canvasRef.current) {
//       canvasRef.current.getContext('2d')
//         .clearRect(0, 0, canvasRef.current.width, canvasRef.current.height)
//     }
//   }

//   function handleImageClick(e) {
//     if (phase === 'analyzing' || phase === 'generating') return
//     const img      = imgRef.current
//     const rect     = img.getBoundingClientRect()
//     const displayX = e.clientX - rect.left
//     const displayY = e.clientY - rect.top
//     // Store coords in ORIGINAL (naturalWidth/Height) pixel space
//     const scaleX   = img.naturalWidth  / rect.width
//     const scaleY   = img.naturalHeight / rect.height
//     setClickPoint({ x: Math.round(displayX * scaleX), y: Math.round(displayY * scaleY) })
//     setDisplayPt( { x: displayX, y: displayY })
//     setPhase('point-selected')
//     setAnalysis(null)
//     setGenerated(null)
//     setError(null)
//   }

//   async function handleAnalyze() {
//     if (!imageFile || !clickPoint) return
//     setPhase('analyzing')
//     setError(null)

//     // Compress the image and get the scale factors applied
//     const { blob, scaleX, scaleY } = await compressImage(imageFile)

//     // ── KEY FIX ──────────────────────────────────────────────
//     // clickPoint is in original-image pixels.
//     // The backend receives the compressed image, so we MUST scale
//     // the coordinates to match, otherwise they fall outside the
//     // compressed canvas → PIL raises "Coordinate 'right' < 'left'".
//     const scaledX = Math.round(clickPoint.x * scaleX)
//     const scaledY = Math.round(clickPoint.y * scaleY)
//     // ─────────────────────────────────────────────────────────

//     const fd = new FormData()
//     fd.append('image',  blob, 'image.jpg')
//     fd.append('x',      scaledX)
//     fd.append('y',      scaledY)
//     fd.append('radius', 80)

//     try {
//       const res  = await fetch(`${API}/api/analyze`, { method: 'POST', body: fd })
//       if (!res.ok) throw new Error(`Server error: ${await res.text()}`)
//       const data = await res.json()
//       setAnalysis(data)
//       setPhase('analyzed')
//     } catch (e) {
//       setError(e.message)
//       setPhase('point-selected')
//     }
//   }

//   // Sends JSON (not FormData) to avoid Starlette's 1024 KB form-field limit
//   async function handleGenerate() {
//     if (!analysis) return
//     setPhase('generating')
//     setError(null)

//     try {
//       const res = await fetch(`${API}/api/generate`, {
//         method:  'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({
//           prompt:         analysis.image_prompt,
//           local_crop_b64: analysis.local_crop_b64,
//           global_b64:     analysis.marked_image_b64,
//         }),
//       })
//       if (!res.ok) throw new Error(`Server error: ${await res.text()}`)
//       const data = await res.json()
//       setGenerated(data.image_b64)
//       setPhase('done')
//     } catch (e) {
//       setError(e.message)
//       setPhase('analyzed')
//     }
//   }

//   function handleReset() {
//     setImageFile(null)
//     setImageUrl(null)
//     setClickPoint(null)
//     setDisplayPt(null)
//     setAnalysis(null)
//     setGenerated(null)
//     setError(null)
//     setPhase('upload')
//   }

//   return (
//     <div className="app">

//       <header className="header">
//         <div className="header-inner">
//           <div className="logo">
//             <span className="logo-icon">◎</span>
//             <span className="logo-text">SEMANTIC<span className="logo-accent"> DRILL DOWN</span></span>
//           </div>
//           <div className={`status-badge ${ollamaOk === true ? 'ok' : ollamaOk === false ? 'err' : 'checking'}`}>
//             <span className="status-dot" />
//             {ollamaOk === null  && 'Connecting…'}
//             {ollamaOk === true  && 'Ollama ready'}
//             {ollamaOk === false && 'Ollama offline'}
//           </div>
//         </div>
//         <StepTracker phase={phase} />
//       </header>

//       <main className="main">

//         <section className="panel left-panel">
//           <div className="panel-label">INPUT</div>

//           <input
//             ref={fileInputRef}
//             type="file"
//             accept="image/png,image/jpeg,image/webp"
//             onChange={handleFileChange}
//             style={{ display: 'none' }}
//           />

//           {!imageUrl ? (
//             <div className="dropzone" onClick={() => fileInputRef.current.click()}>
//               <div className="dropzone-icon">⊕</div>
//               <p className="dropzone-title">Upload Image</p>
//               <p className="dropzone-hint">PNG, JPG, WEBP supported</p>
//             </div>
//           ) : (
//             <button className="btn-ghost small" onClick={() => fileInputRef.current.click()}>
//               ↺ Change Image
//             </button>
//           )}

//           {imageUrl && (
//             <div className="image-container">
//               <div className="image-hint">
//                 {phase === 'select'         && '↓ Click anywhere on the image to select a region'}
//                 {phase === 'point-selected' && `✓ Region selected at (${clickPoint?.x}, ${clickPoint?.y})`}
//                 {phase === 'analyzing'      && '⟳ Analyzing region…'}
//                 {phase === 'analyzed'       && '✓ Analysis complete — generate below'}
//                 {phase === 'generating'     && '⟳ Generating drill-down…'}
//                 {phase === 'done'           && '✓ Done! See result on the right'}
//               </div>

//               <div className="img-wrapper">
//                 <img
//                   ref={imgRef}
//                   src={imageUrl}
//                   alt="Uploaded"
//                   className={`main-img ${phase === 'select' || phase === 'point-selected' ? 'clickable' : ''}`}
//                   onClick={handleImageClick}
//                   draggable={false}
//                 />
//                 <canvas ref={canvasRef} className="reticle-canvas" />
//               </div>

//               {analysis?.local_crop_b64 && (
//                 <div className="crop-preview">
//                   <span className="crop-label">LOCAL CROP</span>
//                   <img
//                     src={`data:image/png;base64,${analysis.local_crop_b64}`}
//                     alt="Cropped region"
//                     className="crop-img"
//                   />
//                 </div>
//               )}
//             </div>
//           )}

//           <div className="action-row">
//             {phase === 'point-selected' && (
//               <button className="btn-primary" onClick={handleAnalyze}>
//                 <span>⬡</span> Analyze Region
//               </button>
//             )}
//             {phase === 'analyzing' && (
//               <button className="btn-primary loading" disabled>
//                 <span className="spinner" /> Analyzing…
//               </button>
//             )}
//             {phase === 'analyzed' && (
//               <button className="btn-primary" onClick={handleGenerate}>
//                 <span>✦</span> Generate Drill-Down
//               </button>
//             )}
//             {phase === 'generating' && (
//               <button className="btn-primary loading" disabled>
//                 <span className="spinner" /> Generating…
//               </button>
//             )}
//             {(phase === 'done' || analysis) && (
//               <button className="btn-ghost" onClick={handleReset}>
//                 ← Start Over
//               </button>
//             )}
//           </div>

//           {error && (
//             <div className="error-box">
//               <span className="error-icon">⚠</span>
//               <span>{error}</span>
//             </div>
//           )}
//         </section>

//         <section className="panel right-panel">
//           <div className="panel-label">OUTPUT</div>

//           {!analysis && !generated && (
//             <div className="empty-state">
//               <div className="empty-icon">◎</div>
//               <p>Upload an image and click a region<br />to begin semantic exploration</p>
//             </div>
//           )}

//           {analysis && (
//             <div className="result-block">
//               <div className="result-section">
//                 <h3 className="result-title">
//                   <span className="result-dot" style={{background:'var(--teal)'}} />
//                   SEMANTIC ANALYSIS
//                 </h3>
//                 <p className="result-text">{analysis.analysis}</p>
//               </div>
//               <div className="result-section">
//                 <h3 className="result-title">
//                   <span className="result-dot" style={{background:'var(--amber)'}} />
//                   IMAGE PROMPT
//                 </h3>
//                 <p className="prompt-text">{analysis.image_prompt}</p>
//               </div>
//             </div>
//           )}

//           {generated && (
//             <div className="generated-block">
//               <div className="result-section">
//                 <h3 className="result-title">
//                   <span className="result-dot" style={{background:'var(--red)'}} />
//                   DRILL-DOWN IMAGE
//                 </h3>
//               </div>
//               <img
//                 src={`data:image/png;base64,${generated}`}
//                 alt="Generated drill-down"
//                 className="generated-img"
//               />
//               <a
//                 href={`data:image/png;base64,${generated}`}
//                 download="drilldown.png"
//                 className="btn-download"
//               >
//                 ⬇ Download Image
//               </a>
//             </div>
//           )}
//         </section>

//       </main>
//     </div>
//   )
// }

// const PHASE_STEP = {
//   upload: 0, select: 1, 'point-selected': 1,
//   analyzing: 2, analyzed: 2, generating: 3, done: 3,
// }

// function StepTracker({ phase }) {
//   const current = PHASE_STEP[phase] ?? 0
//   const labels  = ['Upload', 'Select Region', 'Analyze', 'Generate']
//   return (
//     <div className="step-tracker">
//       {labels.map((label, i) => (
//         <div
//           key={i}
//           className={`step ${i < current ? 'done' : i === current ? 'active' : 'pending'}`}
//         >
//           <div className="step-dot">
//             {i < current ? '✓' : <span>{i + 1}</span>}
//           </div>
//           <span className="step-label">{label}</span>
//           {i < labels.length - 1 && <div className="step-line" />}
//         </div>
//       ))}
//     </div>
//   )
// }


//attempt 4 
// import { useState, useRef, useEffect } from 'react'
// import './App.css'

// const API = 'http://localhost:8000'

// /* ── reticle drawing (unchanged) ─────────────────────────────── */
// function drawReticle(canvas, img, dx, dy) {
//   const rect = img.getBoundingClientRect()
//   canvas.width  = rect.width
//   canvas.height = rect.height
//   const ctx = canvas.getContext('2d')
//   ctx.clearRect(0, 0, canvas.width, canvas.height)
//   const R = 44
//   ctx.strokeStyle = '#ff2d55'
//   ctx.lineWidth   = 2
//   ctx.setLineDash([7, 4])
//   ctx.beginPath()
//   ctx.arc(dx, dy, R, 0, Math.PI * 2)
//   ctx.stroke()
//   ctx.setLineDash([])
//   ctx.lineWidth = 1.5
//   const GAP = 10, ARM = 22
//   ;[
//     [dx - R - ARM, dy, dx - R - GAP, dy],
//     [dx + R + GAP, dy, dx + R + ARM, dy],
//     [dx, dy - R - ARM, dx, dy - R - GAP],
//     [dx, dy + R + GAP, dx, dy + R + ARM],
//   ].forEach(([x1, y1, x2, y2]) => {
//     ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke()
//   })
//   const corners = [
//     [0.15, Math.PI / 2 - 0.15],
//     [Math.PI / 2 + 0.15, Math.PI - 0.15],
//     [Math.PI + 0.15, (3 * Math.PI) / 2 - 0.15],
//     [(3 * Math.PI) / 2 + 0.15, Math.PI * 2 - 0.15],
//   ]
//   ctx.lineWidth = 2.5
//   corners.forEach(([a1, a2]) => {
//     ctx.beginPath(); ctx.arc(dx, dy, R, a1, a2); ctx.stroke()
//   })
//   ctx.fillStyle = '#ff2d55'
//   ctx.beginPath(); ctx.arc(dx, dy, 4, 0, Math.PI * 2); ctx.fill()
//   ctx.font      = '11px JetBrains Mono, monospace'
//   ctx.fillStyle = '#ff2d5599'
//   ctx.fillText(`${Math.round(dx)}, ${Math.round(dy)}`, dx + R + 8, dy - 4)
// }

// /* ── image compression ───────────────────────────────────────── */
// async function compressImage(file, maxSizePx = 1200) {
//   return new Promise((resolve) => {
//     const img = new Image()
//     img.onload = () => {
//       const canvas = document.createElement('canvas')
//       const origW = img.naturalWidth, origH = img.naturalHeight
//       let w = origW, h = origH
//       if (w > maxSizePx || h > maxSizePx) {
//         if (w > h) { h = Math.round(h * maxSizePx / w); w = maxSizePx }
//         else       { w = Math.round(w * maxSizePx / h); h = maxSizePx }
//       }
//       canvas.width = w; canvas.height = h
//       canvas.getContext('2d').drawImage(img, 0, 0, w, h)
//       canvas.toBlob(
//         (blob) => resolve({ blob, scaleX: w / origW, scaleY: h / origH }),
//         'image/jpeg', 0.85,
//       )
//     }
//     img.src = URL.createObjectURL(file)
//   })
// }

// /* ── b64 string → File object (for generated images used as parents) */
// function b64ToFile(b64, filename = 'image.png') {
//   const bin = atob(b64)
//   const arr = new Uint8Array(bin.length)
//   for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i)
//   return new File([arr], filename, { type: 'image/png' })
// }

// /* ════════════════════════════════════════════════════════════════
//    MAIN APP
//    ════════════════════════════════════════════════════════════════ */
// export default function App() {

//   const [ollamaOk,    setOllamaOk]    = useState(null)
//   const [imageFile,   setImageFile]   = useState(null)    // File object (for sending)
//   const [imageUrl,    setImageUrl]    = useState(null)    // displayable URL
//   const [clickPoint,  setClickPoint]  = useState(null)
//   const [displayPt,   setDisplayPt]   = useState(null)
//   const [phase,       setPhase]       = useState('upload')
//   const [analysis,    setAnalysis]    = useState(null)
//   const [generated,   setGenerated]   = useState(null)
//   const [error,       setError]       = useState(null)
//   const [topic,       setTopic]       = useState('')
//   const [drillChain,  setDrillChain]  = useState([])      // history of all drill-downs
//   const [inputMode,   setInputMode]   = useState('choose') // 'choose' | 'upload' | 'text'

//   const imgRef       = useRef(null)
//   const canvasRef    = useRef(null)
//   const fileInputRef = useRef(null)

//   /* ── health check ──────────────────────────────────────────── */
//   useEffect(() => {
//     fetch(`${API}/api/health`)
//       .then(r => r.json())
//       .then(d => setOllamaOk(d.ollama))
//       .catch(() => setOllamaOk(false))
//   }, [])

//   /* ── draw reticle on click ─────────────────────────────────── */
//   useEffect(() => {
//     if (!displayPt || !canvasRef.current || !imgRef.current) return
//     drawReticle(canvasRef.current, imgRef.current, displayPt.x, displayPt.y)
//   }, [displayPt])

//   /* ── handlers ──────────────────────────────────────────────── */
//   function handleFileChange(e) {
//     const file = e.target.files[0]
//     if (!file) return
//     setImageFile(file)
//     setImageUrl(URL.createObjectURL(file))
//     setClickPoint(null); setDisplayPt(null)
//     setAnalysis(null); setGenerated(null); setError(null)
//     setPhase('select')
//     setInputMode('upload')
//     if (canvasRef.current) {
//       canvasRef.current.getContext('2d')
//         .clearRect(0, 0, canvasRef.current.width, canvasRef.current.height)
//     }
//   }

//   function handleImageClick(e) {
//     if (phase === 'analyzing' || phase === 'generating' || phase === 'generating-text') return
//     const img    = imgRef.current
//     const rect   = img.getBoundingClientRect()
//     const displayX = e.clientX - rect.left
//     const displayY = e.clientY - rect.top
//     const scaleX   = img.naturalWidth  / rect.width
//     const scaleY   = img.naturalHeight / rect.height
//     setClickPoint({ x: Math.round(displayX * scaleX), y: Math.round(displayY * scaleY) })
//     setDisplayPt( { x: displayX, y: displayY })
//     setPhase('point-selected')
//     setAnalysis(null); setGenerated(null); setError(null)
//   }

//   /* ── generate initial image from text prompt ───────────────── */
//   async function handleGenerateFromText() {
//     if (!topic.trim()) return
//     setPhase('generating-text')
//     setError(null)

//     try {
//       const res = await fetch(`${API}/api/generate-from-text`, {
//         method:  'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body:    JSON.stringify({ topic: topic.trim() }),
//       })
//       if (!res.ok) throw new Error(`Server error: ${await res.text()}`)
//       const data = await res.json()

//       // Convert the generated b64 image into a File so it can be sent to /api/analyze
//       const file = b64ToFile(data.image_b64)
//       const url  = `data:image/png;base64,${data.image_b64}`

//       setImageFile(file)
//       setImageUrl(url)
//       setDrillChain([{ image_b64: data.image_b64, prompt: data.image_prompt, depth: 0 }])
//       setPhase('select')
//       setClickPoint(null); setDisplayPt(null)
//       setAnalysis(null); setGenerated(null)
//     } catch (e) {
//       setError(e.message)
//       setPhase('upload')
//     }
//   }

//   /* ── analyze region ────────────────────────────────────────── */
//   async function handleAnalyze() {
//     if (!imageFile || !clickPoint) return
//     setPhase('analyzing')
//     setError(null)

//     const { blob, scaleX, scaleY } = await compressImage(imageFile)
//     const scaledX = Math.round(clickPoint.x * scaleX)
//     const scaledY = Math.round(clickPoint.y * scaleY)

//     const fd = new FormData()
//     fd.append('image', blob, 'image.jpg')
//     fd.append('x', scaledX)
//     fd.append('y', scaledY)
//     fd.append('radius', 80)

//     try {
//       const res  = await fetch(`${API}/api/analyze`, { method: 'POST', body: fd })
//       if (!res.ok) throw new Error(`Server error: ${await res.text()}`)
//       const data = await res.json()
//       setAnalysis(data)
//       setPhase('analyzed')
//     } catch (e) {
//       setError(e.message)
//       setPhase('point-selected')
//     }
//   }

//   /* ── generate drill-down image ─────────────────────────────── */
//   async function handleGenerate() {
//     if (!analysis) return
//     setPhase('generating')
//     setError(null)

//     try {
//       const res = await fetch(`${API}/api/generate`, {
//         method:  'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({
//           prompt:         analysis.image_prompt,
//           local_crop_b64: analysis.local_crop_b64,
//           global_b64:     analysis.marked_image_b64,
//         }),
//       })
//       if (!res.ok) throw new Error(`Server error: ${await res.text()}`)
//       const data = await res.json()
//       setGenerated(data.image_b64)

//       // Add to drill chain history
//       setDrillChain(prev => [...prev, {
//         image_b64: data.image_b64,
//         analysis:  analysis.analysis,
//         prompt:    analysis.image_prompt,
//         depth:     prev.length,
//       }])

//       setPhase('done')
//     } catch (e) {
//       setError(e.message)
//       setPhase('analyzed')
//     }
//   }

//   /* ── use generated image as next parent (infinite recursion) ── */
//   function handleDrillDeeper() {
//     if (!generated) return
//     const file = b64ToFile(generated)
//     const url  = `data:image/png;base64,${generated}`
//     setImageFile(file)
//     setImageUrl(url)
//     setClickPoint(null); setDisplayPt(null)
//     setAnalysis(null); setGenerated(null); setError(null)
//     setPhase('select')
//     if (canvasRef.current) {
//       canvasRef.current.getContext('2d')
//         .clearRect(0, 0, canvasRef.current.width, canvasRef.current.height)
//     }
//   }

//   /* ── full reset ────────────────────────────────────────────── */
//   function handleReset() {
//     setImageFile(null); setImageUrl(null)
//     setClickPoint(null); setDisplayPt(null)
//     setAnalysis(null); setGenerated(null)
//     setError(null); setTopic('')
//     setDrillChain([])
//     setPhase('upload')
//     setInputMode('choose')
//   }

//   /* ── current depth label ───────────────────────────────────── */
//   const currentDepth = drillChain.length

//   const canClick = phase === 'select' || phase === 'point-selected'

//   /* ══════════════════════════════════════════════════════════════
//      RENDER
//      ══════════════════════════════════════════════════════════════ */
//   return (
//     <div className="app">

//       {/* ── HEADER ─────────────────────────────────────────────── */}
//       <header className="header">
//         <div className="header-inner">
//           <div className="logo">
//             <span className="logo-icon">◎</span>
//             <span className="logo-text">SEMANTIC<span className="logo-accent"> DRILL DOWN</span></span>
//           </div>
//           <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
//             {currentDepth > 0 && (
//               <div className="depth-indicator">
//                 DEPTH {currentDepth}
//               </div>
//             )}
//             <div className={`status-badge ${ollamaOk === true ? 'ok' : ollamaOk === false ? 'err' : 'checking'}`}>
//               <span className="status-dot" />
//               {ollamaOk === null  && 'Connecting…'}
//               {ollamaOk === true  && 'Ollama ready'}
//               {ollamaOk === false && 'Ollama offline'}
//             </div>
//           </div>
//         </div>
//         <StepTracker phase={phase} />
//       </header>

//       {/* ── MAIN ───────────────────────────────────────────────── */}
//       <main className="main">

//         {/* ── LEFT PANEL: INPUT ──────────────────────────────────── */}
//         <section className="panel left-panel">
//           <div className="panel-label">INPUT</div>

//           <input
//             ref={fileInputRef}
//             type="file"
//             accept="image/png,image/jpeg,image/webp"
//             onChange={handleFileChange}
//             style={{ display: 'none' }}
//           />

//           {/* ── INPUT MODE CHOOSER (shown when no image yet) ────── */}
//           {!imageUrl && phase === 'upload' && (
//             <>
//               {inputMode === 'choose' && (
//                 <div className="input-chooser">
//                   <div
//                     className="chooser-card"
//                     onClick={() => fileInputRef.current.click()}
//                   >
//                     <span className="chooser-icon">⊕</span>
//                     <span className="chooser-title">Upload Image</span>
//                     <span className="chooser-hint">PNG, JPG, WEBP</span>
//                   </div>

//                   <div className="chooser-divider">
//                     <span>OR</span>
//                   </div>

//                   <div
//                     className="chooser-card"
//                     onClick={() => setInputMode('text')}
//                   >
//                     <span className="chooser-icon">✎</span>
//                     <span className="chooser-title">Describe a Scene</span>
//                     <span className="chooser-hint">AI generates the starting image</span>
//                   </div>
//                 </div>
//               )}

//               {inputMode === 'text' && (
//                 <div className="text-input-area">
//                   <label className="text-input-label">
//                     Describe what you want to explore
//                   </label>
//                   <textarea
//                     className="topic-textarea"
//                     value={topic}
//                     onChange={e => setTopic(e.target.value)}
//                     placeholder="e.g. A cross-section of a human heart, A geological layer of the Grand Canyon, Inside a mechanical watch..."
//                     rows={4}
//                     autoFocus
//                   />
//                   <div className="action-row">
//                     <button
//                       className="btn-primary"
//                       onClick={handleGenerateFromText}
//                       disabled={!topic.trim()}
//                     >
//                       <span>✦</span> Generate Starting Image
//                     </button>
//                     <button className="btn-ghost" onClick={() => setInputMode('choose')}>
//                       ← Back
//                     </button>
//                   </div>
//                 </div>
//               )}
//             </>
//           )}

//           {/* ── GENERATING FROM TEXT spinner ──────────────────────── */}
//           {phase === 'generating-text' && (
//             <div className="text-generating">
//               <div className="spinner-large" />
//               <p className="gen-text-msg">Generating your starting image…</p>
//               <p className="gen-text-sub">This may take a minute</p>
//             </div>
//           )}

//           {/* ── IMAGE + INTERACTION ──────────────────────────────── */}
//           {imageUrl && phase !== 'generating-text' && (
//             <>
//               <button className="btn-ghost small" onClick={() => fileInputRef.current.click()}>
//                 ↺ Change Image
//               </button>

//               <div className="image-container">
//                 <div className="image-hint">
//                   {phase === 'select'         && `↓ Click anywhere to select a region ${currentDepth > 0 ? `(depth ${currentDepth})` : ''}`}
//                   {phase === 'point-selected' && `✓ Region selected at (${clickPoint?.x}, ${clickPoint?.y})`}
//                   {phase === 'analyzing'      && '⟳ Analyzing region…'}
//                   {phase === 'analyzed'       && '✓ Analysis complete — generate below'}
//                   {phase === 'generating'     && '⟳ Generating drill-down…'}
//                   {phase === 'done'           && '✓ Done! See result on the right'}
//                 </div>

//                 <div className="img-wrapper">
//                   <img
//                     ref={imgRef}
//                     src={imageUrl}
//                     alt="Current parent"
//                     className={`main-img ${canClick ? 'clickable' : ''}`}
//                     onClick={handleImageClick}
//                     draggable={false}
//                   />
//                   <canvas ref={canvasRef} className="reticle-canvas" />
//                 </div>

//                 {analysis?.local_crop_b64 && (
//                   <div className="crop-preview">
//                     <span className="crop-label">LOCAL CROP</span>
//                     <img
//                       src={`data:image/png;base64,${analysis.local_crop_b64}`}
//                       alt="Cropped region"
//                       className="crop-img"
//                     />
//                   </div>
//                 )}
//               </div>
//             </>
//           )}

//           {/* ── ACTION BUTTONS ────────────────────────────────────── */}
//           <div className="action-row">
//             {phase === 'point-selected' && (
//               <button className="btn-primary" onClick={handleAnalyze}>
//                 <span>⬡</span> Analyze Region
//               </button>
//             )}
//             {phase === 'analyzing' && (
//               <button className="btn-primary loading" disabled>
//                 <span className="spinner" /> Analyzing…
//               </button>
//             )}
//             {phase === 'analyzed' && (
//               <button className="btn-primary" onClick={handleGenerate}>
//                 <span>✦</span> Generate Drill-Down
//               </button>
//             )}
//             {phase === 'generating' && (
//               <button className="btn-primary loading" disabled>
//                 <span className="spinner" /> Generating…
//               </button>
//             )}
//             {(phase === 'done' || analysis || currentDepth > 0) && (
//               <button className="btn-ghost" onClick={handleReset}>
//                 ← Start Over
//               </button>
//             )}
//           </div>

//           {error && (
//             <div className="error-box">
//               <span className="error-icon">⚠</span>
//               <span>{error}</span>
//             </div>
//           )}
//         </section>

//         {/* ── RIGHT PANEL: OUTPUT ──────────────────────────────── */}
//         <section className="panel right-panel">
//           <div className="panel-label">OUTPUT</div>

//           {!analysis && !generated && drillChain.length === 0 && (
//             <div className="empty-state">
//               <div className="empty-icon">◎</div>
//               <p>Upload an image or describe a scene<br />to begin semantic exploration</p>
//             </div>
//           )}

//           {/* ── DRILL CHAIN HISTORY ──────────────────────────────── */}
//           {drillChain.length > 0 && !analysis && !generated && (
//             <div className="drill-chain">
//               <div className="chain-header">
//                 <span className="chain-title">DRILL CHAIN</span>
//                 <span className="chain-count">{drillChain.length} level{drillChain.length > 1 ? 's' : ''}</span>
//               </div>
//               {drillChain.map((item, i) => (
//                 <div className="drill-card" key={i}>
//                   <div className="drill-card-header">
//                     <span className="depth-badge">
//                       {i === 0 ? 'ORIGIN' : `DEPTH ${i}`}
//                     </span>
//                   </div>
//                   <img
//                     src={`data:image/png;base64,${item.image_b64}`}
//                     alt={`Depth ${i}`}
//                     className="drill-card-img"
//                   />
//                   {item.analysis && (
//                     <p className="drill-card-desc">{item.analysis}</p>
//                   )}
//                 </div>
//               ))}
//             </div>
//           )}

//           {/* ── CURRENT ANALYSIS ──────────────────────────────────── */}
//           {analysis && (
//             <div className="result-block">
//               <div className="result-section">
//                 <h3 className="result-title">
//                   <span className="result-dot" style={{ background: 'var(--teal)' }} />
//                   SEMANTIC ANALYSIS
//                 </h3>
//                 <p className="result-text">{analysis.analysis}</p>
//               </div>
//               <div className="result-section">
//                 <h3 className="result-title">
//                   <span className="result-dot" style={{ background: 'var(--amber)' }} />
//                   IMAGE PROMPT
//                 </h3>
//                 <p className="prompt-text">{analysis.image_prompt}</p>
//               </div>
//             </div>
//           )}

//           {/* ── GENERATED IMAGE + DRILL DEEPER ────────────────────── */}
//           {generated && (
//             <div className="generated-block">
//               <div className="result-section">
//                 <h3 className="result-title">
//                   <span className="result-dot" style={{ background: 'var(--red)' }} />
//                   DRILL-DOWN IMAGE — DEPTH {currentDepth}
//                 </h3>
//               </div>
//               <img
//                 src={`data:image/png;base64,${generated}`}
//                 alt="Generated drill-down"
//                 className="generated-img"
//               />
//               <div className="generated-actions">
//                 <button className="btn-drill-deeper" onClick={handleDrillDeeper}>
//                   <span>◎</span> Drill Deeper
//                   <span className="drill-arrow">→</span>
//                 </button>
//                 <a
//                   href={`data:image/png;base64,${generated}`}
//                   download={`drilldown-depth-${currentDepth}.png`}
//                   className="btn-download"
//                 >
//                   ⬇ Download
//                 </a>
//               </div>
//             </div>
//           )}
//         </section>

//       </main>
//     </div>
//   )
// }

// /* ── Step Tracker ────────────────────────────────────────────── */
// const PHASE_STEP = {
//   upload: 0, 'generating-text': 0,
//   select: 1, 'point-selected': 1,
//   analyzing: 2, analyzed: 2,
//   generating: 3, done: 3,
// }

// function StepTracker({ phase }) {
//   const current = PHASE_STEP[phase] ?? 0
//   const labels  = ['Start', 'Select Region', 'Analyze', 'Generate']
//   return (
//     <div className="step-tracker">
//       {labels.map((label, i) => (
//         <div
//           key={i}
//           className={`step ${i < current ? 'done' : i === current ? 'active' : 'pending'}`}
//         >
//           <div className="step-dot">
//             {i < current ? '✓' : <span>{i + 1}</span>}
//           </div>
//           <span className="step-label">{label}</span>
//           {i < labels.length - 1 && <div className="step-line" />}
//         </div>
//       ))}
//     </div>
//   )
// }



//----------
import { useState, useRef, useEffect } from 'react'
import './App.css'

const API = 'http://localhost:8000'

/* ── reticle drawing (unchanged) ─────────────────────────────── */
function drawReticle(canvas, img, dx, dy) {
  const rect = img.getBoundingClientRect()
  canvas.width  = rect.width
  canvas.height = rect.height
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  const R = 44
  ctx.strokeStyle = '#ff2d55'
  ctx.lineWidth   = 2
  ctx.setLineDash([7, 4])
  ctx.beginPath()
  ctx.arc(dx, dy, R, 0, Math.PI * 2)
  ctx.stroke()
  ctx.setLineDash([])
  ctx.lineWidth = 1.5
  const GAP = 10, ARM = 22
  ;[
    [dx - R - ARM, dy, dx - R - GAP, dy],
    [dx + R + GAP, dy, dx + R + ARM, dy],
    [dx, dy - R - ARM, dx, dy - R - GAP],
    [dx, dy + R + GAP, dx, dy + R + ARM],
  ].forEach(([x1, y1, x2, y2]) => {
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke()
  })
  const corners = [
    [0.15, Math.PI / 2 - 0.15],
    [Math.PI / 2 + 0.15, Math.PI - 0.15],
    [Math.PI + 0.15, (3 * Math.PI) / 2 - 0.15],
    [(3 * Math.PI) / 2 + 0.15, Math.PI * 2 - 0.15],
  ]
  ctx.lineWidth = 2.5
  corners.forEach(([a1, a2]) => {
    ctx.beginPath(); ctx.arc(dx, dy, R, a1, a2); ctx.stroke()
  })
  ctx.fillStyle = '#ff2d55'
  ctx.beginPath(); ctx.arc(dx, dy, 4, 0, Math.PI * 2); ctx.fill()
  ctx.font      = '11px JetBrains Mono, monospace'
  ctx.fillStyle = '#ff2d5599'
  ctx.fillText(`${Math.round(dx)}, ${Math.round(dy)}`, dx + R + 8, dy - 4)
}

/* ── image compression ───────────────────────────────────────── */
async function compressImage(file, maxSizePx = 1200) {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      const origW = img.naturalWidth, origH = img.naturalHeight
      let w = origW, h = origH
      if (w > maxSizePx || h > maxSizePx) {
        if (w > h) { h = Math.round(h * maxSizePx / w); w = maxSizePx }
        else       { w = Math.round(w * maxSizePx / h); h = maxSizePx }
      }
      canvas.width = w; canvas.height = h
      canvas.getContext('2d').drawImage(img, 0, 0, w, h)
      canvas.toBlob(
        (blob) => resolve({ blob, scaleX: w / origW, scaleY: h / origH }),
        'image/jpeg', 0.85,
      )
    }
    img.src = URL.createObjectURL(file)
  })
}

/* ── b64 string → File object (for generated images used as parents) */
function b64ToFile(b64, filename = 'image.png') {
  const bin = atob(b64)
  const arr = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i)
  return new File([arr], filename, { type: 'image/png' })
}

/* ════════════════════════════════════════════════════════════════
   MAIN APP
   ════════════════════════════════════════════════════════════════ */
export default function App() {

  const [ollamaOk,    setOllamaOk]    = useState(null)
  const [imageFile,   setImageFile]   = useState(null)    // File object (for sending)
  const [imageUrl,    setImageUrl]    = useState(null)    // displayable URL
  const [clickPoint,  setClickPoint]  = useState(null)
  const [displayPt,   setDisplayPt]   = useState(null)
  const [phase,       setPhase]       = useState('upload')
  const [analysis,    setAnalysis]    = useState(null)
  const [generated,   setGenerated]   = useState(null)
  const [error,       setError]       = useState(null)
  const [topic,       setTopic]       = useState('')
  const [drillChain,  setDrillChain]  = useState([])      // history of all drill-downs
  const [inputMode,   setInputMode]   = useState('choose') // 'choose' | 'upload' | 'text'

  const imgRef       = useRef(null)
  const canvasRef    = useRef(null)
  const fileInputRef = useRef(null)

  /* ── health check ──────────────────────────────────────────── */
  useEffect(() => {
    fetch(`${API}/api/health`)
      .then(r => r.json())
      .then(d => setOllamaOk(d.ollama))
      .catch(() => setOllamaOk(false))
  }, [])

  /* ── draw reticle on click ─────────────────────────────────── */
  useEffect(() => {
    if (!displayPt || !canvasRef.current || !imgRef.current) return
    drawReticle(canvasRef.current, imgRef.current, displayPt.x, displayPt.y)
  }, [displayPt])

  /* ── handlers ──────────────────────────────────────────────── */
  function handleFileChange(e) {
    const file = e.target.files[0]
    if (!file) return
    setImageFile(file)
    setImageUrl(URL.createObjectURL(file))
    setClickPoint(null); setDisplayPt(null)
    setAnalysis(null); setGenerated(null); setError(null)
    setPhase('select')
    setInputMode('upload')
    if (canvasRef.current) {
      canvasRef.current.getContext('2d')
        .clearRect(0, 0, canvasRef.current.width, canvasRef.current.height)
    }
  }

  function handleImageClick(e) {
    if (phase === 'analyzing' || phase === 'generating' || phase === 'generating-text') return
    const img    = imgRef.current
    const rect   = img.getBoundingClientRect()
    const displayX = e.clientX - rect.left
    const displayY = e.clientY - rect.top
    const scaleX   = img.naturalWidth  / rect.width
    const scaleY   = img.naturalHeight / rect.height
    setClickPoint({ x: Math.round(displayX * scaleX), y: Math.round(displayY * scaleY) })
    setDisplayPt( { x: displayX, y: displayY })
    setPhase('point-selected')
    setAnalysis(null); setGenerated(null); setError(null)
  }

  /* ── generate initial image from text prompt ───────────────── */
  async function handleGenerateFromText() {
    if (!topic.trim()) return
    setPhase('generating-text')
    setError(null)

    try {
      const res = await fetch(`${API}/api/generate-from-text`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ topic: topic.trim() }),
      })
      if (!res.ok) throw new Error(`Server error: ${await res.text()}`)
      const data = await res.json()

      // Convert the generated b64 image into a File so it can be sent to /api/analyze
      const file = b64ToFile(data.image_b64)
      const url  = `data:image/png;base64,${data.image_b64}`

      setImageFile(file)
      setImageUrl(url)
      setDrillChain([{ image_b64: data.image_b64, prompt: data.image_prompt, depth: 0 }])
      setPhase('select')
      setClickPoint(null); setDisplayPt(null)
      setAnalysis(null); setGenerated(null)
    } catch (e) {
      setError(e.message)
      setPhase('upload')
    }
  }

  /* ── analyze region ────────────────────────────────────────── */
  async function handleAnalyze() {
    if (!imageFile || !clickPoint) return
    setPhase('analyzing')
    setError(null)

    const { blob, scaleX, scaleY } = await compressImage(imageFile)
    const scaledX = Math.round(clickPoint.x * scaleX)
    const scaledY = Math.round(clickPoint.y * scaleY)

    const fd = new FormData()
    fd.append('image', blob, 'image.jpg')
    fd.append('x', scaledX)
    fd.append('y', scaledY)
    fd.append('radius', 80)

    try {
      const res  = await fetch(`${API}/api/analyze`, { method: 'POST', body: fd })
      if (!res.ok) throw new Error(`Server error: ${await res.text()}`)
      const data = await res.json()
      setAnalysis(data)
      setPhase('analyzed')
    } catch (e) {
      setError(e.message)
      setPhase('point-selected')
    }
  }

  /* ── generate drill-down image ─────────────────────────────── */
  async function handleGenerate() {
    if (!analysis) return
    setPhase('generating')
    setError(null)

    try {
      const res = await fetch(`${API}/api/generate`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt:         analysis.image_prompt,
          local_crop_b64: analysis.local_crop_b64,
          global_b64:     analysis.marked_image_b64,
        }),
      })
      if (!res.ok) throw new Error(`Server error: ${await res.text()}`)
      const data = await res.json()
      setGenerated(data.image_b64)

      // Add to drill chain history
      setDrillChain(prev => [...prev, {
        image_b64: data.image_b64,
        analysis:  analysis.analysis,
        prompt:    analysis.image_prompt,
        depth:     prev.length,
      }])

      setPhase('done')
    } catch (e) {
      setError(e.message)
      setPhase('analyzed')
    }
  }

  /* ── use generated image as next parent (infinite recursion) ── */
  function handleDrillDeeper() {
    if (!generated) return
    const file = b64ToFile(generated)
    const url  = `data:image/png;base64,${generated}`
    setImageFile(file)
    setImageUrl(url)
    setClickPoint(null); setDisplayPt(null)
    setAnalysis(null); setGenerated(null); setError(null)
    setPhase('select')
    if (canvasRef.current) {
      canvasRef.current.getContext('2d')
        .clearRect(0, 0, canvasRef.current.width, canvasRef.current.height)
    }
  }

  /* ── full reset ────────────────────────────────────────────── */
  function handleReset() {
    setImageFile(null); setImageUrl(null)
    setClickPoint(null); setDisplayPt(null)
    setAnalysis(null); setGenerated(null)
    setError(null); setTopic('')
    setDrillChain([])
    setPhase('upload')
    setInputMode('choose')
  }

  /* ── current depth label ───────────────────────────────────── */
  const currentDepth = drillChain.length

  const canClick = phase === 'select' || phase === 'point-selected'

  /* ══════════════════════════════════════════════════════════════
     RENDER
     ══════════════════════════════════════════════════════════════ */
  return (
    <div className="app">

      {/* ── HEADER ─────────────────────────────────────────────── */}
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">◎</span>
            <span className="logo-text">SEMANTIC<span className="logo-accent"> DRILL DOWN</span></span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {currentDepth > 0 && (
              <div className="depth-indicator">
                DEPTH {currentDepth}
              </div>
            )}
            <div className={`status-badge ${ollamaOk === true ? 'ok' : ollamaOk === false ? 'err' : 'checking'}`}>
              <span className="status-dot" />
              {ollamaOk === null  && 'Connecting…'}
              {ollamaOk === true  && 'Ollama ready'}
              {ollamaOk === false && 'Ollama offline'}
            </div>
          </div>
        </div>
        <StepTracker phase={phase} />
      </header>

      {/* ── MAIN ───────────────────────────────────────────────── */}
      <main className="main">

        {/* ── LEFT PANEL: INPUT ──────────────────────────────────── */}
        <section className="panel left-panel">
          <div className="panel-label">INPUT</div>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />

          {/* ── INPUT MODE CHOOSER (shown when no image yet) ────── */}
          {!imageUrl && phase === 'upload' && (
            <>
              {inputMode === 'choose' && (
                <div className="input-chooser">
                  <div
                    className="chooser-card"
                    onClick={() => fileInputRef.current.click()}
                  >
                    <span className="chooser-icon">⊕</span>
                    <span className="chooser-title">Upload Image</span>
                    <span className="chooser-hint">PNG, JPG, WEBP</span>
                  </div>

                  <div className="chooser-divider">
                    <span>OR</span>
                  </div>

                  <div
                    className="chooser-card"
                    onClick={() => setInputMode('text')}
                  >
                    <span className="chooser-icon">✎</span>
                    <span className="chooser-title">Describe a Scene</span>
                    <span className="chooser-hint">AI generates the starting image</span>
                  </div>
                </div>
              )}

              {inputMode === 'text' && (
                <div className="text-input-area">
                  <label className="text-input-label">
                    Describe what you want to explore
                  </label>
                  <textarea
                    className="topic-textarea"
                    value={topic}
                    onChange={e => setTopic(e.target.value)}
                    placeholder="e.g. A cross-section of a human heart, A geological layer of the Grand Canyon, Inside a mechanical watch..."
                    rows={4}
                    autoFocus
                  />
                  <div className="action-row">
                    <button
                      className="btn-primary"
                      onClick={handleGenerateFromText}
                      disabled={!topic.trim()}
                    >
                      <span>✦</span> Generate Starting Image
                    </button>
                    <button className="btn-ghost" onClick={() => setInputMode('choose')}>
                      ← Back
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {/* ── GENERATING FROM TEXT spinner ──────────────────────── */}
          {phase === 'generating-text' && (
            <div className="text-generating">
              <div className="spinner-large" />
              <p className="gen-text-msg">Generating your starting image…</p>
              <p className="gen-text-sub">This may take a minute</p>
            </div>
          )}

          {/* ── IMAGE + INTERACTION ──────────────────────────────── */}
          {imageUrl && phase !== 'generating-text' && (
            <>
              <button className="btn-ghost small" onClick={() => fileInputRef.current.click()}>
                ↺ Change Image
              </button>

              <div className="image-container">
                <div className="image-hint">
                  {phase === 'select'         && `↓ Click anywhere to select a region ${currentDepth > 0 ? `(depth ${currentDepth})` : ''}`}
                  {phase === 'point-selected' && `✓ Region selected at (${clickPoint?.x}, ${clickPoint?.y})`}
                  {phase === 'analyzing'      && '⟳ Analyzing region…'}
                  {phase === 'analyzed'       && '✓ Analysis complete — generate below'}
                  {phase === 'generating'     && '⟳ Generating drill-down…'}
                  {phase === 'done'           && '✓ Done! See result on the right'}
                </div>

                <div className="img-wrapper">
                  <img
                    ref={imgRef}
                    src={imageUrl}
                    alt="Current parent"
                    className={`main-img ${canClick ? 'clickable' : ''}`}
                    onClick={handleImageClick}
                    draggable={false}
                  />
                  <canvas ref={canvasRef} className="reticle-canvas" />
                </div>

                {analysis?.local_crop_b64 && (
                  <div className="crop-preview">
                    <span className="crop-label">LOCAL CROP</span>
                    <img
                      src={`data:image/png;base64,${analysis.local_crop_b64}`}
                      alt="Cropped region"
                      className="crop-img"
                    />
                  </div>
                )}
              </div>
            </>
          )}

          {/* ── ACTION BUTTONS ────────────────────────────────────── */}
          <div className="action-row">
            {phase === 'point-selected' && (
              <button className="btn-primary" onClick={handleAnalyze}>
                <span>⬡</span> Analyze Region
              </button>
            )}
            {phase === 'analyzing' && (
              <button className="btn-primary loading" disabled>
                <span className="spinner" /> Analyzing…
              </button>
            )}
            {phase === 'analyzed' && (
              <button className="btn-primary" onClick={handleGenerate}>
                <span>✦</span> Generate Drill-Down
              </button>
            )}
            {phase === 'generating' && (
              <button className="btn-primary loading" disabled>
                <span className="spinner" /> Generating…
              </button>
            )}
            {(phase === 'done' || analysis || currentDepth > 0) && (
              <button className="btn-ghost" onClick={handleReset}>
                ← Start Over
              </button>
            )}
          </div>

          {error && (
            <div className="error-box">
              <span className="error-icon">⚠</span>
              <span>{error}</span>
            </div>
          )}
        </section>

        {/* ── RIGHT PANEL: OUTPUT ──────────────────────────────── */}
        <section className="panel right-panel">
          <div className="panel-label">OUTPUT</div>

          {!analysis && !generated && drillChain.length === 0 && (
            <div className="empty-state">
              <div className="empty-icon">◎</div>
              <p>Upload an image or describe a scene<br />to begin semantic exploration</p>
            </div>
          )}

          {/* ── DRILL CHAIN HISTORY ──────────────────────────────── */}
          {drillChain.length > 0 && !analysis && !generated && (
            <div className="drill-chain">
              <div className="chain-header">
                <span className="chain-title">DRILL CHAIN</span>
                <span className="chain-count">{drillChain.length} level{drillChain.length > 1 ? 's' : ''}</span>
              </div>
              {drillChain.map((item, i) => (
                <div className="drill-card" key={i}>
                  <div className="drill-card-header">
                    <span className="depth-badge">
                      {i === 0 ? 'ORIGIN' : `DEPTH ${i}`}
                    </span>
                  </div>
                  <img
                    src={`data:image/png;base64,${item.image_b64}`}
                    alt={`Depth ${i}`}
                    className="drill-card-img"
                  />
                  {item.analysis && (
                    <p className="drill-card-desc">{item.analysis}</p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* ── CURRENT ANALYSIS ──────────────────────────────────── */}
          {analysis && (
            <div className="result-block">
              <div className="result-section">
                <h3 className="result-title">
                  <span className="result-dot" style={{ background: 'var(--teal)' }} />
                  SEMANTIC ANALYSIS
                </h3>
                <p className="result-text">{analysis.analysis}</p>
              </div>
              <div className="result-section">
                <h3 className="result-title">
                  <span className="result-dot" style={{ background: 'var(--amber)' }} />
                  IMAGE PROMPT
                </h3>
                <p className="prompt-text">{analysis.image_prompt}</p>
              </div>
            </div>
          )}

          {/* ── GENERATED IMAGE + DRILL DEEPER ────────────────────── */}
          {generated && (
            <div className="generated-block">
              <div className="result-section">
                <h3 className="result-title">
                  <span className="result-dot" style={{ background: 'var(--red)' }} />
                  DRILL-DOWN IMAGE — DEPTH {currentDepth}
                </h3>
              </div>
              <img
                src={`data:image/png;base64,${generated}`}
                alt="Generated drill-down"
                className="generated-img"
              />
              <div className="generated-actions">
                <button className="btn-drill-deeper" onClick={handleDrillDeeper}>
                  <span>◎</span> Drill Deeper
                  <span className="drill-arrow">→</span>
                </button>
                <a
                  href={`data:image/png;base64,${generated}`}
                  download={`drilldown-depth-${currentDepth}.png`}
                  className="btn-download"
                >
                  ⬇ Download
                </a>
              </div>
            </div>
          )}
        </section>

      </main>
    </div>
  )
}

/* ── Step Tracker ────────────────────────────────────────────── */
const PHASE_STEP = {
  upload: 0, 'generating-text': 0,
  select: 1, 'point-selected': 1,
  analyzing: 2, analyzed: 2,
  generating: 3, done: 3,
}

function StepTracker({ phase }) {
  const current = PHASE_STEP[phase] ?? 0
  const labels  = ['Start', 'Select Region', 'Analyze', 'Generate']
  return (
    <div className="step-tracker">
      {labels.map((label, i) => (
        <div
          key={i}
          className={`step ${i < current ? 'done' : i === current ? 'active' : 'pending'}`}
        >
          <div className="step-dot">
            {i < current ? '✓' : <span>{i + 1}</span>}
          </div>
          <span className="step-label">{label}</span>
          {i < labels.length - 1 && <div className="step-line" />}
        </div>
      ))}
    </div>
  )
}
