# Semantic Drill Down Setup

Run all commands from the project root:

```bash
cd /Users/sshah/Documents/personal_capstone_drilldown-1
```

## 1. Install Dependencies

Python backend:

```bash
python3 -m pip install -r requirements.txt
```

React frontend:

```bash
npm install
```

## 2. Start Ollama

In a separate terminal:

```bash
ollama serve
```

Make sure the configured models exist locally:

```bash
ollama pull qwen2.5vl:7b
ollama pull x/flux2-klein:4b-bf16
```

The backend reads these values from `.env`:

```env
OLLAMA_BASE=http://localhost:11434
VISION_MODEL=qwen2.5vl:7b
IMAGE_MODEL=x/flux2-klein:4b-bf16
MODEL_PROVIDER=ollama
```

## 3. Run Backend

In a new terminal from the project root:

```bash
npm run backend
```

Equivalent direct command:

```bash
python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Check it:

```bash
curl http://127.0.0.1:8000/api/health
```

You want:

```json
{"status":"ok","ollama":true,"provider":"ollama"}
```

## 4. Run Frontend

In another terminal from the project root:

```bash
npm run frontend
```

Open:

```text
http://127.0.0.1:5174/
```

## Common Errors

If backend says `ImportError: attempted relative import beyond top-level package`, you started the wrong app path. Use:

```bash
python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

If frontend says it cannot find `package.json`, you are probably inside `frontend/`. Run `npm run frontend` from the project root.

If the frontend shows `Backend offline`, make sure the backend is running on port `8000` and `.env` / `frontend/.env` both point to `127.0.0.1:8000`.

If image generation returns `Model returned no image`, Ollama responded but the selected `IMAGE_MODEL` did not return image data from `/api/generate`.
