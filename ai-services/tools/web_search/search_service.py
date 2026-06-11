from typing import Any, Dict, List, Optional

import httpx

from tools.web_search.providers.base import SearchStatus
from tools.web_search.providers.google_cse import GoogleCSEProvider
from tools.web_search.providers.scraper import ScraperProvider
from tools.web_search.providers.serpapi import SerpAPIProvider
from tools.web_search.providers.serper import SerperProvider

WEB_SEARCH_CONFIG_URL = "http://localhost:6500/api/v1/web-search/config"


class WebSearchService:
    def __init__(self, config: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        if config is None:
            config = self._load_config_from_rust()
        self.providers: List[Any] = []
        self._init_providers(config)
        if not self.providers:
            raise RuntimeError("No web search providers available")

    def _load_config_from_rust(self) -> Dict[str, Dict[str, Any]]:
        try:
            resp = httpx.get(WEB_SEARCH_CONFIG_URL, timeout=5.0)
            resp.raise_for_status()
            json_resp = resp.json()
            data = json_resp.get("data", {})
            cfg: Dict[str, Dict[str, Any]] = {}
            for key in ("serper", "serpapi", "scraper", "google_cse"):
                enabled = data.get(f"{key}_enabled", False)
                api_key = data.get(f"{key}_api_key", "")
                if enabled and api_key:
                    entry: Dict[str, Any] = {"enabled": True, "api_key": api_key}
                    if key == "google_cse":
                        entry["cx"] = data.get("google_cse_cx", "")
                        if not entry["cx"]:
                            continue
                    cfg[key] = entry
            return cfg
        except Exception:
            return {}

    def _init_providers(self, config: Dict[str, Dict[str, Any]]) -> None:
        priority = [
            ("serper", SerperProvider),
            ("serpapi", SerpAPIProvider),
            ("scraper", ScraperProvider),
            ("google_cse", GoogleCSEProvider),
        ]
        for name, provider_class in priority:
            if name in config and config[name].get("enabled", False):
                try:
                    if name == "google_cse":
                        provider = provider_class(
                            api_key=config[name]["api_key"], cx=config[name]["cx"]
                        )
                    else:
                        provider = provider_class(api_key=config[name]["api_key"])
                    self.providers.append(provider)
                except Exception:
                    pass

    async def search(
        self, query: str, num: int = 10, location: Optional[str] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        for provider in self.providers:
            try:
                result = await provider.search(query, num=num, location=location, **kwargs)
                if result.get("status") == SearchStatus.SUCCESS:
                    return result
            except Exception:
                pass
        return {"status": SearchStatus.FAILED, "provider": None, "results": [], "error": "All providers failed"}

    def get_available_providers(self) -> List[str]:
        return [p.name for p in self.providers]
