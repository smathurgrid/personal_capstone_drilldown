# # ============================================================
# # backend.py  —  FastAPI server for Semantic Drill Down
# # ============================================================
# # Run with:  uvicorn backend:app --reload --port 8000
# # ============================================================

# from fastapi import FastAPI, UploadFile, File, Form
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from PIL import Image, ImageDraw
# import requests
# import base64
# import io
# import torch
# from diffusers import StableDiffusionImg2ImgPipeline

# from starlette.formparsers import MultiPartParser          # ← ADD
# MultiPartParser.max_part_size = 50 * 1024 * 1024          # ← ADD
# MultiPartParser.max_field_size = 50 * 1024 * 1024   # 50 MB for form fields  ← THE FIX
 

# app = FastAPI()
# # ── CORS ─────────────────────────────────────────────────────
# # This tells the server "it's OK to accept requests from the
# # React dev server running on localhost:5174"
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5174"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ── CONFIG ────────────────────────────────────────────────────
# OLLAMA_BASE  = "http://localhost:11434"
# VISION_MODEL = "qwen2.5vl:7b"
# IMAGE_MODEL  = "x/flux2-klein:4b-bf16"

# # ── HELPERS ───────────────────────────────────────────────────

# def pil_to_b64(img: Image.Image) -> str:
#     """Convert a PIL image → base64 string (PNG format)."""
#     buf = io.BytesIO()
#     img.save(buf, format="PNG")
#     return base64.b64encode(buf.getvalue()).decode()


# # ── ROUTE 1: Health Check ────────────────────────────────────
# # React calls this on startup to know if Ollama is ready

# @app.get("/api/health")
# def health():
#     try:
#         r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
#         if r.status_code == 200:
#             return {"status": "ok", "ollama": True}
#     except Exception:
#         pass
#     return JSONResponse({"status": "error", "ollama": False}, status_code=503)


# # ── ROUTE 2: Vision Analysis ──────────────────────────────────
# # Receives: the original image file + click coordinates
# # Returns:  analysis text, image_prompt, local crop b64, marked image b64

# @app.post("/api/analyze")
# async def analyze(
#     image:  UploadFile = File(...),      # the uploaded image file
#     x:      int        = Form(...),      # click X in actual image pixels
#     y:      int        = Form(...),      # click Y in actual image pixels
#     radius: int        = Form(80),       # how big the crop region is
# ):
#     # 1. Read uploaded file → PIL Image
#     img_bytes = await image.read()
#     original  = Image.open(io.BytesIO(img_bytes)).convert("RGB")

#     # 2. Draw red circle on a COPY (this is the "global context" image)
#     marked = original.copy()
#     draw   = ImageDraw.Draw(marked)
#     draw.ellipse((x-radius, y-radius, x+radius, y+radius), outline="red", width=6)
#     draw.ellipse((x-8,      y-8,      x+8,      y+8),      fill="red")

#     # 3. Crop the clicked region (this is the "local context" image)
#     x1 = max(0, x - radius)
#     y1 = max(0, y - radius)
#     x2 = min(original.width,  x + radius)
#     y2 = min(original.height, y + radius)
#     local_crop = original.crop((x1, y1, x2, y2))

#     # 4. Convert both to base64 so we can send them to Ollama
#     global_b64 = pil_to_b64(marked)
#     local_b64  = pil_to_b64(local_crop)

#     # 5. Build the vision prompt — we send TWO images for better understanding
#     prompt = """You are analyzing an image for a recursive semantic drill-down visualization.

# You are given TWO images:
#   Image 1 — FULL scene with a RED circle marking the region of interest (global context)
#   Image 2 — A CLOSE-UP crop of exactly what is inside the red circle (local context)

# Your task:
# 1. Use Image 1 to understand WHERE in the scene this region is.
# 2. Use Image 2 to understand WHAT is actually there in fine detail.
# 3. Describe what hidden internal structures, microscopic layers, or deeper details
#    naturally exist inside this region — things you wouldn't see at normal zoom.

# Format your response EXACTLY like this:

# ANALYSIS:
# <2-3 sentences combining global + local understanding>

# IMAGE PROMPT:
# <A single paragraph. Photorealistic. Highly detailed. Describes zooming INTO this
#  specific region to reveal its internal structure. Written as an image generation prompt.>"""

#     payload = {
#         "model": VISION_MODEL,
#         "messages": [{
#             "role":    "user",
#             "content": prompt,
#             "images":  [global_b64, local_b64],   # ← send BOTH images
#         }],
#         "stream": False,
#     }

#     r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=120)
#     r.raise_for_status()
#     result = r.json()["message"]["content"]

#     # 6. Parse the structured response
#     analysis_text = result
#     image_prompt  = result   # fallback: use everything

#     if "IMAGE PROMPT:" in result:
#         parts        = result.split("IMAGE PROMPT:")
#         image_prompt = parts[-1].strip()
#         if "ANALYSIS:" in parts[0]:
#             analysis_text = parts[0].split("ANALYSIS:")[-1].strip()

#     return {
#         "analysis":        analysis_text,
#         "image_prompt":    image_prompt,
#         "local_crop_b64":  local_b64,    # the cropped region
#         "marked_image_b64": global_b64,  # full image with red circle
#     }


# # ── ROUTE 3: Image-to-Image Generation ───────────────────────
# # KEY CHANGE from the original Streamlit version:
# # Instead of text→image, we now send:
# #   - the AI-written prompt
# #   - the local crop  (primary visual reference — what to zoom into)
# #   - the global image (secondary — scene context)
# # This is "image-to-image" generation

