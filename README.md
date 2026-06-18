# DrillDown: The Infinite Technical Canvas

DrillDown is an advanced visual exploration system that combines Vision AI, Object Segmentation, Depth Estimation, and Generative AI to allow users to "drill into" images. By identifying specific sub-components, estimating depth layers, and generating high-detail macro close-ups or immersive point-of-view perspectives, it creates an interactive, infinite technical diagram experience.

---

## 🚀 Key Features

- **Autonomous Scene Analysis:** Automatically scans and annotates key technical regions (objects, materials, textures) in any image using a high-tech scanning animation.
- **Infinite Technical Zoom:** Generate endless nested layers of technical detail by clicking objects directly or clicking automated technical labels.
- **Perspective POV Mode:** Supports switching from standard macro-detail zooms into a **First-Person Point-of-View (POV) perspective** looking outward from the selected component.
- **Dynamic 3D Parallax Scene Canvas:** Interactive layers separated using local AI-driven depth estimation (`DepthService`), creating a tactile 3D depth illusion as you hover and move your mouse.
- **Smooth Flipbook Animations:** Renders cinematic transitions between drill layers using automatic server-side frames and client-side flipbook video integration.
- **Coordinate Guardrails & Robust Grounding:** Utilizes Meta SAM2 (Segment Anything) and specialized parsing logic to prevent misalignment and guarantee spatial grounding.
- **Multimodal AI Orchestration:** Integrates cloud models alongside a fully **100% Local Offline Fallback** that maintains robust technical prompt engineering.

---

## 🛠 Technology Stack

### Frontend (Client)
- **Framework:** React 19 (Vite), JavaScript (ES Modules).
- **Animations & Graphics:** Three.js / React Three Fiber & Drei (for immersive 3D/canvas effects), SVG graphics, and CSS3.
- **Interactive UI Components:** 
  - `ParallaxScene`: Live mouse-driven 3D parallax effects utilizing custom depth maps.
  - `FlipbookPlayer`: Clean frame-blending/video player for cinematic depth transitions.

### Backend (Server)
- **Framework:** FastAPI (Python 3.10+).
- **Core Pipelines:**
  - `AIService`: Manages multimodal prompt routing and schema parsing.
  - `SAM2Service`: Executes spatial grounding and mask segmentation using Meta's Segment Anything Model 2.
  - `DepthService`: Generates depth maps to isolate interactive visual planes.
  - `VideoService`: Handles transitions and server-side flipbook generation.
  - `DocumentService`: Handles text/manual conversions and ingestion.

### AI Models
- **Vision & Reasoning (Cloud & Local):** 
  - **Gemini 2.5 Pro:** High-fidelity cloud vision.
  - **Qwen 2.5/3.5 (9B) Local Fallback:** Self-hosted on Ollama (`qwen3.5:9b`), configured with a high-capacity **8,192 token context window** to safely handle dense image tokens and detailed JSON payloads.
- **Segmentation:** Meta SAM2.
- **Depth Estimation:** Self-hosted depth map pipelines.
- **Generation:** FLUX.1 [schnell] & Google Imagen 4.0 (for rendering infinite drill layers).

---

## 📦 Setup & Installation

### 1. Backend Setup
1. **Initialize Virtual Environment & Install Dependencies:**
   ```bash
   cd server
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. **Environment Configuration (`server/.env`):**
   Configure your access keys:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key
   HF_TOKEN=your_huggingface_token
   NVIDIA_API_KEY=your_nvidia_api_key
   ```
3. **Local Ollama Setup (For Local Vision Fallback):**
   Make sure Ollama is installed and the Qwen model is pulled:
   ```bash
   ollama pull qwen3.5:9b
   ```
4. **Run the Backend Server:**
   ```bash
   PYTHONPATH=. python3 app/main.py
   ```
   *The API will boot on `http://localhost:8000`*

### 2. Frontend Setup
1. **Install Dependencies:**
   ```bash
   cd client
   npm install
   ```
2. **Run Vite Development Server:**
   ```bash
   npm run dev
   ```
   *The client web application will be accessible on `http://localhost:5173`*

---

## 📂 Project Structure

```
├───client/
│   ├───src/
│   │   ├───components/
│   │   │   ├───FlipbookPlayer.jsx     # Controls transitions & animation playbacks
│   │   │   └───ParallaxScene.jsx      # Mouse-interactive 3D depth experience
│   │   ├───App.jsx                    # Primary single-page app layout
│   │   ├───api.js                     # Standard API connectors to FastAPI
│   │   └───main.jsx
│   └───package.json
├───server/
│   ├───app/
│   │   ├───api/
│   │   │   └───pages.py               # Pages router with SSE streaming endpoints
│   │   ├───services/
│   │   │   ├───ai_service.py          # Multimodal routing, prompting & parsing
│   │   │   ├───depth_service.py       # Handles local depth map extraction
│   │   │   ├───document_service.py    # Manages manual ingestion & extraction
│   │   │   ├───page_service.py        # Coordinates drill logic & layout state
│   │   │   ├───sam2_service.py        # Spatial mask segmentation
│   │   │   └───video_service.py       # Cinematic frame sequencer
│   │   └───main.py                    # App initialization & FastAPI entrypoint
│   └───requirements.txt
└───notes/                             # Design, reports, and architecture deep-dives
```

---
**Developed for the DrillDown Capstone Project.**
