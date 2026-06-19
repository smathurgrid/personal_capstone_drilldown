import asyncio
import io
import os
import hashlib
from typing import List, Dict, Any
import numpy as np
from PIL import Image
import httpx
from ..core.config import settings
from ..core.cache import cache

class SearchService:
    def __init__(self):
        self.fclip = None

    def _ensure_fclip(self):
        if self.fclip is None:
            os.makedirs(os.path.join(settings.DEBUG_DIR, "matplotlib"), exist_ok=True)
            os.environ.setdefault("MPLCONFIGDIR", os.path.join(settings.DEBUG_DIR, "matplotlib"))
            print("Initializing FashionCLIP for visual reranking...")
            from fashion_clip.fashion_clip import FashionCLIP

            self.fclip = FashionCLIP('fashion-clip')
        return self.fclip

    async def _download_image(self, url: str) -> Image.Image:
        """Asynchronously downloads an image from a URL."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=5.0)
                response.raise_for_status()
                return Image.open(io.BytesIO(response.content)).convert("RGB")
            except Exception as e:
                print(f"Failed to download image from {url}: {e}")
                return None

    def _get_embedding_sync(self, img_path: str) -> np.ndarray:
        """Synchronous wrapper for FashionCLIP encoding."""
        return self._ensure_fclip().encode_images([img_path], batch_size=1)[0]

    async def _get_embedding(self, image: Image.Image, cache_key_prefix: str) -> np.ndarray:
        """Gets embedding with caching."""
        # Create a deterministic hash for the image or use prefix if it's a URL
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        img_bytes = buffered.getvalue()
        img_hash = hashlib.md5(img_bytes).hexdigest()
        
        cache_key = f"fclip:{cache_key_prefix}:{img_hash}"
        cached_vector = await cache.get(cache_key)
        
        if cached_vector:
            return np.array(cached_vector)

        # Save temporarily for FashionCLIP (it prefers paths)
        temp_path = os.path.join(settings.DEBUG_DIR, f"temp_{img_hash}.jpg")
        image.save(temp_path)
        
        try:
            # Run the synchronous FashionCLIP encoding in a thread pool
            vector = await asyncio.to_thread(self._get_embedding_sync, temp_path)
            await cache.set(cache_key, vector.tolist(), expire_seconds=86400 * 7) # Cache for 7 days
            return vector
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    async def rerank_products(self, garment_crop_path: str, products: List[Dict[str, Any]], target_attributes: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Reranks products based on 0.7 visual similarity + 0.3 semantic similarity.
        """
        if not products:
            return []

        print(f"Reranking {len(products)} products...")
        
        # 1. Get embedding for the target garment
        target_img = Image.open(garment_crop_path).convert("RGB")
        target_vector = await self._get_embedding(target_img, "target")

        # 2. Download product images concurrently
        download_tasks = [self._download_image(p.get("image_url", "")) for p in products]
        product_images = await asyncio.gather(*download_tasks)
        print(f"Downloaded product images: {sum(1 for img in product_images if img)} / {len(products)}")

        # 3. Compute similarities
        valid_products = []
        for product, p_img in zip(products, product_images):
            if not p_img:
                continue

            try:
                p_vector = await self._get_embedding(p_img, f"product_{product['id']}")
            except Exception as e:
                print(f"Skipping product '{product.get('title', '')}': embedding failed — {e}")
                continue

            # Compute cosine similarity
            denom = np.linalg.norm(target_vector) * np.linalg.norm(p_vector)
            visual_sim = float(np.dot(target_vector, p_vector) / denom) if denom > 0 else 0.0

            # Compute semantic score (basic keyword matching against title/retailer)
            semantic_score = 0.0
            searchable_text = f"{product.get('title', '')} {product.get('retailer', '')}".lower()

            if target_attributes.get('color', '').lower() in searchable_text:
                semantic_score += 0.3
            if target_attributes.get('material', '').lower() in searchable_text:
                semantic_score += 0.3
            if target_attributes.get('category', '').lower() in searchable_text:
                semantic_score += 0.4

            final_score = (0.7 * max(0, visual_sim)) + (0.3 * semantic_score)

            product["visual_match_pct"] = round(final_score * 100)
            product["visual_similarity"] = round(max(0, visual_sim), 4)
            product["semantic_similarity"] = round(semantic_score, 4)
            product["final_score"] = round(final_score, 4)
            valid_products.append(product)
            print(
                f"Rank score | {product.get('title', '')[:80]} | "
                f"visual={product['visual_similarity']} semantic={product['semantic_similarity']} "
                f"final={product['final_score']}"
            )

        # 4. Sort by final score descending
        valid_products.sort(key=lambda x: x["visual_match_pct"], reverse=True)
        print(f"Reranking complete. Top match score: {valid_products[0]['visual_match_pct'] if valid_products else 0}%")
        return valid_products

search_service = SearchService()