# @app.post("/api/generate")
# async def generate(
#     prompt:          str = Form(...),
#     local_crop_b64:  str = Form(...),   # cropped region as base64
#     global_b64:      str = Form(...),   # full marked image as base64
# ):
#     payload = {
#         "model":  IMAGE_MODEL,
#         "prompt": prompt,
#         "images": [local_crop_b64, global_b64],   # ← img2img: pass both images
#         "stream": False,
#     }

#     r = requests.post(f"{OLLAMA_BASE}/api/generate", json=payload, timeout=300)
#     r.raise_for_status()
#     data = r.json()

#     # Ollama flux returns either "image" (singular) or "images" (list)
#     if "image" in data and data["image"]:
#         return {"image_b64": data["image"]}
#     elif "images" in data and data["images"]:
#         return {"image_b64": data["images"][0]}
#     else:
#         return JSONResponse(
#             {"error": "Model returned no image. Is it loaded correctly?", "raw": data},
#             status_code=500
#         )
#------attempt 2-------#
# ============================================================
# backend.py  —  FastAPI server for Semantic Drill Down
# ============================================================

# from fastapi import FastAPI, UploadFile, File, Form
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from PIL import Image, ImageDraw
# import requests
# import base64
# import io
# import torch
# from diffusers import StableDiffusionImg2ImgPipeline

# from starlette.formparsers import MultiPartParser
# MultiPartParser.max_part_size = 50 * 1024 * 1024   # 50MB limit

# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5174"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# OLLAMA_BASE  = "http://localhost:11434"
# VISION_MODEL = "qwen2.5vl:7b"

# # ── Device detection ──────────────────────────────────────────

# if torch.backends.mps.is_available():
#     DEVICE = "mps"
# elif torch.cuda.is_available():
#     DEVICE = "cuda"
# else:
#     DEVICE = "cpu"

# print(f"Using device: {DEVICE}")

# # ── Load SD + IP-Adapter once at startup ──────────────────────

# print("Loading Stable Diffusion pipeline...")

# pipeline = StableDiffusionImg2ImgPipeline.from_pretrained(
#     "runwayml/stable-diffusion-v1-5",
#     torch_dtype=torch.float16 if DEVICE != "cpu" else torch.float32,
#     safety_checker=None
# ).to(DEVICE)

# pipeline.enable_attention_slicing()

# print("Loading IP-Adapter...")

# pipeline.load_ip_adapter(
#     "h94/IP-Adapter",
#     subfolder="models",
#     weight_name="ip-adapter_sd15.bin"
# )

# # 0.6 = balanced global influence
# pipeline.set_ip_adapter_scale(0.6)

# print("Pipeline ready.")

# # ── HELPERS ───────────────────────────────────────────────────

# def pil_to_b64(img: Image.Image) -> str:
#     """Convert PIL image → base64 PNG string."""
#     buf = io.BytesIO()
#     img.save(buf, format="PNG")
#     return base64.b64encode(buf.getvalue()).decode()


# def crop_region(original: Image.Image, x: int, y: int, radius: int):
#     """Crop a square region around (x, y) with given radius."""
#     x1 = max(0, x - radius)
#     y1 = max(0, y - radius)
#     x2 = min(original.width,  x + radius)
#     y2 = min(original.height, y + radius)
#     return original.crop((x1, y1, x2, y2))


# # ── ROUTE 1: Health Check ─────────────────────────────────────

# @app.get("/api/health")
# def health():
#     try:
#         r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
#         if r.status_code == 200:
#             return {"status": "ok", "ollama": True, "device": DEVICE}
#     except Exception:
#         pass
#     return JSONResponse({"status": "error", "ollama": False}, status_code=503)


# # ── ROUTE 2: Vision Analysis ──────────────────────────────────
# # Receives: image file + click coordinates
# # Returns:  analysis text, image_prompt, local crop b64, marked image b64

# @app.post("/api/analyze")
# async def analyze(
#     image:  UploadFile = File(...),
#     x:      int        = Form(...),
#     y:      int        = Form(...),
#     radius: int        = Form(80),
# ):
#     # Read uploaded file → PIL Image
#     img_bytes = await image.read()
#     original  = Image.open(io.BytesIO(img_bytes)).convert("RGB")

#     # Draw red circle on a copy (global context)
#     marked = original.copy()
#     draw   = ImageDraw.Draw(marked)
#     draw.ellipse((x-radius, y-radius, x+radius, y+radius), outline="red", width=6)
#     draw.ellipse((x-8, y-8, x+8, y+8), fill="red")

#     # Crop clicked region (local context)
#     local_crop = crop_region(original, x, y, radius)

#     # Convert both to base64 for Ollama vision call
#     global_b64 = pil_to_b64(marked)
#     local_b64  = pil_to_b64(local_crop)

#     # Vision prompt — two images sent together
#     prompt = """You are analyzing an image for a recursive semantic drill-down visualization.

# You are given TWO images:
#   Image 1 — FULL scene with a RED circle marking the region of interest (global context)
#   Image 2 — A CLOSE-UP crop of exactly what is inside the red circle (local context)

# Your task:
# 1. Use Image 1 to understand WHERE in the scene this region is.
# 2. Use Image 2 to understand WHAT is actually there in fine detail.
# 3. Describe what hidden internal structures, microscopic layers, or deeper details
#    naturally exist inside this region.

# Format your response EXACTLY like this:

# ANALYSIS:
# <2-3 sentences combining global + local understanding>

# IMAGE PROMPT:
# <A single paragraph. Photorealistic. Highly detailed. Describes zooming INTO this
#  specific region to reveal its internal structure. Written as an image generation prompt.>"""

#     payload = {
#         "model": VISION_MODEL,
#         "messages": [{
#             "role":    "user",
#             "content": prompt,
#             "images":  [global_b64, local_b64],
#         }],
#         "stream": False,
#     }

