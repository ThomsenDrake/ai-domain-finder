import httpx
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class SearXNGClient:
    def __init__(self, base_url: str = "https://searx.be"):
        self.base_url = base_url
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.fallback_instances = [
            "https://searx.org",
            "https://searx.space"
        ]
    
    async def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Search using SearXNG instance with fallback support"""
        logger.info(f"Searching SearXNG for: {query}")
        
        try:
            return await self._perform_search(query, limit)
        except Exception as e:
            logger.warning(f"Primary SearXNG instance failed: {e}")
            
            # Try fallback instances
            for fallback_url in self.fallback_instances:
                try:
                    logger.info(f"Trying fallback instance: {fallback_url}")
                    original_url = self.base_url
                    self.base_url = fallback_url
                    result = await self._perform_search(query, limit)
                    self.base_url = original_url  # Restore original
                    return result
                except Exception as fallback_error:
                    logger.warning(f"Fallback instance {fallback_url} failed: {fallback_error}")
                    continue
            
            logger.error("All SearXNG instances failed")
            return []
    
    async def _perform_search(self, query: str, limit: int) -> List[Dict]:
        """Perform the actual search request"""
        params = {
            'q': query,
            'format': 'json',
            'engines': 'google,bing,duckduckgo',
            'language': 'en',
            'time_range': '',
            'safesearch': '0',
            'pageno': '1'
        }
        
        headers = {
            'User-Agent': 'Domain-Enrichment-Tool/1.0'
        }
        
        logger.debug(f"Making request to {self.base_url}/search with params: {params}")
        
        response = await self.http_client.get(
            f"{self.base_url}/search",
            params=params,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])[:limit]
            logger.debug(f"Got {len(results)} search results")
            return results
        else:
            logger.error(f"SearXNG returned status {response.status_code}: {response.text}")
            raise Exception(f"SearXNG API returned status {response.status_code}")
    
    async def close(self):
        """Close the HTTP client"""
        await self.http_client.aclose()