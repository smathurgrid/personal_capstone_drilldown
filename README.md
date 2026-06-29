# DrillDown Unified

**This folder is the application root.** Copy `.env.example` to `.env` before starting.

A single-page app for interactive visual drill-down: upload an image or enter a topic, explore labeled hotspots, and drill deeper into illustrated layers. Two exploration modes share one UI; optional PDF knowledge bases ground explainer analysis in your documentation.

| UI mode | What it does |
|---------|--------------|
| **Explainer** | Topic or image → auto-labels → click to drill → deeper illustrated layer (Ollama vision + Flux) |
| **Ecommerce Match** | Outfit image → click item → similar product recommendations (Gemini + FashionCLIP + Qdrant) |

Additional capabilities:

| Feature | Description |
|---------|-------------|
| **Drill perspective** | *Inside Zoom (Macro)* — cross-section into a region; *POV Perspective (Outward)* — first-person view from a point |
| **Knowledge Base** | Upload a PDF manual; explainer drills retrieve hybrid dense/sparse chunks from that document |
| **Agent auto-drill** | `POST /api/agent/auto-drill` — autonomous multi-level drill loop (SSE) |
| **Layer 3 tools** | `POST /api/analyze`, `/api/generate`, etc. — low-level vision/generation contracts |

---

## Quick start

```bash
# 1. Environment
cp .env.example .env
# Edit .env: GOOGLE_API_KEY for ecommerce; MODEL_PROVIDER=ollama for explainer

# 2. Dependencies
pip install -r requirements.txt
npm install

# 3. Ollama models (explainer)
ollama pull qwen3.5:9b
ollama pull qwen2.5vl:7b
ollama pull x/flux2-klein:4b

# 4. Ecommerce data (optional — only for Ecommerce Match mode)
# Place dataset under data/fashion-dataset/ (see data/fashion-dataset/README.md)
npm run ingest -- --limit 1000

# 5. Run
npm run backend    # API :8000
npm run frontend   # UI  :5173
```

- App: http://127.0.0.1:5173  
- API docs: http://127.0.0.1:8000/docs  

Use **Explainer Mode** or **Ecommerce Match** on the home screen. For KB-grounded drills, switch Context to **Knowledge Base** and upload a PDF before exploring.

> **Ecommerce note:** Catalog drill (`/api/ecommerce/*`) is fully implemented on the backend (requires dataset ingest + `GOOGLE_API_KEY`). The unified `App.tsx` entry is explainer-first; legacy ecommerce UI lives under `frontend/src/pages/ecommerce/`.

Set `MODEL_PROVIDER=mock` to develop the UI without Ollama (generation returns placeholders).

---

## Project structure

```text
./                                 ← app root (package name: drilldown-unified)
├── backend/
│   ├── app/
│   │   ├── main.py                FastAPI entry, CORS, static mounts
│   │   ├── controllers/           Request handlers (ecommerce, vision, generation, kb, tools)
│   │   ├── routes/                HTTP route wiring
│   │   └── dependencies.py        Dependency injection setup
│   ├── agent/                     Layer 2 auto-drill orchestrator (SSE)
│   ├── core/
│   │   ├── factory.py             Injectable ServiceFactory
│   │   └── protocols.py           Service contracts (Protocol definitions)
│   ├── services/
│   │   ├── ecommerce/             Catalog, drill coordination
│   │   ├── explainer/             Vision, page orchestration, generation, drill context
│   │   └── knowledge_base/        PDF ingest, hybrid retrieval, figure enrichment
│   ├── repositories/              Data access (page, history)
│   ├── models/                    Pydantic API schemas
│   └── shared/                    Config, errors, drill modes, generation bridge
├── frontend/src/
│   ├── App.tsx                    Main unified UI (explore, canvas, history)
│   ├── components/ui/             DrillCanvas, ProductPanel, Header, …
│   ├── hooks/                     useAppHealth, useExplainerSession, …
│   ├── pages/                     Legacy route views (not wired in main.tsx)
│   ├── services/                  API clients (explainer-api, drill-adapter, ecommerce-api)
│   └── utils/                     Helpers (coords, errors)
├── packages/types/                @shared/types TypeScript contracts
├── tests/
│   ├── backend/                   pytest
│   └── frontend/                  vitest
├── docs/                          Architecture, guides
├── data/                          Runtime storage (qdrant, uploads, kb, static)
├── scripts/                       ingest_fashion_dataset.py, smoke_test.sh
├── .env.example
├── requirements.txt
├── package.json
└── README.md
```