#     r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=120)
#     r.raise_for_status()
#     result = r.json()["message"]["content"]

#     # Parse structured response
#     analysis_text = result
#     image_prompt  = result

#     if "IMAGE PROMPT:" in result:
#         parts        = result.split("IMAGE PROMPT:")
#         image_prompt = parts[-1].strip()
#         if "ANALYSIS:" in parts[0]:
#             analysis_text = parts[0].split("ANALYSIS:")[-1].strip()

#     return {
#         "analysis":         analysis_text,
#         "image_prompt":     image_prompt,
#         "local_crop_b64":   local_b64,
#         "marked_image_b64": global_b64,
#     }


# # ── ROUTE 3: Image-to-Image Generation ───────────────────────
# # CHANGED: now receives image file + x/y coords instead of base64 strings
# # Backend re-crops the region itself — no large base64 in transit
# #
# # Sends TWO images to SD + IP-Adapter natively:
# #   image            = crop  (local context  — what to transform)
# #   ip_adapter_image = full  (global context — scene reference)

# @app.post("/api/generate")
# async def generate(
#     image:  UploadFile = File(...),   # ← CHANGED: file instead of base64
#     x:      int        = Form(...),   # ← CHANGED: coords instead of base64
#     y:      int        = Form(...),   # ← CHANGED
#     prompt: str        = Form(...),
# ):
#     # Read image + re-crop (same as analyze does)
#     img_bytes = await image.read()
#     original  = Image.open(io.BytesIO(img_bytes)).convert("RGB")

#     radius = 250   # larger crop for generation than analysis
#     crop   = crop_region(original, x, y, radius)

#     # Resize both to 512x512 (SD native resolution)
#     crop_512 = crop.resize((512, 512), Image.LANCZOS)
#     full_512 = original.resize((512, 512), Image.LANCZOS)

#     negative_prompt = (
#         "blurry, low quality, distorted, deformed, ugly, "
#         "cartoon, illustration, painting, text, watermark, "
#         "out of focus, overexposed, underexposed"
#     )

#     try:
#         with torch.inference_mode():
#             output = pipeline(
#                 prompt              = prompt,
#                 negative_prompt     = negative_prompt,
#                 image               = crop_512,    # local context
#                 ip_adapter_image    = full_512,    # global context
#                 strength            = 0.70,
#                 guidance_scale      = 7.5,
#                 num_inference_steps = 40
#             )

#         generated_img = output.images[0]
#         generated_img.thumbnail((512, 512), Image.LANCZOS)

#         return {"image_b64": pil_to_b64(generated_img)}

#     except Exception as e:
#         return JSONResponse(
#             status_code=500,
#             content={"error": f"Generation failed: {str(e)}"}
#         )

#----------attempt 3----------

# from fastapi import FastAPI, UploadFile, File, Form, Request
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from PIL import Image, ImageDraw
# import requests
# import base64
# import io

# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5174"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# OLLAMA_BASE  = "http://localhost:11434"
# VISION_MODEL = "qwen2.5vl:7b"
# IMAGE_MODEL  = "x/flux2-klein:4b-bf16"


# def pil_to_b64(img: Image.Image) -> str:
#     buf = io.BytesIO()
#     img.save(buf, format="PNG")
#     return base64.b64encode(buf.getvalue()).decode()


# # ── ROUTE 1: Health Check ─────────────────────────────────────
# @app.get("/api/health")
# def health():
#     try:
#         r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
#         if r.status_code == 200:
#             return {"status": "ok", "ollama": True}
#     except Exception:
#         pass
#     return JSONResponse({"status": "error", "ollama": False}, status_code=503)


# # ── ROUTE 2: Vision Analysis ──────────────────────────────────
# # Still uses multipart/form-data but only for the actual FILE upload +
# # small integer fields — no large base64 strings here, so no size issue.
# @app.post("/api/analyze")
# async def analyze(
#     image:  UploadFile = File(...),
#     x:      int        = Form(...),
#     y:      int        = Form(...),
#     radius: int        = Form(80),
# ):
#     img_bytes = await image.read()
#     original  = Image.open(io.BytesIO(img_bytes)).convert("RGB")

#     marked = original.copy()
#     draw   = ImageDraw.Draw(marked)
#     draw.ellipse((x-radius, y-radius, x+radius, y+radius), outline="red", width=6)
#     draw.ellipse((x-8, y-8, x+8, y+8), fill="red")

#     x1 = max(0, x - radius)
#     y1 = max(0, y - radius)
#     x2 = min(original.width,  x + radius)
#     y2 = min(original.height, y + radius)
#     local_crop = original.crop((x1, y1, x2, y2))

#     global_b64 = pil_to_b64(marked)
#     local_b64  = pil_to_b64(local_crop)

#     prompt = """You are analyzing an image for a recursive semantic drill-down visualization.

# You are given TWO images:
#   Image 1 — FULL scene with a RED circle marking the region of interest (global context)
#   Image 2 — A CLOSE-UP crop of exactly what is inside the red circle (local context)

# Your task:
# 1. Use Image 1 to understand WHERE in the scene this region is.
# 2. Use Image 2 to understand WHAT is actually there in fine detail.
# 3. Describe what hidden internal structures, microscopic layers, or deeper details
#    naturally exist inside this region — things you wouldn't see at normal zoom.

# Format your response EXACTLY like this:

# ANALYSIS:
# <2-3 sentences combining global + local understanding>

# IMAGE PROMPT:
# <A single paragraph. Photorealistic. Highly detailed. Describes zooming INTO this
#  specific region to reveal its internal structure. Written as an image generation prompt.>"""

