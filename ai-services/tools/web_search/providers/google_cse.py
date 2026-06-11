from typing import Any, Dict, Optional

from tools.web_search.providers.base import (
    SearchProvider,
    SearchProviderBase,
    SearchResultItem,
    SearchStatus,
)


class GoogleCSEProvider(SearchProviderBase):
    BASE_URL = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, api_key: str, cx: str, timeout: int = 10) -> None:
        self.api_key = api_key
        self.cx = cx
        self.timeout = timeout
        self.name = "GoogleCSEProvider"

    async def search(
        self, query: str, num: int = 10, location: Optional[str] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        num = min(max(num, 1), 10)
        params: Dict[str, Any] = {
            "key": self.api_key,
            "cx": self.cx,
            "q": query,
            "num": num,
        }
        if location:
            params["cr"] = f"country{location.upper()}"
        response = await self._make_request(self.BASE_URL, method="GET", params=params, timeout=self.timeout)
        if response:
            return self._parse_response(response)
        return {"status": SearchStatus.FAILED, "provider": SearchProvider.GOOGLE_CSE, "results": [], "error": "Request failed"}

    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        results: list[SearchResultItem] = []
        for idx, item in enumerate(response.get("items", []), start=1):
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
            "provider": SearchProvider.GOOGLE_CSE,
            "results": [r.to_dict() for r in results],
            "total": len(results),
        }
