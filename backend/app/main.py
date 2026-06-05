from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import hashlib
import os
import shutil
import uuid
from .core.config import settings
from .services.vision import vision_service
from .services.search import search_service
from PIL import Image, ImageDraw
import json

app = FastAPI(title="AI Ecommerce DrillDown API")

# Ensure debug directory exists
os.makedirs(settings.DEBUG_DIR, exist_ok=True)

@app.get("/")
async def root():
    return {
        "message": "AI Ecommerce DrillDown API is running",
        "frontend_url": "http://localhost:5173",
        "docs_url": "http://localhost:8000/docs"
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for history (for demo purposes, could be Redis)
drill_history = []

def draw_marker(image, x_norm, y_norm):
    draw = ImageDraw.Draw(image)
    width, height = image.size
    cx, cy = x_norm * width, y_norm * height
    
    # Outer ring
    radius = 12
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline="red", width=3)
    # Inner dot
    dot_radius = 4
    draw.ellipse([cx - dot_radius, cy - dot_radius, cx + dot_radius, cy + dot_radius], fill="red")
    return image

@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    # Generate unique ID and hash
    image_id = str(uuid.uuid4())
    content = await file.read()
    image_hash = hashlib.md5(content).hexdigest()
    
    file_ext = os.path.splitext(file.filename)[1]
    image_filename = f"{image_id}{file_ext}"
    image_path = os.path.join(settings.UPLOADS_DIR, image_filename)
    
    with open(image_path, "wb") as f:
        f.write(content)
        
    return {"imageId": image_id, "imageHash": image_hash, "imageUrl": f"/uploads/{image_filename}"}

@app.post("/api/identify")
async def identify_item(
    imageId: str = Form(...),
    x: float = Form(...),
    y: float = Form(...)
):
    print(f"\n--- NEW DRILLDOWN REQUEST ---")
    print(f"Coordinates: x={x:.4f}, y={y:.4f}")
    
    # 1. Find original image
    image_filename = None
    for f in os.listdir(settings.UPLOADS_DIR):
        if f.startswith(imageId):
            image_filename = f
            break
            
    if not image_filename:
        raise HTTPException(status_code=404, detail="Image not found")
        
    original_path = os.path.join(settings.UPLOADS_DIR, image_filename)
    
    # 2. Generate Composite Image
    img = Image.open(original_path).convert("RGB")
    composite_img = img.copy()
    composite_img = draw_marker(composite_img, x, y)
    
    composite_filename = f"comp_{image_filename}"
    composite_path = os.path.join(settings.DEBUG_DIR, composite_filename)
    composite_img.save(composite_path)
    
    # Save original to debug too
    img.save(os.path.join(settings.DEBUG_DIR, f"orig_{image_filename}"))
    
    # 3. Identify item with Gemini (Original + Composite)
    attributes = await vision_service.identify_item(original_path, composite_path, x, y)
    
    if not attributes:
        print(f"FAILED: Gemini identification returned no attributes")
        raise HTTPException(status_code=500, detail="Could not identify item")
        
    print(f"IDENTIFIED: {attributes.get('articleType')} ({attributes.get('color')})")
    print(f"DESCRIPTION: {attributes.get('description')}")

    # 4. Generate Fused Embeddings with FashionCLIP
    bbox = attributes.get('bounding_box')
    
    # Validation: Ensure bbox exists and is valid
    if not bbox or not all(k in bbox for k in ['x1', 'y1', 'x2', 'y2']):
        print("WARNING: Invalid bounding box, using full image for retrieval")
        orig_crop = img
        comp_crop = composite_img
    else:
        x1, y1, x2, y2 = bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2']
        # Clamp to image size
        x1, x2 = max(0, min(x1, img.width)), max(0, min(x2, img.width))
        y1, y2 = max(0, min(y1, img.height)), max(0, min(y2, img.height))
        
        if x2 <= x1 or y2 <= y1:
            print(f"WARNING: Zero dimension crop, using full image")
            orig_crop = img
            comp_crop = composite_img
        else:
            print(f"CROPPING: {x1}, {y1}, {x2}, {y2} (Size: {x2-x1}x{y2-y1})")
            orig_crop = img.crop((x1, y1, x2, y2))
            comp_crop = composite_img.crop((x1, y1, x2, y2))
            
            # Save crops for diagnostics
            orig_crop.save(os.path.join(settings.DEBUG_DIR, f"crop_orig_{image_filename}"))
            comp_crop.save(os.path.join(settings.DEBUG_DIR, f"crop_comp_{image_filename}"))
    
    # Get fused embedding (0.7 orig + 0.3 comp)
    embedding = search_service.get_embedding(orig_crop, comp_crop)
    
    # 5. Hybrid Search in Qdrant (Visual + Semantic)
    search_results = await search_service.hybrid_search(embedding, attributes)
    
    # 6. Format and Return
    results = []
    for res in search_results:
        results.append({
            "product_id": res.id,
            "visual_score": res.score, # This is the final fused score now
            "payload": res.payload
        })
    
    print(f"PIPELINE COMPLETE: Found {len(results)} ranked matches")
        
    node = {
        "id": str(uuid.uuid4()),
        "imageId": imageId,
        "x": x,
        "y": y,
        "attributes": attributes,
        "results": results
    }
    drill_history.append(node)
    
    return node

@app.post("/api/drill")
async def drill_down(
    productId: int = Form(...),
    x: float = Form(...),
    y: float = Form(...)
):
    # Find product image in dataset
    image_filename = f"{productId}.jpg"
    image_path = os.path.join(settings.DATASET_IMAGES_DIR, image_filename)
    
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Product image not found")
        
    # For drilldown, we don't necessarily need a composite since it's a known product,
    # but to keep logic consistent we follow the same path.
    img = Image.open(image_path).convert("RGB")
    composite_img = img.copy()
    composite_img = draw_marker(composite_img, x, y)
    
    # Save to temp for vision service
    temp_orig = os.path.join(settings.DEBUG_DIR, f"temp_drill_orig_{productId}.jpg")
    temp_comp = os.path.join(settings.DEBUG_DIR, f"temp_drill_comp_{productId}.jpg")
    img.save(temp_orig)
    composite_img.save(temp_comp)
    
    attributes = await vision_service.identify_item(temp_orig, temp_comp, x, y)
    
    if not attributes:
        raise HTTPException(status_code=500, detail="Could not identify item")
        
    bbox = attributes.get('bounding_box')
    if bbox and all(k in bbox for k in ['x1', 'y1', 'x2', 'y2']):
        orig_crop = img.crop((bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2']))
        comp_crop = composite_img.crop((bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2']))
    else:
        orig_crop = img
        comp_crop = composite_img
        
    embedding = search_service.get_embedding(orig_crop, comp_crop)
    search_results = await search_service.hybrid_search(embedding, attributes)
    
    results = []
    for res in search_results:
        results.append({
            "product_id": res.id,
            "visual_score": res.score,
            "payload": res.payload
        })
        
    node = {
        "id": str(uuid.uuid4()),
        "productId": productId,
        "x": x,
        "y": y,
        "attributes": attributes,
        "results": results
    }
    drill_history.append(node)
    
    return node

@app.get("/api/history")
async def get_history():
    return drill_history

# Static files for uploads
from fastapi.staticfiles import StaticFiles
app.mount("/uploads", StaticFiles(directory=settings.UPLOADS_DIR), name="uploads")

# Also mount dataset images for the frontend to show product images
app.mount("/dataset", StaticFiles(directory=settings.DATASET_IMAGES_DIR), name="dataset")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