#     payload = {
#         "model": VISION_MODEL,
#         "messages": [{
#             "role":    "user",
#             "content": prompt,
#             "images":  [global_b64, local_b64],
#         }],
#         "stream": False,
#     }

#     r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=120)
#     r.raise_for_status()
#     result = r.json()["message"]["content"]

#     analysis_text = result
#     image_prompt  = result

#     if "IMAGE PROMPT:" in result:
#         parts        = result.split("IMAGE PROMPT:")
#         image_prompt = parts[-1].strip()
#         if "ANALYSIS:" in parts[0]:
#             analysis_text = parts[0].split("ANALYSIS:")[-1].strip()

#     return {
#         "analysis":         analysis_text,
#         "image_prompt":     image_prompt,
#         "local_crop_b64":   local_b64,
#         "marked_image_b64": global_b64,
#     }


# # ── ROUTE 3: Image Generation ─────────────────────────────────
# # KEY FIX: Accept JSON body instead of multipart/form-data.
# # Base64 strings are large — sending them as Form() fields hits
# # Starlette's multipart field size limit (1024 KB by default).
# # A JSON body has no such limit in FastAPI/Starlette.
# @app.post("/api/generate")
# async def generate(request: Request):
#     body           = await request.json()          # ← plain JSON, no size limit
#     prompt         = body["prompt"]
#     local_crop_b64 = body["local_crop_b64"]
#     global_b64     = body["global_b64"]

#     payload = {
#         "model":  IMAGE_MODEL,
#         "prompt": prompt,
#         "images": [local_crop_b64, global_b64],
#         "stream": False,
#     }

#     r = requests.post(f"{OLLAMA_BASE}/api/generate", json=payload, timeout=300)
#     r.raise_for_status()
#     data = r.json()

#     if "image" in data and data["image"]:
#         return {"image_b64": data["image"]}
#     elif "images" in data and data["images"]:
#         return {"image_b64": data["images"][0]}
#     else:
#         return JSONResponse(
#             {"error": "Model returned no image. Is it loaded correctly?", "raw": data},
#             status_code=500,
#         )
    


# #attemp4 
# from fastapi import FastAPI, UploadFile, File, Form, Request
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from PIL import Image, ImageDraw
# import requests
# import base64
# import io

# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5174"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# OLLAMA_BASE  = "http://localhost:11434"
# VISION_MODEL = "qwen2.5vl:7b"
# IMAGE_MODEL  = "x/flux2-klein:4b-bf16"


# def pil_to_b64(img: Image.Image) -> str:
#     buf = io.BytesIO()
#     img.save(buf, format="PNG")
#     return base64.b64encode(buf.getvalue()).decode()


# # ── ROUTE 1: Health Check ─────────────────────────────────────
# @app.get("/api/health")
# def health():
#     try:
#         r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
#         if r.status_code == 200:
#             return {"status": "ok", "ollama": True}
#     except Exception:
#         pass
#     return JSONResponse({"status": "error", "ollama": False}, status_code=503)


# # ── ROUTE 2: Vision Analysis ──────────────────────────────────
# # Still uses multipart/form-data but only for the actual FILE upload +
# # small integer fields — no large base64 strings here, so no size issue.
# @app.post("/api/analyze")
# async def analyze(
#     image:  UploadFile = File(...),
#     x:      int        = Form(...),
#     y:      int        = Form(...),
#     radius: int        = Form(80),
# ):
#     img_bytes = await image.read()
#     original  = Image.open(io.BytesIO(img_bytes)).convert("RGB")

#     marked = original.copy()
#     draw   = ImageDraw.Draw(marked)
#     draw.ellipse((x-radius, y-radius, x+radius, y+radius), outline="red", width=6)
#     draw.ellipse((x-8, y-8, x+8, y+8), fill="red")

#     x1 = max(0, x - radius)
#     y1 = max(0, y - radius)
#     x2 = min(original.width,  x + radius)
#     y2 = min(original.height, y + radius)
#     local_crop = original.crop((x1, y1, x2, y2))

#     global_b64 = pil_to_b64(marked)
#     local_b64  = pil_to_b64(local_crop)

#     prompt = """You are analyzing an image for a recursive semantic drill-down visualization.

# You are given TWO images:
#   Image 1 — FULL scene with a RED circle marking the region of interest (global context)
#   Image 2 — A CLOSE-UP crop of exactly what is inside the red circle (local context)

# Your task:
# 1. Use Image 1 to understand WHERE in the scene this region is.
# 2. Use Image 2 to understand WHAT is actually there in fine detail.
# 3. Describe what hidden internal structures, microscopic layers, or deeper details
#    naturally exist inside this region — things you wouldn't see at normal zoom.

# Format your response EXACTLY like this:

# ANALYSIS:
# <2-3 sentences combining global + local understanding>

# IMAGE PROMPT:
# <A single paragraph. Photorealistic. Highly detailed. Describes zooming INTO this
#  specific region to reveal its internal structure. Written as an image generation prompt.>"""

#     payload = {
#         "model": VISION_MODEL,
#         "messages": [{
#             "role":    "user",
#             "content": prompt,
#             "images":  [global_b64, local_b64],
#         }],
#         "stream": False,
#     }

#     r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=120)
#     r.raise_for_status()
#     result = r.json()["message"]["content"]

#     analysis_text = result
#     image_prompt  = result

#     if "IMAGE PROMPT:" in result:
#         parts        = result.split("IMAGE PROMPT:")
#         image_prompt = parts[-1].strip()
#         if "ANALYSIS:" in parts[0]:
#             analysis_text = parts[0].split("ANALYSIS:")[-1].strip()

