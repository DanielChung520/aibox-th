from typing import Any, Dict, Optional
from urllib.parse import quote

from tools.web_search.providers.base import SearchProvider, SearchProviderBase, SearchStatus


class ScraperProvider(SearchProviderBase):
    BASE_URL = "http://api.scraperapi.com"

    def __init__(self, api_key: str, timeout: int = 15) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.name = "ScraperProvider"

    async def search(
        self, query: str, num: int = 10, location: Optional[str] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        google_url = f"https://www.google.com/search?q={quote(query)}&num={num}"
        if location:
            google_url += f"&gl={location}"
        params = {"api_key": self.api_key, "url": google_url}
        response = await self._make_request(self.BASE_URL, method="GET", params=params, timeout=self.timeout)
        if response:
            return self._parse_response(response)
        return {"status": SearchStatus.FAILED, "provider": SearchProvider.SCRAPER, "results": [], "error": "Request failed"}

    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": SearchStatus.SUCCESS, "provider": SearchProvider.SCRAPER, "results": [], "total": 0}
