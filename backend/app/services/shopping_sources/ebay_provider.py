from typing import List, Dict, Any
from .base_provider import BaseProvider
from ...core.config import settings

class EbayProvider(BaseProvider):
    @property
    def source_name(self) -> str:
        return "eBay"

    @property
    def is_configured(self) -> bool:
        return settings.SHOPPING_PROVIDERS["ebay"]

    @property
    def is_enabled(self) -> bool:
        return bool(settings.EBAY_API_KEY)

    async def search(self, query: str) -> List[Dict[str, Any]]:
        if not settings.EBAY_API_KEY:
            return []
            
        print(f"eBay Provider placeholder hit for: {query}")
        # Future implementation here
        return []
