# DrillDown Project - Complete Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [Implementation History](#implementation-history)
5. [Design System](#design-system)
6. [Features](#features)
7. [Troubleshooting](#troubleshooting)

---

## Project Overview

**DrillDown Unified** - An AI-powered visual exploration platform with two modes:

### Explainer Mode
Upload or describe a topic → AI generates illustration with auto-labels → click any component → generates deeper illustrated layer using Ollama vision + Flux image generation.

### Ecommerce Mode  
Upload outfit photo → AI identifies items → click item → get product recommendations using Gemini + FashionCLIP + Qdrant vector search.

---

## Quick Start

```bash
cd /Users/sshah/Downloads/personal_capstone_drilldown-drilldown-v1

# 1. Environment setup
cp .env.example .env
# Edit .env: Add GOOGLE_API_KEY for ecommerce; MODEL_PROVIDER=ollama for explainer

# 2. Install dependencies
pip install -r requirements.txt
npm install

# 3. Install Ollama models (for explainer mode)
ollama pull qwen3.5:9b
ollama pull x/flux2-klein:4b-bf16

# 4. Optional: Ingest ecommerce data
npm run ingest -- --limit 1000

# 5. Start the application
npm run backend    # API server on :8000
npm run frontend   # UI on :5173
```

**Access Points:**
- Explainer: http://127.0.0.1:5173/#/explainer
- Ecommerce: http://127.0.0.1:5173/#/ecommerce
- API docs: http://127.0.0.1:8000/docs

---

## Architecture

### Project Structure

```
drilldown-unified/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI entry point
│   │   ├── controllers/           # Request handlers
│   │   ├── routes/                # HTTP endpoints
│   │   └── dependencies.py        # Dependency injection
│   ├── core/
│   │   ├── factory.py             # Service factory
│   │   └── protocols.py           # Interface definitions
│   ├── services/
│   │   ├── ecommerce/             # Catalog, drill coordination
│   │   └── explainer/             # Vision, orchestration, generation
│   ├── repositories/              # Data access layer
│   ├── models/                    # Pydantic schemas
│   └── shared/                    # Config, utilities
├── frontend/src/
│   ├── components/
│   │   └── ui/                    # UI components
│   ├── pages/                     # Route views
│   ├── services/                  # API clients
│   └── styles/                    # CSS files
├── data/                          # Runtime storage
├── tests/                         # Backend & frontend tests
└── docs/                          # Additional documentation
```

### API Endpoints

| Prefix | Purpose |
|--------|---------|
| `/api/ecommerce/*` | Upload, identify, drill, history |
| `/api/explainer/vision/*` | Upload, analyze, page, stream-page, confirm-drill |
| `/api/explainer/generate/*` | Generate images from text |
| `/uploads`, `/dataset`, `/static` | Static file serving |

### Technology Stack

**Backend:**
- FastAPI (Python web framework)
- Ollama (Local LLM/vision models)
- PIL/Pillow (Image processing)
- Qdrant (Vector database for ecommerce)

**Frontend:**
- React + TypeScript
- Vite (Build tool)
- Tailwind CSS
- Recharts (Data visualization)
- Framer Motion (Animations)

---

## Implementation History

### Phase 1: Home Page & Enterprise Theme
- Created professional landing page with hero section
- Implemented split-color "DrillDown" branding (white + orange)
- Applied enterprise dark theme with exact colors:
  - Orange: #D56434
  - Gold: #c5a059
  - Black: #0a0a0a
- Centered layout with search and mode shortcuts

### Phase 2: New UI Integration
- Replaced old UI with professional split-screen layout
- Integrated backend API with drill-adapter service layer
- Created DrillCanvas, ProductPanel, and RecentDrills components
- Implemented responsive design with Tailwind

### Phase 3: Color System Refinement
- Applied accurate colors from original design:
  - Primary: #bbc7df (light blue-gray)
  - Secondary: #ffb598 (soft peach/orange)
  - Orange Glow: #D56434 (burnt orange)
  - Navy backgrounds: #142240 and #1e3460
- Updated fonts: Playfair Display, Source Sans 3, JetBrains Mono
- Made RecentDrills fully dynamic (removed hardcoded content)

### Phase 4: Image Upload Flow Optimization
- Instant image display (< 200ms after upload)
- Two-phase rendering: Show image → Analyze → Labels appear
- Progressive labeling with "🔴 Generating Labels..." indicator
- Auto-redirect to canvas view after upload

### Phase 5: UX Polish
- Removed unnecessary UI elements
- Hidden tabs when in canvas view
- Simplified ProductPanel interactions
- Improved loading states and feedback

### Phase 6: Label & Coordinate Fixes
- Fixed label positioning to use backend's granular_details format
- Added coordinate conversion (normalized 0-1 to percentage)
- Implemented comprehensive coordinate logging
- Added position tooltips for debugging

### Phase 7: Panel Restructuring
- Changed "SPECIFICATIONS" to "ALL LABELS" showing all components
- Updated "DESCRIPTION" to show whole image description
- Added drilldown capability on each label
- Made entire label cards clickable
- Panel title shows image name (not component name)

### Phase 8: Layout Stability
- Fixed ProductPanel width to stable 420px
- Locked canvas to viewport height (no scrolling)
- Improved flex container hierarchy
- Better responsive behavior

### Phase 9: Drilldown Flow Enhancement
- Made label cards directly clickable for drilldown
- Added single "GENERATE DRILLDOWN" button
- Implemented click detection: First click selects, second drills
- Removed individual action buttons from labels

### Phase 10: Performance & Generation Fix
- Fixed image generation timeout issue
- Frontend now calls `/confirm-drill` endpoint after "confirm" event
- Added coordinate validation to prevent crop errors
- Enhanced loading overlay with realistic time estimates (2-5 min)
- Added detailed error logging for debugging

---

## Design System

### Color Palette

```css
/* Primary Colors */
--primary: #bbc7df        /* Light blue-gray (text, borders) */
--secondary: #ffb598      /* Soft peach/orange (buttons, accents) */
--orange-glow: #D56434    /* Burnt orange (highlights, hover) */

/* Backgrounds */
--navy-dark: #142240      /* Main background */
--navy-light: #1e3460     /* Panel backgrounds */
--black: #0a0a0a          /* Deep black */

/* Accents */
--gold: #c5a059           /* Gold accents */
```

### Typography

- **Headers**: Playfair Display (serif, elegant)
- **Body**: Source Sans 3 (sans-serif, readable)
- **Code/Data**: JetBrains Mono (monospace)

### Component Styles

**Buttons:**
- Primary: Orange (#ffb598) with hover effects
- Disabled: Muted with reduced opacity
- Border radius: 0.5rem (rounded-lg)

**Panels:**
- Fixed width: 420px
- Background: Navy light (#1e3460)
- Border: 1px solid primary color
- Padding: 1.5rem

**Canvas:**
- Full viewport height (no scroll)
- Dark background with image centered
- Red circle hotspots with hover tooltips
- Smooth transitions and animations

---

## Features

### Explainer Mode Features

1. **Image Upload & Analysis**
   - Drag & drop or click to upload
   - Instant image display (< 200ms)
   - AI vision analysis in background
   - Progressive label generation

2. **Interactive Canvas**
   - Click hotspots to view details
   - Hover tooltips with component names
   - Coordinate display for debugging
   - Smooth animations

3. **Component Panel**
   - ALL LABELS tab: Lists all detected components
   - DESCRIPTION tab: Shows overall image description
   - Clickable label cards for drilldown
   - Fixed stable layout

4. **Drilldown Generation**
   - Click any component to drill deeper
   - AI generates detailed sub-component view
   - 2-5 minute generation with progress indicator
   - Maintains drill history in timeline

5. **Drill Path Timeline**
   - Visual history of drill stages
   - Click to navigate back to any stage
   - Shows thumbnail previews
   - Current stage highlighted

6. **Topic-based Generation**
   - Describe a topic in text
   - AI generates initial illustration
   - Auto-analyzes and adds labels
   - Same drill capabilities

### Ecommerce Mode Features

1. **Outfit Upload**
   - Upload fashion/outfit photos
   - AI identifies individual items

2. **Item Identification**
   - Uses Gemini vision API
   - Detects clothing items and accessories
   - Clickable hotspots on items

3. **Product Recommendations**
   - Vector search using FashionCLIP
   - Qdrant database for similarity matching
   - Shows similar products from catalog

---

## Troubleshooting

### Common Issues

**1. Image Generation Taking Too Long (4-5 minutes)**
- **Fixed**: Frontend now properly calls confirm-drill endpoint
- The streaming API requires confirmation to trigger generation
- Check browser console for generation progress logs

**2. Labels Not Appearing on Image**
- Backend returns `granular_details` format with normalized coordinates
- Frontend converts `point[0] * 100` for x, `point[1] * 100` for y
- Check console logs for coordinate conversion details

**3. 404 Not Found Errors**
- Ensure backend is running: `npm run backend`
- Check API base URL in `.env`: `VITE_API_BASE=http://127.0.0.1:8000`
- Verify Ollama is running: `ollama list`

**4. Coordinate Validation Errors ("right < left")**
- **Fixed**: Added coordinate validation in image_utils.py
- Prevents invalid crop regions near image edges
- Automatically adjusts to valid bounds

**5. Canvas Scrolling Issues**
- Main container uses `h-screen overflow-hidden`
- Canvas container has `flex-1 min-h-0`
- Fixed panel width prevents layout shifts

**6. Models Not Loading**
```bash
# Verify Ollama models are installed
ollama list

# Install required models
ollama pull qwen3.5:9b
ollama pull x/flux2-klein:4b-bf16

# Check Ollama is running
curl http://localhost:11434/api/tags
```

**7. Build Errors**
```bash
# Clear caches and reinstall
rm -rf node_modules frontend/node_modules
npm install
cd frontend && npm install

# Rebuild
npm run build
```

### Debug Mode

Enable detailed logging in browser console:
- Coordinate mapping logs show label positioning
- API call logs show request/response flow
- Generation progress shows current step

Check backend logs for:
- Image generation progress
- Coordinate validation
- Model inference timing

### Performance Tips

1. **Reduce Analysis Time**: Use `scanMode: "focus"` instead of "global"
2. **Faster Generation**: Use smaller Flux model or mock provider for testing
3. **Cache Results**: Drill results are cached by default
4. **Optimize Images**: Resize large uploads to < 2MB before uploading

---

## Environment Variables

### Required for Explainer Mode

```bash
# Ollama Configuration
OLLAMA_BASE=http://localhost:11434
EXPLAINER_VISION_MODEL=qwen3.5:9b
IMAGE_MODEL=x/flux2-klein:4b-bf16
MODEL_PROVIDER=ollama

# Paths
EXPLAINER_STATIC_DIR=./data/explainer/static
```

### Required for Ecommerce Mode

```bash
# Google Gemini API
GOOGLE_API_KEY=your_api_key_here

# Qdrant Vector DB
QDRANT_PATH=./data/qdrant_storage

# Fashion Dataset
DATASET_IMAGES_DIR=./data/fashion-dataset/images
```

### Frontend Configuration

```bash
VITE_API_BASE=http://127.0.0.1:8000
```

---

## Testing

```bash
# Run all tests
npm run test

# Backend tests only
npm run test:backend

# Frontend tests only
npm run test:frontend

# Smoke test (requires backend running)
npm run smoke

# Health check
npm run health
```

---

## Recent Fixes Applied

1. ✅ Frontend now calls `/confirm-drill` endpoint to trigger image generation
2. ✅ Added coordinate validation to prevent crop errors
3. ✅ Enhanced loading states with realistic time estimates
4. ✅ Fixed label coordinate mapping for granular_details format
5. ✅ Improved error handling and logging throughout the stack

---

## Development Workflow

```bash
# Terminal 1: Backend
npm run backend

# Terminal 2: Frontend  
npm run frontend

# Terminal 3: Tests/Commands
npm run test
npm run health
```

**Hot Reload:**
- Backend: FastAPI auto-reloads on Python file changes
- Frontend: Vite HMR updates on save

**Building for Production:**
```bash
npm run build
# Outputs to frontend/dist/
```

---

## Support & Resources

- API Documentation: http://127.0.0.1:8000/docs
- Health Check: http://127.0.0.1:8000/api/health
- Frontend Dev Server: http://127.0.0.1:5173

For issues, check:
1. Browser console (F12)
2. Backend terminal logs
3. Network tab in DevTools
4. This documentation's Troubleshooting section

---

**Last Updated**: 2026-06-20
**Version**: 1.0.0-complete
