from typing import List, Dict, Any
from .base_provider import BaseProvider
from ...core.config import settings

class EtsyProvider(BaseProvider):
    @property
    def source_name(self) -> str:
        return "Etsy"

    @property
    def is_configured(self) -> bool:
        return settings.SHOPPING_PROVIDERS["etsy"]

    @property
    def is_enabled(self) -> bool:
        return bool(settings.ETSY_API_KEY)

    async def search(self, query: str) -> List[Dict[str, Any]]:
        if not settings.ETSY_API_KEY:
            return []
            
        print(f"Etsy Provider placeholder hit for: {query}")
        # Future implementation here
        return []
