# DrillDown Unified

**This folder is the application root.** Everything needed to run both product modes lives here. Copy `.env.example` to `.env` before starting.

Two modes in one app:

| Mode | Route | What it does |
|------|-------|--------------|
| **Explainer** | `#/explainer` | Upload or topic → auto-labels → click drill → deeper illustrated layer (Ollama vision + Flux) |
| **Ecommerce** | `#/ecommerce` | Upload outfit → click item → product recommendations (Gemini + FashionCLIP + Qdrant) |

The Explainer has two sub-modes selectable in the sidebar:

| Sub-mode | What it does |
|----------|--------------|
| **Generic** | Drill into any image using VLM analysis only — no documents needed |
| **Knowledge Base** | Upload a PDF manual → system ingests it → every drill is grounded in your documentation with a source citation |

---

## Quick start

```bash
cd drilldown-unified

# 1. Environment
cp .env.example .env
# Edit .env: GOOGLE_API_KEY for ecommerce; MODEL_PROVIDER=ollama for explainer

# 2. Dependencies
pip install -r requirements.txt
npm install

# 3. Ollama models (explainer)
ollama pull qwen3.5:9b           # vision analysis
ollama pull qwen2.5vl:7b         # KB figure description (Knowledge Base mode)
ollama pull x/flux2-klein:4b-bf16  # image generation

# 4. Ecommerce data (optional — only for fashion mode)
# Place dataset under data/fashion-dataset/ (see data/fashion-dataset/README.md)
npm run ingest -- --limit 1000

# 5. Run
npm run backend    # API :8000
npm run frontend   # UI  :5173
```

- Explainer: http://127.0.0.1:5173/#/explainer  
- Ecommerce: http://127.0.0.1:5173/#/ecommerce  
- API docs: http://127.0.0.1:8000/docs  

---

## Project Structure

```text
drilldown-unified/                 ← you are here (app root)
├── backend/
│   ├── app/
│   │   ├── main.py                FastAPI entry, error handlers
│   │   ├── controllers/           Request handlers (ecommerce.py, vision.py, generation.py)
│   │   ├── routes/                HTTP route wiring
│   │   └── dependencies.py        Dependency injection setup
│   ├── core/
│   │   ├── factory.py             Injectable ServiceFactory
│   │   └── protocols.py           Service contracts (Protocol definitions)
│   ├── services/
│   │   ├── ecommerce/             Catalog, drill coordination
│   │   ├── explainer/             Vision analysis, page orchestration, generation
│   │   └── knowledge_base/        PDF ingestion (Docling), embedding, Qdrant storage, retrieval
│   ├── repositories/              Data access (page, history)
│   ├── models/                    Pydantic API schemas
│   └── shared/                    Config, errors, utilities, coordinates
├── frontend/src/
│   ├── components/                Reusable UI (AppHeader, …)
│   ├── hooks/                     useAppHealth, useHashMode
│   ├── pages/                     Route views (EcommercePage, ExplainerPage)
│   ├── services/                  API clients (kebab-case)
│   ├── assets/                    Static assets
│   └── utils/                     Helpers (coords, errors)
├── packages/types/                @shared/types TypeScript contracts
├── tests/
│   ├── backend/                   pytest tests
│   └── frontend/                  vitest tests
├── docs/                          Architecture, guides
├── data/                          Runtime storage (qdrant, uploads, static)
├── scripts/                       ingest_data.py, smoke.sh
├── .env.example
├── requirements.txt
├── package.json
└── README.md
```

See [docs/architecture.md](docs/architecture.md) for layer separation and dependency injection patterns.

### API mounts

| Prefix | Purpose |
|--------|---------|
| `/api/ecommerce/*` | Upload, identify, drill, history |
| `/api/explainer/vision/*` | Upload, analyze, page, stream-page |
| `/api/explainer/generate/*` | generate, generate-from-text |
| `/api/kb/upload` | Upload + ingest a PDF manual into the Knowledge Base |
| `/api/kb/list` | List all uploaded manuals |
| `/api/kb/{id}` DELETE | Remove a manual and its Qdrant collection |
| `/uploads`, `/dataset`, `/static` | Static file serving |

Explainer drill uses **vision (identify) → adapter → generation**. It does not use Google Imagen or Sid `/api/analyze`.

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
| `IMAGE_MODEL` | Explainer | Default `x/flux2-klein:4b-bf16` |
| `MODEL_PROVIDER` | Explainer | `ollama` or `mock` (UI dev without Ollama) |
| `SAM2_PATH`, `HF_TOKEN` | Explainer | Optional SAM2 segmentation |
| `VITE_API_BASE` | Frontend | Default `http://127.0.0.1:8000` |

| `KB_DIR` | Knowledge Base | Default `./data/kb` — stores KB registry JSON |
| `KB_QDRANT_PATH` | Knowledge Base | Default `./data/kb/qdrant` — vector DB for KB chunks |
| `VISION_MODEL` | Knowledge Base | Default `qwen2.5vl:7b` — used to describe diagrams during PDF ingestion |

All `./data/...` paths resolve relative to **this folder**, not the parent repo.

---

## npm scripts

| Script | Command |
|--------|---------|
| `npm run backend` | Start FastAPI on :8000 |
| `npm run frontend` | Start Vite on :5173 |
| `npm run build` | Production frontend build |
| `npm run health` | `GET /api/health` |
| `npm run smoke` | End-to-end API smoke (backend must be running) |
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
npm run smoke     # terminal 2 (needs Ollama for full pass)
```

---

## Knowledge Base (RAG) mode

The Explainer sidebar has a **Generic / Knowledge Base** toggle.

### How it works

1. Switch to **Knowledge Base** mode in the sidebar
2. Click **Upload PDF manual** — upload any equipment manual, SOP, or troubleshooting guide
3. The system ingests the PDF using **Docling** (IBM's layout-aware parser):
   - Text and tables are extracted directly
   - Diagrams, flowcharts, and figures are sent to the local VLM (`qwen2.5vl:7b`) which describes them in words
   - Everything is stored as searchable chunks in a local Qdrant vector database
4. Select the uploaded manual from the list to make it active
5. Click **Generic** at any time to go back to no-KB mode

When a manual is active, every drill automatically searches it and shows a **Source citation** (document name + page number + match %) in the metadata panel.

### First-time PDF ingestion

On the very first ingestion, Docling downloads its layout and OCR models (~500MB total). This is a one-time download — all subsequent ingestions start immediately.

### Supported document types

| Document | Works well? |
|---|---|
| Equipment / O&M manuals | Excellent — text, diagrams, parts lists all ingested |
| SOPs and procedures | Excellent — numbered steps and tables extracted cleanly |
| Troubleshooting guides | Excellent — decision trees converted to numbered steps by VLM |
| P&IDs (piping & instrument diagrams) | Good — VLM describes flow paths and component connections |
| Scanned PDFs (no text layer) | Partial — OCR fallback runs, accuracy depends on scan quality |

### Test ingestion locally

```bash
python test_ingestion.py path/to/your_manual.pdf
```

Prints how many elements Docling found, shows a VLM description of the first diagram, runs 4 test queries, and confirms end-to-end retrieval is working.

---

## Optional: SAM2 grounding

1. Clone SAM2 and set `SAM2_PATH` in `.env`
2. Set `HF_TOKEN` for model weights
3. Restart backend — health will report `sam2_available: true`

Default grounding is SAM2 when available, otherwise red-ring marker.
