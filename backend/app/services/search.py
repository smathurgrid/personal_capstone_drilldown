from qdrant_client import QdrantClient
from qdrant_client.http import models
from fashion_clip.fashion_clip import FashionCLIP
from ..core.config import settings
import os
import numpy as np

class SearchService:
    def __init__(self):
        self.client = QdrantClient(path=settings.QDRANT_PATH)
        self.fclip = FashionCLIP('fashion-clip')

    def get_embedding(self, original_crop, composite_crop):
        # Save crops temporarily with absolute paths
        orig_path = os.path.join(settings.DEBUG_DIR, "temp_orig_crop.jpg")
        comp_path = os.path.join(settings.DEBUG_DIR, "temp_comp_crop.jpg")
        original_crop.save(orig_path)
        composite_crop.save(comp_path)
        
        # Generate embeddings
        embeddings = self.fclip.encode_images([orig_path, comp_path], batch_size=2)
        
        # Fusion: 0.7 original + 0.3 composite
        fused = 0.7 * embeddings[0] + 0.3 * embeddings[1]
        
        # Cleanup
        os.remove(orig_path)
        os.remove(comp_path)
        
        print(f"Embedding fusion complete. Dimensions: {fused.shape}")
        return fused.tolist()

    async def hybrid_search(self, embedding, attributes: dict, limit: int = 50):
        print(f"SEARCHING with attributes: {attributes}")
        
        # Initial vector search using the new query_points API (v1.11+)
        # query_points replaces the older 'search' method
        search_results = self.client.query_points(
            collection_name=settings.COLLECTION_NAME,
            query=embedding,
            limit=limit,
            with_payload=True
        ).points
        
        final_results = []
        for res in search_results:
            payload = res.payload
            
            # Semantic scoring logic
            semantic_score = 0
            # Match articleType
            if attributes.get('articleType') == payload.get('articleType'):
                semantic_score += 0.4
            # Match color
            if attributes.get('color') == payload.get('baseColour'):
                semantic_score += 0.3
            # Match gender
            if attributes.get('gender') == payload.get('gender'):
                semantic_score += 0.2
            # Match masterCategory (Try both keys for robustness)
            cat = attributes.get('masterCategory') or attributes.get('category')
            if cat == payload.get('masterCategory'):
                semantic_score += 0.1
                
            # Final score: 0.7 visual (Qdrant score) + 0.3 semantic
            visual_score = res.score
            res.score = (0.7 * visual_score) + (0.3 * semantic_score)
            
            final_results.append(res)
            
        # Re-sort based on final score
        final_results.sort(key=lambda x: x.score, reverse=True)
        
        print(f"FOUND {len(final_results)} results")
        if final_results:
            print(f"TOP MATCH: {final_results[0].payload.get('productDisplayName')} (Final Score: {final_results[0].score:.4f})")
            
        return final_results

search_service = SearchService()