#     return {
#         "analysis":         analysis_text,
#         "image_prompt":     image_prompt,
#         "local_crop_b64":   local_b64,
#         "marked_image_b64": global_b64,
#     }


# # ── ROUTE 3: Image Generation ─────────────────────────────────
# # KEY FIX: Accept JSON body instead of multipart/form-data.
# # Base64 strings are large — sending them as Form() fields hits
# # Starlette's multipart field size limit (1024 KB by default).
# # A JSON body has no such limit in FastAPI/Starlette.
# @app.post("/api/generate")
# async def generate(request: Request):
#     body           = await request.json()          # ← plain JSON, no size limit
#     prompt         = body["prompt"]
#     local_crop_b64 = body["local_crop_b64"]
#     global_b64     = body["global_b64"]

#     payload = {
#         "model":  IMAGE_MODEL,
#         "prompt": prompt,
#         "images": [local_crop_b64, global_b64],
#         "stream": False,
#     }

#     r = requests.post(f"{OLLAMA_BASE}/api/generate", json=payload, timeout=300)
#     r.raise_for_status()
#     data = r.json()

#     if "image" in data and data["image"]:
#         return {"image_b64": data["image"]}
#     elif "images" in data and data["images"]:
#         return {"image_b64": data["images"][0]}
#     else:
#         return JSONResponse(
#             {"error": "Model returned no image. Is it loaded correctly?", "raw": data},
#             status_code=500,
#         )

#-----attempt last 
# from fastapi import FastAPI, UploadFile, File, Form, Request
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from PIL import Image, ImageDraw
# import requests
# import base64
# import io

# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5174"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# OLLAMA_BASE  = "http://localhost:11434"
# VISION_MODEL = "qwen2.5vl:7b"
# IMAGE_MODEL  = "x/flux2-klein:4b-bf16"


# def pil_to_b64(img: Image.Image) -> str:
#     buf = io.BytesIO()
#     img.save(buf, format="PNG")
#     return base64.b64encode(buf.getvalue()).decode()


# # ── ROUTE 1: Health Check ─────────────────────────────────────
# @app.get("/api/health")
# def health():
#     try:
#         r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
#         if r.status_code == 200:
#             return {"status": "ok", "ollama": True}
#     except Exception:
#         pass
#     return JSONResponse({"status": "error", "ollama": False}, status_code=503)


# # ── ROUTE 2: Vision Analysis ──────────────────────────────────
# @app.post("/api/analyze")
# async def analyze(
#     image:  UploadFile = File(...),
#     x:      int        = Form(...),
#     y:      int        = Form(...),
#     radius: int        = Form(80),
# ):
#     img_bytes = await image.read()
#     original  = Image.open(io.BytesIO(img_bytes)).convert("RGB")

#     marked = original.copy()
#     draw   = ImageDraw.Draw(marked)
#     draw.ellipse((x-radius, y-radius, x+radius, y+radius), outline="red", width=6)
#     draw.ellipse((x-8, y-8, x+8, y+8), fill="red")

#     x1 = max(0, x - radius)
#     y1 = max(0, y - radius)
#     x2 = min(original.width,  x + radius)
#     y2 = min(original.height, y + radius)
#     local_crop = original.crop((x1, y1, x2, y2))

#     global_b64 = pil_to_b64(marked)
#     local_b64  = pil_to_b64(local_crop)

#     prompt = """You are analyzing an image for a recursive semantic drill-down visualization.
# This is an EDUCATIONAL EXPLAINER tool — like an illustrated textbook or infographic.

# You are given TWO images:
#   Image 1 — FULL scene with a RED circle marking the region of interest (global context)
#   Image 2 — A CLOSE-UP crop of exactly what is inside the red circle (local context)

# Your task:
# 1. Use Image 1 to understand WHERE in the scene this region is.
# 2. Use Image 2 to understand WHAT is actually there in fine detail.
# 3. Describe what hidden internal structures, layers, components, or deeper details
#    naturally exist inside this region — things a student would want to learn about.

# Format your response EXACTLY like this:

# ANALYSIS:
# <2-3 sentences combining global + local understanding>

# IMAGE PROMPT:
# <A single paragraph describing an EDUCATIONAL ILLUSTRATION of what is inside this
#  region. Style: clean technical illustration, cross-section cutaway views, soft
#  watercolor or muted palette, architectural/scientific diagram style.
#  NOT photorealistic — think textbook illustration or encyclopedia diagram.
#  CRITICAL: Do NOT include ANY text, labels, titles, annotations, callout lines,
#  or words in the image. The image must be PURELY visual with ZERO text or lettering
#  of any kind. Describe only visual elements, structures, colors, and composition.>"""

#     payload = {
#         "model": VISION_MODEL,
#         "messages": [{
#             "role":    "user",
#             "content": prompt,
#             "images":  [global_b64, local_b64],
#         }],
#         "stream": False,
#     }

#     r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=120)
#     r.raise_for_status()
#     result = r.json()["message"]["content"]

#     analysis_text = result
#     image_prompt  = result

#     if "IMAGE PROMPT:" in result:
#         parts        = result.split("IMAGE PROMPT:")
#         image_prompt = parts[-1].strip()
#         if "ANALYSIS:" in parts[0]:
#             analysis_text = parts[0].split("ANALYSIS:")[-1].strip()

#     return {
#         "analysis":         analysis_text,
#         "image_prompt":     image_prompt,
#         "local_crop_b64":   local_b64,
#         "marked_image_b64": global_b64,
#     }


# # ── ROUTE 3: Image Generation ─────────────────────────────────
# @app.post("/api/generate")
# async def generate(request: Request):
#     body           = await request.json()
#     prompt         = body["prompt"]
#     local_crop_b64 = body["local_crop_b64"]
#     global_b64     = body["global_b64"]

