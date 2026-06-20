"""Ecommerce catalog drill-down business logic."""

import hashlib
import os
import uuid

from fastapi import HTTPException, UploadFile
from PIL import Image

from backend.core.protocols import DrillHistoryStore
from backend.services.ecommerce.click_marker import draw_click_marker
from backend.services.ecommerce.drill_coordinator import DrillCoordinator
from backend.shared.config import settings


class EcommerceCatalogService:
    def __init__(
        self,
        drill_coordinator: DrillCoordinator,
        drill_history: DrillHistoryStore,
    ) -> None:
        self._drill_coordinator = drill_coordinator
        self._drill_history = drill_history

    async def upload_image(self, file: UploadFile) -> dict:
        image_id = str(uuid.uuid4())
        content = await file.read()
        image_hash = hashlib.md5(content).hexdigest()
        file_ext = os.path.splitext(file.filename or "")[1] or ".jpg"
        image_filename = f"{image_id}{file_ext}"
        image_path = settings.UPLOADS_DIR / image_filename
        with open(image_path, "wb") as handle:
            handle.write(content)
        return {
            "imageId": image_id,
            "imageHash": image_hash,
            "imageUrl": f"/uploads/{image_filename}",
        }

    async def identify_item(self, image_id: str, x: float, y: float) -> dict:
        image_filename = None
        for filename in os.listdir(settings.UPLOADS_DIR):
            if filename.startswith(image_id):
                image_filename = filename
                break
        if not image_filename:
            raise HTTPException(status_code=404, detail="Image not found")

        original_path = settings.UPLOADS_DIR / image_filename
        img = Image.open(original_path).convert("RGB")
        composite_img = draw_click_marker(img.copy(), x, y)
        composite_path = settings.DEBUG_DIR / f"comp_{image_filename}"
        composite_img.save(composite_path)
        img.save(settings.DEBUG_DIR / f"orig_{image_filename}")

        attributes, results = await self._drill_coordinator.identify_and_search(
            img,
            composite_img,
            str(original_path),
            str(composite_path),
            x,
            y,
            clamp_bbox=True,
        )

        node = {
            "id": str(uuid.uuid4()),
            "imageId": image_id,
            "x": x,
            "y": y,
            "canvasImageUrl": f"/uploads/{image_filename}",
            "attributes": attributes,
            "results": results,
        }
        self._drill_history.append(node)
        return node

    async def drill_down(self, product_id: int, x: float, y: float) -> dict:
        image_path = settings.DATASET_IMAGES_DIR / f"{product_id}.jpg"
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Product image not found")

        img = Image.open(image_path).convert("RGB")
        composite_img = draw_click_marker(img.copy(), x, y)
        temp_orig = settings.DEBUG_DIR / f"temp_drill_orig_{product_id}.jpg"
        temp_comp = settings.DEBUG_DIR / f"temp_drill_comp_{product_id}.jpg"
        img.save(temp_orig)
        composite_img.save(temp_comp)

        attributes, results = await self._drill_coordinator.identify_and_search(
            img,
            composite_img,
            str(temp_orig),
            str(temp_comp),
            x,
            y,
            clamp_bbox=False,
        )

        node = {
            "id": str(uuid.uuid4()),
            "productId": product_id,
            "x": x,
            "y": y,
            "canvasImageUrl": f"/dataset/{product_id}.jpg",
            "attributes": attributes,
            "results": results,
        }
        self._drill_history.append(node)
        return node

    def get_history(self) -> list:
        return self._drill_history.list_all()
