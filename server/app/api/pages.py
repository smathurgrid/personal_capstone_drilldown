from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import os
import hashlib
from app.services.page_service import PageService
from app.services.ai_service import AIService
from app.services.document_service import DocumentService

router = APIRouter()
page_service = PageService()
STATIC_DIR = "static"

class PageRequest(BaseModel):
    query: Optional[str] = None
    parentId: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    customTopic: Optional[str] = None
    visionModel: Optional[str] = "qwen3.5"
    groundingMode: Optional[str] = "sam2" # Default to SAM2 Segmentation Workflow
    drillMode: Optional[str] = "inside" # Choose 'inside' (Drill Down) or 'pov' (Point of View)

class AnalyzeRequest(BaseModel):
    pageId: str
    visionModel: Optional[str] = "qwen3.5"

@router.post("/stream-page")
async def stream_page(req: PageRequest):
    if req.x is not None and (req.x < 0.0 or req.x > 1.0 or req.y < 0.0 or req.y > 1.0):
        raise HTTPException(status_code=400, detail="Click coordinates x and y must be within [0.0, 1.0]")
    return StreamingResponse(
        page_service.stream_page(
            query=req.query,
            parent_id=req.parentId,
            x=req.x,
            y=req.y,
            vision_model=req.visionModel,
            grounding_mode=req.groundingMode,
            custom_topic=req.customTopic,
            drill_mode=req.drillMode
        ),
        media_type="text/event-stream"
    )

@router.post("/analyze")
async def analyze_page(req: AnalyzeRequest):
    try:
        image_path = os.path.join(STATIC_DIR, f"{req.pageId}.png")
        if not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail="Image not found")
        
        analysis = await AIService.auto_analyze(image_path, model_key=req.visionModel)
        return analysis
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/page")
async def get_page(req: PageRequest):
    try:
        print(f"Requesting page: {req}")
        if req.x is not None and (req.x < 0.0 or req.x > 1.0 or req.y < 0.0 or req.y > 1.0):
            raise HTTPException(status_code=400, detail="Click coordinates x and y must be within [0.0, 1.0]")
        result = await page_service.get_or_create_page(
            query=req.query,
            parent_id=req.parentId,
            x=req.x,
            y=req.y,
            vision_model=req.visionModel,
            grounding_mode=req.groundingMode,
            drill_mode=req.drillMode
        )
        # Result now includes 'id', 'imageUrl', and we'll add 'confidence'
        return result
    except Exception as e:
        import traceback
        print(f"CRITICAL ERROR in /page: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed.")
    
    allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Unsupported image type: {file.content_type}. Supported: PNG, JPEG, WEBP.")

    try:
        # Read file content to create hash
        content = await file.read()
        
        MAX_SIZE = 10 * 1024 * 1024 # 10MB
        if len(content) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="File too large. Max size allowed is 10MB.")

        page_id = hashlib.sha256(content).hexdigest()
        
        # Save to static directory
        file_path = os.path.join(STATIC_DIR, f"{page_id}.png")
        
        # Always save as PNG for consistency with compositor
        from PIL import Image
        import io
        
        image = Image.open(io.BytesIO(content))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(file_path, "PNG")
        
        # Generate corresponding depth map for the uploaded image
        from app.services.depth_service import DepthService
        depth_path = os.path.join(STATIC_DIR, f"{page_id}_depth.png")
        await DepthService.generate_depth_map(file_path, depth_path)
        
        return {
            "id": page_id, 
            "imageUrl": f"/static/{page_id}.png", 
            "depthUrl": f"/static/{page_id}_depth.png", 
            "metadata": {}, 
            "rawJson": "", 
            "inputPrompt": "", 
            "samConfidence": None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    try:
        content = await file.read()
        metadata = await DocumentService.process_pdf(file.filename, content)
        return metadata
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/document/{document_id}")
async def get_document(document_id: str):
    try:
        return DocumentService.get_document(document_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
