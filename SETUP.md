# Semantic Drill Down — Setup Guide

## What you built
```
semantic-drill-down/
├── backend.py          ← FastAPI server (Python)
├── requirements.txt    ← Python packages
└── frontend/
    ├── package.json    ← Node packages
    ├── vite.config.js  ← Vite bundler config
    ├── index.html      ← HTML entry point
    └── src/
        ├── main.jsx    ← React entry (don't edit this)
        ├── App.jsx     ← Your entire React app ← EDIT THIS
        ├── App.css     ← Styles ← EDIT THIS
        └── index.css   ← Global reset (rarely edit)
```

---

## Step 1 — Install Python backend

```bash
cd semantic-drill-down
pip install -r requirements.txt
```

---

## Step 2 — Install Node (if you don't have it)

Download from https://nodejs.org  (choose the LTS version)

Check it works:
```bash
node --version   # should print v18 or higher
npm --version
```

---

## Step 3 — Install React dependencies

```bash
cd frontend
npm install
```

This reads `package.json` and downloads React + Vite into a `node_modules/` folder.
You only need to do this once.

---

## Step 4 — Run both servers (two terminal tabs)

**Terminal 1 — Backend:**
```bash
cd semantic-drill-down
uvicorn backend:app --reload --port 8000
```
You should see: `Uvicorn running on http://0.0.0.0:8000`

**Terminal 2 — Frontend:**
```bash
cd semantic-drill-down/frontend
npm run dev
```
You should see: `Local: http://localhost:5173/`

Open http://localhost:5173 in your browser.

---

## Step 5 — Make sure Ollama is running

```bash
ollama serve
```

Your models must already be pulled:
```bash
ollama pull qwen2.5vl:7b
ollama pull x/flux2-klein:4b-bf16
```

---

## How to edit the React app

- **Change the API URL:** Edit the `const API = '...'` line at the top of `App.jsx`
- **Change colors/fonts:** Edit the CSS variables in `index.css` (the `:root` block)
- **Change the prompt:** Edit the `prompt` string inside `backend.py` → `analyze()`
- **Change the crop radius:** Edit `fd.append('radius', 80)` in `App.jsx`

Changes to `.jsx` and `.css` files hot-reload instantly in the browser.
Changes to `backend.py` auto-reload because of `--reload` in uvicorn.

---

## React concepts used (quick reference)

| Concept | What it does |
|---|---|
| `useState(x)` | Stores a value that re-renders the UI when changed |
| `useRef(null)` | Gets a pointer to a real DOM element (like getElementById) |
| `useEffect(fn, [])` | Runs code after the component first renders |
| `FormData` | Sends files + form fields in a fetch() request |
| `async/await` | Waits for a network request to complete |
| JSX | HTML-like syntax inside JavaScript — `className` not `class` |
