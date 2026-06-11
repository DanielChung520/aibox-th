from enum import Enum
from typing import List, Optional

from tools.base import BaseTool, ToolInput, ToolOutput
from tools.utils.cache import generate_cache_key, get_cache
from tools.utils.errors import ToolValidationError
from tools.utils.validator import validate_non_empty_string
from tools.web_search.search_service import WebSearchService

WEB_SEARCH_CACHE_TTL = 1800.0


class SearchResult(ToolOutput):
    title: str
    link: str
    snippet: str
    result_type: str = "organic"
    position: Optional[int] = None


class WebSearchInput(ToolInput):
    query: str
    num: int = 10
    location: Optional[str] = None


class WebSearchOutput(ToolOutput):
    query: str
    provider: str
    results: List[SearchResult]
    total: int
    status: str


class WebSearchTool(BaseTool[WebSearchInput, WebSearchOutput]):
    def __init__(self, search_service: Optional[WebSearchService] = None) -> None:
        self._search_service = search_service

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Execute web search with automatic provider fallback (Serper -> SerpAPI -> ScraperAPI -> Google CSE)"

    async def execute(self, input_data: WebSearchInput) -> WebSearchOutput:
        validate_non_empty_string(input_data.query, "query")
        if input_data.num < 1 or input_data.num > 100:
            raise ToolValidationError("num must be between 1 and 100", field="num")

        if self._search_service is None:
            self._search_service = WebSearchService()
        cache_key = generate_cache_key(
            "web_search", query=input_data.query, num=input_data.num, location=input_data.location or ""
        )
        cache = get_cache()
        cached = cache.get(cache_key)
        if cached:
            return WebSearchOutput(**cached)

        result = await self._search_service.search(
            query=input_data.query, num=input_data.num, location=input_data.location
        )

        results = [
            SearchResult(
                title=item.get("title", ""),
                link=item.get("link", ""),
                snippet=item.get("snippet", ""),
                result_type=item.get("type", "organic"),
                position=item.get("position"),
            )
            for item in result.get("results", [])
        ]

        provider = result.get("provider")
        provider_str = getattr(provider, "value", None) if isinstance(provider, Enum) else str(provider) if provider else "unknown"
        status = result.get("status")
        status_str = getattr(status, "value", None) if isinstance(status, Enum) else str(status) if status else "unknown"

        output = WebSearchOutput(
            query=input_data.query,
            provider=provider_str or "unknown",
            results=results,
            total=result.get("total", 0),
            status=status_str or "unknown",
        )
        cache.set(cache_key, output.model_dump(), ttl=WEB_SEARCH_CACHE_TTL)
        return output