#     payload = {
#         "model":  IMAGE_MODEL,
#         "prompt": prompt,
#         "images": [local_crop_b64, global_b64],
#         "stream": False,
#     }

#     r = requests.post(f"{OLLAMA_BASE}/api/generate", json=payload, timeout=300)
#     r.raise_for_status()
#     data = r.json()

#     if "image" in data and data["image"]:
#         return {"image_b64": data["image"]}
#     elif "images" in data and data["images"]:
#         return {"image_b64": data["images"][0]}
#     else:
#         return JSONResponse(
#             {"error": "Model returned no image. Is it loaded correctly?", "raw": data},
#             status_code=500,
#         )


# # ── ROUTE 4: Generate Initial Image from Text Prompt ──────────
# @app.post("/api/generate-from-text")
# async def generate_from_text(request: Request):
#     body = await request.json()
#     user_topic = body["topic"]

#     # Step 1: Use vision model to create a detailed explainer prompt
#     prompt_for_vlm = f"""You are an educational illustrator. A user wants to explore: "{user_topic}"

# Create a detailed image generation prompt for the FIRST overview illustration.
# This should be a wide establishing view — like the first page of a textbook chapter.

# Style: clean technical illustration, soft watercolor or muted palette,
# architectural/scientific diagram style, cross-section or cutaway view if appropriate.
# Think textbook illustration or encyclopedia diagram.
# CRITICAL: Do NOT include ANY text, labels, titles, annotations, callout lines,
# or words in the image. The image must be PURELY visual with ZERO text or lettering.
# Describe only visual elements, structures, colors, and composition.

# Respond with ONLY the image generation prompt, nothing else."""

#     vlm_payload = {
#         "model": VISION_MODEL,
#         "messages": [{"role": "user", "content": prompt_for_vlm}],
#         "stream": False,
#     }

#     r = requests.post(f"{OLLAMA_BASE}/api/chat", json=vlm_payload, timeout=120)
#     r.raise_for_status()
#     image_prompt = r.json()["message"]["content"].strip()

#     # Step 2: Generate the image
#     gen_payload = {
#         "model":  IMAGE_MODEL,
#         "prompt": image_prompt,
#         "stream": False,
#     }

#     r = requests.post(f"{OLLAMA_BASE}/api/generate", json=gen_payload, timeout=300)
#     r.raise_for_status()
#     data = r.json()

#     image_b64 = None
#     if "image" in data and data["image"]:
#         image_b64 = data["image"]
#     elif "images" in data and data["images"]:
#         image_b64 = data["images"][0]

#     if not image_b64:
#         return JSONResponse(
#             {"error": "Model returned no image", "raw": data},
#             status_code=500,
#         )

#     return {
#         "image_b64":    image_b64,
#         "image_prompt": image_prompt,
#     }

##----testing phase 
# ============================================================
# backend.py  —  FastAPI server for Semantic Drill Down
# ============================================================
# Run with:  uvicorn backend:app --reload --port 8000
# ============================================================

# from fastapi import FastAPI, UploadFile, File, Form, Request
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from PIL import Image, ImageDraw
# import requests
# import base64
# import io

# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5174"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# OLLAMA_BASE  = "http://localhost:11434"
# VISION_MODEL = "qwen2.5vl:7b"
# IMAGE_MODEL  = "x/flux2-klein:4b-bf16"


# def pil_to_b64(img: Image.Image) -> str:
#     """Convert PIL image → base64 PNG string."""
#     buf = io.BytesIO()
#     img.save(buf, format="PNG")
#     return base64.b64encode(buf.getvalue()).decode()


# # ── ROUTE 1: Health Check ─────────────────────────────────────
# @app.get("/api/health")
# def health():
#     try:
#         r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
#         if r.status_code == 200:
#             return {"status": "ok", "ollama": True}
#     except Exception:
#         pass
#     return JSONResponse({"status": "error", "ollama": False}, status_code=503)


# # ── ROUTE 2: Vision Analysis ──────────────────────────────────
# @app.post("/api/analyze")
# async def analyze(
#     image:  UploadFile = File(...),
#     x:      int        = Form(...),
#     y:      int        = Form(...),
#     radius: int        = Form(80),
# ):
#     img_bytes = await image.read()
#     original  = Image.open(io.BytesIO(img_bytes)).convert("RGB")

#     # Clamp coordinates to image bounds (safety)
#     x = max(0, min(x, original.width  - 1))
#     y = max(0, min(y, original.height - 1))

#     marked = original.copy()
#     draw   = ImageDraw.Draw(marked)
#     draw.ellipse((x-radius, y-radius, x+radius, y+radius), outline="red", width=6)
#     draw.ellipse((x-8, y-8, x+8, y+8), fill="red")

#     x1 = max(0, x - radius)
#     y1 = max(0, y - radius)
#     x2 = min(original.width,  x + radius)
#     y2 = min(original.height, y + radius)

#     # Extra safety: ensure valid crop bounds
#     if x2 <= x1: x2 = x1 + 1
#     if y2 <= y1: y2 = y1 + 1

#     local_crop = original.crop((x1, y1, x2, y2))

#     global_b64 = pil_to_b64(marked)
#     local_b64  = pil_to_b64(local_crop)

#     prompt = """You are analyzing an image for a recursive semantic drill-down visualization.
# This is an EDUCATIONAL EXPLAINER tool — like an illustrated textbook or infographic.

# You are given TWO images:
#   Image 1 — FULL scene with a RED circle marking the region of interest (global context)
#   Image 2 — A CLOSE-UP crop of exactly what is inside the red circle (local context)

