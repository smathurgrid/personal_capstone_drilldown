"""Vector and semantic product search for ecommerce drill-down."""

import os

from backend.shared.config import Settings


class SearchService:
    def __init__(self, app_settings: Settings) -> None:
        from qdrant_client import QdrantClient
        from fashion_clip.fashion_clip import FashionCLIP

        self._settings = app_settings
        self.client = QdrantClient(path=str(app_settings.QDRANT_PATH))
        self.fclip = FashionCLIP("fashion-clip")

    def get_embedding(self, original_crop, composite_crop):
        orig_path = os.path.join(self._settings.DEBUG_DIR, "temp_orig_crop.jpg")
        comp_path = os.path.join(self._settings.DEBUG_DIR, "temp_comp_crop.jpg")
        original_crop.save(orig_path)
        composite_crop.save(comp_path)
        embeddings = self.fclip.encode_images([orig_path, comp_path], batch_size=2)
        fused = 0.7 * embeddings[0] + 0.3 * embeddings[1]
        os.remove(orig_path)
        os.remove(comp_path)
        return fused.tolist()

    async def hybrid_search(self, embedding, attributes: dict, limit: int = 50):
        search_results = self.client.query_points(
            collection_name=self._settings.COLLECTION_NAME,
            query=embedding,
            limit=limit,
            with_payload=True,
        ).points

        final_results = []
        for res in search_results:
            payload = res.payload
            semantic_score = 0
            if attributes.get("articleType") == payload.get("articleType"):
                semantic_score += 0.4
            if attributes.get("color") == payload.get("baseColour"):
                semantic_score += 0.3
            if attributes.get("gender") == payload.get("gender"):
                semantic_score += 0.2
            cat = attributes.get("masterCategory") or attributes.get("category")
            if cat == payload.get("masterCategory"):
                semantic_score += 0.1
            res.score = (0.7 * res.score) + (0.3 * semantic_score)
            final_results.append(res)

        final_results.sort(key=lambda x: x.score, reverse=True)
        return final_results
