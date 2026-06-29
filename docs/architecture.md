# Architecture

## Overview

DrillDown Unified is a two-mode full-stack application built with **FastAPI** (backend), **React + Vite** (frontend), and **TypeScript** type contracts. Both modes share infrastructure—dependency injection, centralized error handling, repository patterns, and protocols.

---

## Backend Layer Architecture

### Core Principles

- **Dependency Injection**: `ServiceFactory` creates and caches services lazily
- **Protocol-Driven Design**: Service contracts defined via Python `Protocol` classes
- **Repository Pattern**: Data access abstraction for Qdrant, memory, and file storage
- **Error Handling**: Centralized `AppError` with consistent JSON error responses
- **Modular Domains**: `ecommerce` and `explainer` services independently organized

### Layers

#### 1. **Controllers** (`backend/app/controllers/`)

Thin request handlers that delegate to services. No business logic.

Example: `ecommerce.py`
- `POST /api/ecommerce/upload` → controller calls `EcommerceCatalogService.identify()`
- `POST /api/ecommerce/drill` → controller calls `DrillCoordinator.drill()`

Example: `vision.py`
- `POST /api/explainer/vision/analyze` → controller calls `ExplainerContextAnalyzer.analyze()`

#### 2. **Routes** (`backend/app/routes/`)

FastAPI router configuration. Wires controllers to HTTP endpoints using `Depends()` for dependency injection.

Example: `ecommerce.py`
```python
router = APIRouter(prefix="/api/ecommerce")
@router.post("/upload")
def upload(controller = Depends(get_ecommerce_controller)):
    return controller.upload(...)
```

#### 3. **Services** (`backend/services/`)

Business logic split by domain:

- **`ecommerce/`**
  - `CatalogService`: Identifies items, manages catalog
  - `DrillCoordinator`: Orchestrates drilling (identify → recommend → history)
  
- **`explainer/`**
  - `ContextAnalyzer`: Analyzes uploaded images, extracts context
  - `PageOrchestrator`: Orchestrates drill sequence (vision → generation)
  - `GenerationBridge`: Adapts vision outputs for image generation
  - `GroundingStrategies`: Segmentation strategies (SAM2, red-ring)

#### 4. **Repositories** (`backend/repositories/`)

Data access layer. Abstracts persistence (file, in-memory, external).

- `PageRepository`: CRUD for drill pages (file-backed JSON)
- `HistoryRepository`: Stores user drill history (in-memory, optional persistence)

#### 5. **Models** (`backend/models/`)

Pydantic schemas for API requests/responses.

- `explainer.py`: Vision, generation, drill request/response models
- `ecommerce.py`: Catalog, recommendation models

#### 6. **Shared** (`backend/shared/`)

Utilities and configs:

- `config.py`: Environment variable loading
- `errors.py`: `AppError` centralized error class
- `coordinates.py`: Bounding box and coordinate utilities
- `generation_bridge.py`: Vision → generation adapter
- `grounding_defaults.py`: SAM2/red-ring defaults
- `json_extractor.py`: Robust JSON parsing from LLM outputs

#### 7. **Core** (`backend/core/`)

Infrastructure:

- **`factory.py`**: `ServiceFactory` with lazy service creation and caching
- **`protocols.py`**: Python `Protocol` definitions for services and repositories

### Dependency Injection Flow

```
FastAPI Request
    ↓
Router (routes/ecommerce.py)
    ↓
Depends(get_ecommerce_controller)  ← FastAPI DI
    ↓
ServiceFactory.get_ecommerce_controller()  ← Lazy creation, cached
    ↓
Controller receives:
  - EcommerceCatalogService (singleton)
  - DrillCoordinator (singleton)
  - PageRepository (singleton)
```

### Error Handling

All errors surface as `AppError` (in `shared/errors.py`):

```python
@app.exception_handler(AppError)
async def handle_app_error(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "detail": exc.detail
        }
    )
```

---

## Frontend Layer Architecture

### Structure

```
frontend/src/
├── pages/
│   ├── EcommercePage.tsx
│   ├── ecommerce/
│   │   ├── UploadStep.tsx
│   │   ├── ItemPicker.tsx
│   │   └── RecommendationPanel.tsx
│   ├── ExplainerPage.tsx
│   └── explainer/
│       ├── UploadStep.tsx
│       ├── DrillViewer.tsx
│       └── ContextPanel.tsx
├── components/
│   ├── AppHeader.tsx
│   ├── ErrorBoundary.tsx
│   └── LoadingSpinner.tsx
├── services/
│   ├── ecommerce-api.ts
│   ├── explainer-api.ts
│   └── health-api.ts
├── hooks/
│   ├── useAppHealth.ts
│   ├── useHashMode.ts
│   └── useErrorHandler.ts
├── utils/
│   ├── coords.ts
│   ├── errors.ts
│   └── formatters.ts
└── assets/
    └── (static files)
```

### Key Components

#### Pages

- **EcommercePage**: Upload outfit → pick item → view recommendations
- **ExplainerPage**: Upload image/topic → view drill sequence → generate illustrations

#### Services (Kebab-case naming)

- **`ecommerce-api.ts`**: Wraps HTTP calls to `/api/ecommerce/*`
- **`explainer-api.ts`**: Wraps HTTP calls to `/api/explainer/vision/*` and `/api/explainer/generate/*`
- **`health-api.ts`**: Health check, feature availability