# Your task:
# 1. Use Image 1 to understand WHERE in the scene this region is.
# 2. Use Image 2 to understand WHAT is actually there in fine detail.
# 3. Describe what hidden internal structures, layers, components, or deeper details
#    naturally exist inside this region — things a student would want to learn about.

# Format your response EXACTLY like this:

# ANALYSIS:
# <2-3 sentences combining global + local understanding>

# IMAGE PROMPT:
# <A single paragraph describing an EDUCATIONAL ILLUSTRATION of what is inside this
#  region. Style: clean technical illustration, cross-section cutaway views, soft
#  watercolor or muted palette, architectural/scientific diagram style.
#  NOT photorealistic — think textbook illustration or encyclopedia diagram.
#  CRITICAL: Do NOT include ANY text, labels, titles, annotations, callout lines,
#  or words in the image. The image must be PURELY visual with ZERO text or lettering
#  of any kind. Describe only visual elements, structures, colors, and composition.>"""

#     payload = {
#         "model": VISION_MODEL,
#         "messages": [{
#             "role":    "user",
#             "content": prompt,
#             "images":  [global_b64, local_b64],
#         }],
#         "stream": False,
#     }

#     r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=120)
#     r.raise_for_status()
#     result = r.json()["message"]["content"]

#     analysis_text = result
#     image_prompt  = result

#     if "IMAGE PROMPT:" in result:
#         parts        = result.split("IMAGE PROMPT:")
#         image_prompt = parts[-1].strip()
#         if "ANALYSIS:" in parts[0]:
#             analysis_text = parts[0].split("ANALYSIS:")[-1].strip()

#     return {
#         "analysis":         analysis_text,
#         "image_prompt":     image_prompt,
#         "local_crop_b64":   local_b64,
#         "marked_image_b64": global_b64,
#     }


# # ── ROUTE 3: Image Generation (drill-down) ────────────────────
# @app.post("/api/generate")
# async def generate(request: Request):
#     body           = await request.json()
#     prompt         = body["prompt"]
#     local_crop_b64 = body["local_crop_b64"]
#     global_b64     = body["global_b64"]

#     payload = {
#         "model":  IMAGE_MODEL,
#         "prompt": prompt,
#         "images": [local_crop_b64, global_b64],
#         "stream": False,
#     }

#     r = requests.post(f"{OLLAMA_BASE}/api/generate", json=payload, timeout=300)
#     r.raise_for_status()
#     data = r.json()

#     if "image" in data and data["image"]:
#         return {"image_b64": data["image"]}
#     elif "images" in data and data["images"]:
#         return {"image_b64": data["images"][0]}
#     else:
#         return JSONResponse(
#             {"error": "Model returned no image. Is it loaded correctly?", "raw": data},
#             status_code=500,
#         )


# # ── ROUTE 4: Generate Initial Image from Text Prompt ──────────
# @app.post("/api/generate-from-text")
# async def generate_from_text(request: Request):
#     body = await request.json()
#     user_topic = body["topic"]

#     # Step 1: Use vision model to create a detailed image prompt
#     prompt_for_vlm = f"""You are an educational illustrator. A user wants to explore: "{user_topic}"

# Create a detailed image generation prompt for the FIRST overview illustration.
# This should be a wide establishing view — like the first page of a textbook chapter.

# Style: clean technical illustration, soft watercolor or muted palette,
# architectural/scientific diagram style, cross-section or cutaway view if appropriate.
# Think textbook illustration or encyclopedia diagram.
# CRITICAL: Do NOT include ANY text, labels, titles, annotations, callout lines,
# or words in the image. The image must be PURELY visual with ZERO text or lettering.
# Describe only visual elements, structures, colors, and composition.

# Respond with ONLY the image generation prompt, nothing else."""

#     vlm_payload = {
#         "model": VISION_MODEL,
#         "messages": [{"role": "user", "content": prompt_for_vlm}],
#         "stream": False,
#     }

#     r = requests.post(f"{OLLAMA_BASE}/api/chat", json=vlm_payload, timeout=120)
#     r.raise_for_status()
#     image_prompt = r.json()["message"]["content"].strip()

#     # Step 2: Generate the image
#     gen_payload = {
#         "model":  IMAGE_MODEL,
#         "prompt": image_prompt,
#         "stream": False,
#     }

#     r = requests.post(f"{OLLAMA_BASE}/api/generate", json=gen_payload, timeout=300)
#     r.raise_for_status()
#     data = r.json()

#     image_b64 = None
#     if "image" in data and data["image"]:
#         image_b64 = data["image"]
#     elif "images" in data and data["images"]:
#         image_b64 = data["images"][0]

#     if not image_b64:
#         return JSONResponse(
#             {"error": "Model returned no image", "raw": data},
#             status_code=500,
#         )

#     return {
#         "image_b64":    image_b64,
#         "image_prompt": image_prompt,
#     }

##---
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, ImageDraw
import requests
import base64
import io

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_BASE  = "http://localhost:11434"
VISION_MODEL = "qwen2.5vl:7b"
IMAGE_MODEL  = "x/flux2-klein:4b-bf16"


def pil_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ── ROUTE 1: Health Check ─────────────────────────────────────
@app.get("/api/health")
def health():
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        if r.status_code == 200:
            return {"status": "ok", "ollama": True}
    except Exception:
        pass
    return JSONResponse({"status": "error", "ollama": False}, status_code=503)