See [docs/architecture.md](docs/architecture.md) for layer separation and dependency injection patterns.

### API mounts

| Prefix | Purpose |
|--------|---------|
| `/api/health` | Global health + per-module status |
| `/api/ecommerce/*` | Upload, identify, drill, history |
| `/api/explainer/vision/*` | Upload, analyze, page, stream-page, confirm-drill |
| `/api/explainer/generate/*` | generate, generate-from-text |
| `/api/kb/*` | Knowledge base upload, status, list, delete |
| `/api/agent/*` | auto-drill (SSE), health |
| `/api/analyze`, `/api/generate`, … | Layer 3 tool contracts |
| `/uploads`, `/dataset`, `/static` | Static file serving |

Explainer drill flow: **vision (identify) → adapter → generation**. KB mode injects retrieved manual chunks into drill context before analysis.

---

## Environment

Copy `.env.example` → `.env`. Key variables:

| Variable | Mode | Purpose |
|----------|------|---------|
| `GOOGLE_API_KEY` | Ecommerce | Gemini item identification |
| `QDRANT_PATH` | Ecommerce | Default `./data/qdrant_storage` |
| `DATASET_IMAGES_DIR` | Ecommerce | Default `./data/fashion-dataset/images` |
| `OLLAMA_BASE` | Explainer | Default `http://localhost:11434` |
| `EXPLAINER_VISION_MODEL` | Explainer | Default `qwen3.5:9b` (`ROHITH_VISION_MODEL` legacy alias) |
| `VISION_MODEL` | Explainer | Default `qwen2.5vl:7b` (generation/VLM paths) |
| `IMAGE_MODEL` | Explainer | Default `x/flux2-klein:4b` (`ollama pull x/flux2-klein:4b`) |
| `MODEL_PROVIDER` | Explainer | `ollama` or `mock` |
| `LLM_PROVIDER` | Agent / chat | `ollama` (direct) or `litellm` (LiteLLM proxy) |
| `LITELLM_PROXY_BASE`, `LITELLM_API_KEY` | Agent | LiteLLM proxy when `LLM_PROVIDER=litellm` |
| `AGENT_ORCHESTRATOR_MODEL` | Agent | Default `llama3.1` |
| `SAM2_PATH`, `HF_TOKEN` | Explainer | Optional SAM2 segmentation |
| `KB_DIR`, `KB_QDRANT_PATH` | Knowledge Base | Default `./data/kb`, `./data/kb/qdrant` |
| `KB_EMBEDDING_MODEL` | Knowledge Base | Default `BAAI/bge-small-en-v1.5` |
| `VITE_API_BASE` | Frontend | Default `http://127.0.0.1:8000` |
| `VITE_DEFAULT_MODE` | Frontend | Default `explainer` |

All `./data/...` paths resolve relative to **this folder**, not a parent repo.

First KB upload triggers a Docling layout-model download (~500 MB). Ingestion runs in the background; poll `/api/kb/status/{kb_id}` or use the UI wait helper.

---

## npm scripts

| Script | Command |
|--------|---------|
| `npm run backend` | Start FastAPI on :8000 |
| `npm run frontend` / `npm run dev` | Start Vite on :5173 |
| `npm run build` | Production frontend build |
| `npm run preview` | Preview production build |
| `npm run health` | `GET /api/health` |
| `npm run smoke` | End-to-end API smoke (`scripts/smoke_test.sh`; backend must be running) |
| `npm run ingest` | Ingest fashion dataset into Qdrant |
| `npm run test` | Run backend (pytest) + frontend (vitest) tests |
| `npm run test:backend` | pytest only |
| `npm run test:frontend` | vitest only |

---

## Verify

```bash
npm run test
npm run build
npm run backend   # terminal 1
npm run health    # terminal 2
npm run smoke     # terminal 2 (mock-friendly; full pass needs Ollama for generation)
```

---

## Optional: SAM2 grounding

1. Clone SAM2 and set `SAM2_PATH` in `.env`
2. Set `HF_TOKEN` for model weights
3. Restart backend — `/api/explainer/vision/health` reports `sam2_available: true`

Default grounding is SAM2 when available, otherwise red-ring marker.

---

## Optional: pi-agent auto-drill

For `mode: "pi-agent"` on `/api/agent/auto-drill`, install the pi-agent wheel (see comment in `requirements.txt`):

```bash
pip install vendor/pi_agent-0.1.0-py3-none-any.whl
```

Deterministic auto-drill works without the SDK.