#### Hooks

- **`useAppHealth`**: Polls `/api/health`, detects Ollama availability
- **`useHashMode`**: Syncs URL hash with page state (preserves drill state in URL)

#### Utils

- **`coords.ts`**: Bounding box conversion, canvas coordinate transformation
- **`errors.ts`**: Error formatting, user-facing messages

---

## Shared Types (`packages/types/`)

TypeScript interfaces shared between frontend and backend (via `@shared/types`):

```typescript
// @shared/types
export interface HealthResponse {
  status: "ok";
  features: {
    ollama_available: boolean;
    sam2_available: boolean;
  };
}

export interface DrillPage {
  page_id: string;
  image_url: string;
  label: string;
  children: DrillPage[];
}
```

---

## Service Dependencies

### Ecommerce Mode

```
EcommerceCatalogService
├── Gemini API (item identification)
├── FashionCLIP encoder
└── Qdrant (vector DB)

DrillCoordinator
├── CatalogService (item lookup)
├── HistoryRepository (user state)
└── PageRepository (drill pages)
```

### Explainer Mode

```
ExplainerContextAnalyzer
├── Vision model (Ollama: qwen3.5:9b)
└── ContextExtractor

PageOrchestrator
├── ContextAnalyzer (vision)
├── GenerationBridge (adapter)
├── GroundingStrategies (SAM2 or red-ring)
└── GenerationService (Ollama: flux2)

GenerationService
└── Image model (Ollama: x/flux2-klein:4b-bf16)
```

---

## Data Flow

### Ecommerce Drill

```
User Upload (Image)
    ↓
EcommerceCatalogService.identify()  ← Gemini → item class
    ↓
DrillCoordinator.drill()  ← Get similar items from Qdrant
    ↓
PageRepository.save()  ← Persist drill pages
    ↓
Frontend: Display recommendations + history
```

### Explainer Drill

```
User Upload (Image/Topic)
    ↓
ExplainerContextAnalyzer.analyze()  ← Vision model extracts context
    ↓
PageOrchestrator.drill()
    ├── GroundingStrategies.ground()  ← SAM2 segmentation (optional)
    └── GenerationService.generate()  ← Image generation
    ↓
PageRepository.save()  ← Persist drill sequence
    ↓
Frontend: Display interactive drill tree
```

---

## Testing Strategy

### Backend (pytest)

- **Unit tests**: `test_service_factory.py`, `test_grounding_strategies.py`
- **Integration tests**: `test_page_repository.py`, `test_history_repository.py`
- **API tests**: `test_generate.py`, `test_catalog.py`

Run:
```bash
npm run test:backend
pytest tests/backend/ -v
```

### Frontend (vitest)

- **Utils**: `coords.test.ts`, `errors.test.ts`
- **Component**: Snapshot and behavior tests

Run:
```bash
npm run test:frontend
vitest
```

---

## Configuration

Environment variables (see `.env.example`):

**Ecommerce**:
- `GOOGLE_API_KEY`: Gemini API key
- `QDRANT_PATH`: Local or remote Qdrant instance
- `DATASET_IMAGES_DIR`: Fashion dataset path

**Explainer**:
- `OLLAMA_BASE`: Ollama server URL
- `EXPLAINER_VISION_MODEL`: Vision model name
- `IMAGE_MODEL`: Image generation model name
- `SAM2_PATH`: Optional SAM2 repo path
- `HF_TOKEN`: HuggingFace token for model weights

**Frontend**:
- `VITE_API_BASE`: Backend API URL (default: `http://127.0.0.1:8000`)

---

## SOLID Principles Adherence

| Principle | Implementation |
|-----------|-----------------|
| **SRP** | Each service has one responsibility; `PageOrchestrator` delegates to `ContextAnalyzer`, `GenerationBridge`, `GroundingStrategies` |
| **OCP** | New grounding strategies (SAM2, red-ring) added via `GroundingStrategies` class without modifying orchestrator |
| **LSP** | Services conform to `Protocol` interfaces; `ServiceFactory` creates interchangeable implementations |
| **ISP** | Protocols are minimal; clients depend on exact methods they need |
| **DIP** | `ServiceFactory` abstracts concrete service creation; controllers depend on protocols, not implementations |

---

## File Naming Conventions

- **Backend files**: `snake_case.py` (e.g., `page_orchestrator.py`, `context_analyzer.py`)
- **Backend classes**: `PascalCase` (e.g., `PageOrchestrator`, `ContextAnalyzer`)
- **Frontend files**: `kebab-case.ts` for services (e.g., `ecommerce-api.ts`), `PascalCase.tsx` for components
- **Frontend classes/types**: `PascalCase` (e.g., `EcommercePage`, `HealthResponse`)
- **Folders**: `lowercase` (e.g., `services/`, `repositories/`, `components/`)
- **Domain folders**: `lowercase` (e.g., `ecommerce/`, `explainer/`)

---

## Deployment Notes

- **Backend**: FastAPI on `:8000`, use Gunicorn/Uvicorn in production
- **Frontend**: Vite build to `dist/`, serve via static host or CDN
- **Data**: `data/` folder must be writable for Qdrant and uploads
- **Ollama**: Required for explainer mode; can be mocked for frontend dev
- **SAM2**: Optional; service gracefully falls back to red-ring segmentation
