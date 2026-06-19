import asyncio
from typing import List, Dict, Any
from serpapi import GoogleSearch
from .base_provider import BaseProvider
from ...core.config import settings
from ...core.cache import cache

class SerpApiProvider(BaseProvider):
    @property
    def source_name(self) -> str:
        return "Google Shopping"

    @property
    def is_configured(self) -> bool:
        return settings.SHOPPING_PROVIDERS["serpapi"]

    @property
    def is_enabled(self) -> bool:
        return bool(settings.SERPAPI_KEY)

    async def search(self, query: str) -> List[Dict[str, Any]]:
        if not settings.SERPAPI_KEY:
            print("SerpApi Key not found. Skipping.")
            return []

        cache_key = f"serpapi:{query}"
        cached_results = await cache.get(cache_key)
        if cached_results:
            print(f"SerpApi cache hit for: {query}")
            return cached_results

        print(f"SerpApi searching for: {query}")
        params = {
            "engine": "google_shopping",
            "q": query,
            "hl": "en",
            "gl": "us",
            "api_key": settings.SERPAPI_KEY
        }

        try:
            # SerpApi is synchronous, so we run it in a thread pool
            search = GoogleSearch(params)
            results = await asyncio.to_thread(search.get_dict)
            shopping_results = results.get("shopping_results", [])
            print(f"SerpApi result count: {len(shopping_results)}")
            
            if shopping_results:
                print(f"SerpApi first result keys: {list(shopping_results[0].keys())}")

            standardized_results = []
            for item in shopping_results[:30]:  # Limit to top 30
                title = item.get("title") or ""
                if not title:
                    continue

                # Product URL — try multiple field names
                link = (
                    item.get("link")
                    or item.get("product_link")
                    or item.get("url")
                    or ""
                )
                if not link:
                    continue

                # Image — try multiple field names; not strictly required
                image_url = (
                    item.get("thumbnail")
                    or item.get("image")
                    or item.get("product_image")
                    or ""
                )

                item_id = item.get("product_id") or str(hash(link))

                extensions = item.get("extensions") or []
                description = item.get("snippet") or (extensions[0] if extensions else "")

                standardized_results.append({
                    "id": item_id,
                    "title": title,
                    "price": item.get("price", "Check site"),
                    "retailer": item.get("source", "Unknown"),
                    "image_url": image_url,
                    "product_url": link,
                    "description": description,
                    "source": self.source_name
                })
                
            await cache.set(cache_key, standardized_results, expire_seconds=86400) # Cache for 24h
            return standardized_results
            
        except Exception as e:
            print(f"SerpApi search error: {e}")
            return []
