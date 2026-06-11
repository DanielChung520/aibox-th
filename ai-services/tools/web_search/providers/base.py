from enum import Enum
from typing import Any, Dict, Optional

import httpx


class SearchProvider(Enum):
    SERPER = "serper"
    SERPAPI = "serpapi"
    SCRAPER = "scraper"
    GOOGLE_CSE = "google_cse"


class SearchStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    QUOTA_EXCEEDED = "quota_exceeded"
    TIMEOUT = "timeout"
    INVALID_API_KEY = "invalid_api_key"


class SearchResultItem:
    def __init__(
        self,
        title: str,
        link: str,
        snippet: str,
        result_type: str = "organic",
        position: Optional[int] = None,
    ) -> None:
        self.title = title
        self.link = link
        self.snippet = snippet
        self.result_type = result_type
        self.position = position

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "link": self.link,
            "snippet": self.snippet,
            "type": self.result_type,
            "position": self.position,
        }


class SearchProviderBase:
    async def search(
        self, query: str, num: int = 10, location: Optional[str] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    async def _make_request(
        self,
        url: str,
        method: str = "GET",
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: int = 10,
    ) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method.upper() == "POST":
                    resp = await client.post(url, json=json_data, headers=headers)
                else:
                    resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException:
            return None
        except httpx.HTTPStatusError:
            return None
        except Exception:
            return None