# ── ROUTE 2: Vision Analysis ──────────────────────────────────
@app.post("/api/analyze")
async def analyze(
    image:  UploadFile = File(...),
    x:      int        = Form(...),
    y:      int        = Form(...),
    radius: int        = Form(80),
):
    img_bytes = await image.read()
    original  = Image.open(io.BytesIO(img_bytes)).convert("RGB")

    marked = original.copy()
    draw   = ImageDraw.Draw(marked)
    draw.ellipse((x-radius, y-radius, x+radius, y+radius), outline="red", width=6)
    draw.ellipse((x-8, y-8, x+8, y+8), fill="red")

    x1 = max(0, x - radius)
    y1 = max(0, y - radius)
    x2 = min(original.width,  x + radius)
    y2 = min(original.height, y + radius)
    local_crop = original.crop((x1, y1, x2, y2))

    global_b64 = pil_to_b64(marked)
    local_b64  = pil_to_b64(local_crop)

    prompt = """You are analyzing an image for a recursive semantic drill-down visualization.
This is an EDUCATIONAL EXPLAINER tool — like an illustrated textbook or infographic.

You are given TWO images:
  Image 1 — FULL scene with a RED circle marking the region of interest (global context)
  Image 2 — A CLOSE-UP crop of exactly what is inside the red circle (local context)

Your task:
1. Use Image 1 to understand WHERE in the scene this region is.
2. Use Image 2 to understand WHAT is actually there in fine detail.
3. Describe what hidden internal structures, layers, components, or deeper details
   naturally exist inside this region — things a student would want to learn about.

Format your response EXACTLY like this:

ANALYSIS:
<2-3 sentences combining global + local understanding>

IMAGE PROMPT:
<A single paragraph describing an EDUCATIONAL ILLUSTRATION of what is inside this
 region. Style: clean technical illustration, cross-section cutaway views, soft
 watercolor or muted palette, architectural/scientific diagram style.
 NOT photorealistic — think textbook illustration or encyclopedia diagram.
 CRITICAL: Do NOT include ANY text, labels, titles, annotations, callout lines,
 or words in the image. The image must be PURELY visual with ZERO text or lettering
 of any kind. Describe only visual elements, structures, colors, and composition.>"""

    payload = {
        "model": VISION_MODEL,
        "messages": [{
            "role":    "user",
            "content": prompt,
            "images":  [global_b64, local_b64],
        }],
        "stream": False,
    }

    r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=120)
    r.raise_for_status()
    result = r.json()["message"]["content"]

    analysis_text = result
    image_prompt  = result

    if "IMAGE PROMPT:" in result:
        parts        = result.split("IMAGE PROMPT:")
        image_prompt = parts[-1].strip()
        if "ANALYSIS:" in parts[0]:
            analysis_text = parts[0].split("ANALYSIS:")[-1].strip()

    return {
        "analysis":         analysis_text,
        "image_prompt":     image_prompt,
        "local_crop_b64":   local_b64,
        "marked_image_b64": global_b64,
    }


# ── ROUTE 3: Image Generation ─────────────────────────────────
@app.post("/api/generate")
async def generate(request: Request):
    body           = await request.json()
    prompt         = body["prompt"]
    local_crop_b64 = body["local_crop_b64"]
    global_b64     = body["global_b64"]

    payload = {
        "model":  IMAGE_MODEL,
        "prompt": prompt,
        "images": [local_crop_b64, global_b64],
        "stream": False,
    }

    r = requests.post(f"{OLLAMA_BASE}/api/generate", json=payload, timeout=300)
    r.raise_for_status()
    data = r.json()

    if "image" in data and data["image"]:
        return {"image_b64": data["image"]}
    elif "images" in data and data["images"]:
        return {"image_b64": data["images"][0]}
    else:
        return JSONResponse(
            {"error": "Model returned no image. Is it loaded correctly?", "raw": data},
            status_code=500,
        )


# ── ROUTE 4: Generate Initial Image from Text Prompt ──────────
@app.post("/api/generate-from-text")
async def generate_from_text(request: Request):
    body = await request.json()
    user_topic = body["topic"]

    # Step 1: Use vision model to create a detailed explainer prompt
    prompt_for_vlm = f"""You are an educational illustrator. A user wants to explore: "{user_topic}"

Create a detailed image generation prompt for the FIRST overview illustration.
This should be a wide establishing view — like the first page of a textbook chapter.

Style: clean technical illustration, soft watercolor or muted palette,
architectural/scientific diagram style, cross-section or cutaway view if appropriate.
Think textbook illustration or encyclopedia diagram.
CRITICAL: Do NOT include ANY text, labels, titles, annotations, callout lines,
or words in the image. The image must be PURELY visual with ZERO text or lettering.
Describe only visual elements, structures, colors, and composition.

Respond with ONLY the image generation prompt, nothing else."""

    vlm_payload = {
        "model": VISION_MODEL,
        "messages": [{"role": "user", "content": prompt_for_vlm}],
        "stream": False,
    }

    r = requests.post(f"{OLLAMA_BASE}/api/chat", json=vlm_payload, timeout=120)
    r.raise_for_status()
    image_prompt = r.json()["message"]["content"].strip()

    # Step 2: Generate the image
    gen_payload = {
        "model":  IMAGE_MODEL,
        "prompt": image_prompt,
        "stream": False,
    }

    r = requests.post(f"{OLLAMA_BASE}/api/generate", json=gen_payload, timeout=300)
    r.raise_for_status()
    data = r.json()

    image_b64 = None
    if "image" in data and data["image"]:
        image_b64 = data["image"]
    elif "images" in data and data["images"]:
        image_b64 = data["images"][0]

    if not image_b64:
        return JSONResponse(
            {"error": "Model returned no image", "raw": data},
            status_code=500,
        )

    return {
        "image_b64":    image_b64,
        "image_prompt": image_prompt,
    }
