from typing import List, Dict, Any

class BaseProvider:
    """Base interface for all shopping providers."""
    
    @property
    def source_name(self) -> str:
        """The display name of the provider."""
        raise NotImplementedError

    @property
    def is_configured(self) -> bool:
        """Whether this provider is enabled by current application configuration."""
        return False

    @property
    def is_enabled(self) -> bool:
        """Whether this provider has enough credentials to run."""
        return False
        
    async def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Executes a search query and returns a standardized list of products.
        Standard format required:
        [
            {
                "id": str,
                "title": str,
                "price": str,
                "retailer": str,
                "image_url": str,
                "product_url": str,
                "source": self.source_name
            }
        ]
        """
        raise NotImplementedError
