"""Coordinates product identification and vector search for drill-down."""

from fastapi import HTTPException
from PIL import Image

from backend.core.protocols import ProductIdentification, ProductSearch


def format_search_results(search_results) -> list[dict]:
    return [
        {"product_id": res.id, "visual_score": res.score, "payload": res.payload}
        for res in search_results
    ]


def crop_by_bounding_box(
    img: Image.Image, composite_img: Image.Image, bbox: dict | None, *, clamp: bool
):
    if not bbox or not all(k in bbox for k in ["x1", "y1", "x2", "y2"]):
        return img, composite_img

    x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
    if clamp:
        x1, x2 = max(0, min(x1, img.width)), max(0, min(x2, img.width))
        y1, y2 = max(0, min(y1, img.height)), max(0, min(y2, img.height))
        if x2 <= x1 or y2 <= y1:
            return img, composite_img

    return img.crop((x1, y1, x2, y2)), composite_img.crop((x1, y1, x2, y2))


class DrillCoordinator:
    def __init__(
        self,
        product_identification: ProductIdentification,
        product_search: ProductSearch,
    ) -> None:
        self._product_identification = product_identification
        self._product_search = product_search

    async def identify_and_search(
        self,
        img: Image.Image,
        composite_img: Image.Image,
        orig_path: str,
        comp_path: str,
        x: float,
        y: float,
        *,
        clamp_bbox: bool,
    ) -> tuple[dict, list[dict]]:
        attributes = await self._product_identification.identify_item(orig_path, comp_path, x, y)
        if not attributes:
            raise HTTPException(status_code=500, detail="Could not identify item")

        orig_crop, comp_crop = crop_by_bounding_box(
            img, composite_img, attributes.get("bounding_box"), clamp=clamp_bbox
        )
        embedding = self._product_search.get_embedding(orig_crop, comp_crop)
        search_results = await self._product_search.hybrid_search(embedding, attributes)
        return attributes, format_search_results(search_results)
