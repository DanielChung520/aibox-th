from typing import Any, Dict, Optional

from tools.web_search.providers.base import (
    SearchProvider,
    SearchProviderBase,
    SearchResultItem,
    SearchStatus,
)


class SerperProvider(SearchProviderBase):
    BASE_URL = "https://google.serper.dev/search"

    def __init__(self, api_key: str, timeout: int = 10) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.name = "SerperProvider"

    async def search(
        self, query: str, num: int = 10, location: Optional[str] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        num = min(max(num, 1), 100)
        payload: Dict[str, Any] = {"q": query, "num": num}
        if location:
            payload["location"] = location
            payload["gl"] = kwargs.get("gl", "tw")
            payload["hl"] = kwargs.get("hl", "zh-tw")

        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        response = await self._make_request(
            self.BASE_URL, method="POST", json_data=payload, headers=headers, timeout=self.timeout
        )
        if response:
            return self._parse_response(response)
        return {"status": SearchStatus.FAILED, "provider": SearchProvider.SERPER, "results": [], "error": "Request failed"}

    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        results: list[SearchResultItem] = []
        if "answerBox" in response:
            ab = response["answerBox"]
            results.append(
                SearchResultItem(
                    title=ab.get("title", ""),
                    link=ab.get("link", ""),
                    snippet=ab.get("snippet", ""),
                    result_type="answer_box",
                    position=0,
                )
            )
        for idx, item in enumerate(response.get("organic", []), start=1):
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
            "provider": SearchProvider.SERPER,
            "results": [r.to_dict() for r in results],
            "total": len(results),
        }
