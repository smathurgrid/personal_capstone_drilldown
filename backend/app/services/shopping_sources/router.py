import asyncio
from typing import List, Dict, Any
from .serp_provider import SerpApiProvider
from .ebay_provider import EbayProvider
from .etsy_provider import EtsyProvider

class ShoppingRouter:
    def __init__(self):
        self.provider_map = {
            "serpapi": SerpApiProvider(),
            "ebay": EbayProvider(),
            "etsy": EtsyProvider(),
        }

    async def route_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Routes the search query to all active providers concurrently
        and aggregates the standardized results.
        """
        print(f"\n--- ROUTING SHOPPING QUERY: '{query}' ---")
        
        active_providers = [
            provider
            for key, provider in self.provider_map.items()
            if provider.is_configured and provider.is_enabled
        ]
        print(f"Active shopping providers: {[p.source_name for p in active_providers]}")

        # Run all provider searches concurrently
        tasks = [provider.search(query) for provider in active_providers]
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)
        
        aggregated_results = []
        for result in results_lists:
            if isinstance(result, list):
                aggregated_results.extend(result)
            elif isinstance(result, Exception):
                print(f"Provider failed with exception: {result}")
                
        print(f"--- AGGREGATED {len(aggregated_results)} RESULTS ---")
        return aggregated_results

shopping_router = ShoppingRouter()
