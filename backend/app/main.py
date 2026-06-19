from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
import hashlib
import os
import shutil
import uuid
import json
from .core.config import settings
from .services.vision import vision_service
from .services.search import search_service
from .services.shopping_sources.router import shopping_router
from PIL import Image, ImageOps

app = FastAPI(title="AI Ecommerce DrillDown API")

@app.get("/api/health")
async def health():
    return {"status": "ok"}

os.makedirs(settings.DEBUG_DIR, exist_ok=True)
os.makedirs(settings.UPLOADS_DIR, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_UPLOAD_DIM = 1280  # max px on longest side sent to Qwen and displayed

@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    image_id = str(uuid.uuid4())
    content = await file.read()
    image_hash = hashlib.md5(content).hexdigest()

    # Always normalize to JPEG at a capped resolution so Qwen's returned
    # coordinates are in the same space as what PIL and the browser see.
    import io
    with Image.open(io.BytesIO(content)) as img:
        img = ImageOps.exif_transpose(img)   # honour EXIF rotation
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > MAX_UPLOAD_DIM:
            scale = MAX_UPLOAD_DIM / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            w, h = img.size

    image_filename = f"{image_id}.jpg"
    image_path = os.path.join(settings.UPLOADS_DIR, image_filename)
    img.save(image_path, "JPEG", quality=92)
    print(f"Saved upload {image_filename}: {w}x{h}")

    return {"imageId": image_id, "imageHash": image_hash, "imageUrl": f"/uploads/{image_filename}", "filename": image_filename}

@app.post("/api/detect-garments")
async def detect_garments(filename: str = Form(...)):
    print(f"\n--- DETECT GARMENTS: {filename} ---")
    image_path = os.path.join(settings.UPLOADS_DIR, filename)
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
        
    try:
        garments = await vision_service.detect_garments(image_path)
    except Exception as exc:
        print(f"Garment detection failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Garment detection failed: {exc}")
    return {"garments": garments}

@app.post("/api/get-details")
async def get_details(filename: str = Form(...), bbox: str = Form(...)):
    print(f"\n--- GET DETAILS: {filename} ---")
    image_path = os.path.join(settings.UPLOADS_DIR, filename)
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
        
    try:
        bbox_dict = json.loads(bbox)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid bounding box format")
        
    try:
        details = await vision_service.analyze_garment(image_path, bbox_dict)
    except Exception as exc:
        print(f"Garment analysis failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Garment analysis failed: {exc}")
    if not details:
        raise HTTPException(status_code=500, detail="Failed to analyze garment")
        
    return details

@app.post("/api/search-products")
async def search_products(query: str = Form(...)):
    print(f"\n--- SEARCH PRODUCTS: {query} ---")
    products = await shopping_router.route_query(query)
    return {"products": products}

@app.post("/api/rerank")
async def rerank_products(
    filename: str = Form(...),
    bbox: str = Form(...),
    products: str = Form(...),
    attributes: str = Form(...)
):
    print(f"\n--- RERANK PRODUCTS ---")
    image_path = os.path.join(settings.UPLOADS_DIR, filename)
    
    try:
        bbox_dict = json.loads(bbox)
        products_list = json.loads(products)
        attributes_dict = json.loads(attributes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
    # Crop target image for FashionCLIP
    crop_path = os.path.join(settings.DEBUG_DIR, f"crop_{uuid.uuid4()}.jpg")
    with Image.open(image_path) as img:
        crop = img.crop((bbox_dict['x1'], bbox_dict['y1'], bbox_dict['x2'], bbox_dict['y2']))
        crop.save(crop_path)
        
    ranked_products = await search_service.rerank_products(crop_path, products_list, attributes_dict)
    
    if os.path.exists(crop_path):
        os.remove(crop_path)
        
    return {"products": ranked_products}

# Static files
from fastapi.staticfiles import StaticFiles
app.mount("/uploads", StaticFiles(directory=settings.UPLOADS_DIR), name="uploads")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
