from typing import Any, Dict, Optional

from tools.web_search.providers.base import (
    SearchProvider,
    SearchProviderBase,
    SearchResultItem,
    SearchStatus,
)


class SerpAPIProvider(SearchProviderBase):
    BASE_URL = "https://serpapi.com/search"

    def __init__(self, api_key: str, timeout: int = 10) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.name = "SerpAPIProvider"

    async def search(
        self, query: str, num: int = 10, location: Optional[str] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        num = min(max(num, 1), 100)
        params: Dict[str, Any] = {
            "q": query,
            "num": num,
            "api_key": self.api_key,
            "engine": "google",
        }
        if location:
            params["location"] = location
        response = await self._make_request(self.BASE_URL, method="GET", params=params, timeout=self.timeout)
        if response:
            return self._parse_response(response)
        return {"status": SearchStatus.FAILED, "provider": SearchProvider.SERPAPI, "results": [], "error": "Request failed"}

    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        results: list[SearchResultItem] = []
        if "answer_box" in response:
            ab = response["answer_box"]
            results.append(
                SearchResultItem(
                    title=ab.get("title", ""),
                    link=ab.get("link", ""),
                    snippet=ab.get("snippet", ab.get("answer", "")),
                    result_type="answer_box",
                    position=0,
                )
            )
        for idx, item in enumerate(response.get("organic_results", []), start=1):
            results.append(
                SearchResultItem(
                    title=item.get("title", ""),
                    link=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    result_type="organic",
                    position=idx,
                )
            )
        return {
            "status": SearchStatus.SUCCESS,
            "provider": SearchProvider.SERPAPI,
            "results": [r.to_dict() for r in results],
            "total": len(results),
        }
