"""
@file        llm_resolver.py
@description Reusable Model ID → provider → base_url + api_key resolution.
             Parses "provider:model" format, looks up llm.providers in system_params
             and model_providers in ArangoDB, constructs the correct API endpoint.
@lastUpdate  2026-05-01 02:45:00
@author      Sisyphus
@version     1.1.0
"""

import json
import logging
import os
import time

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:6500")
_CACHE_TTL = 300
_providers_cache: tuple[dict, float] | None = None
_model_providers_cache: tuple[dict[str, dict], float] | None = None


class ResolvedLLMConfig(BaseModel):
    provider: str
    model_name: str
    endpoint: str
    api_key: str
    base_url: str


def _parse_model_id(model_id: str) -> tuple[str, str]:
    if ":" in model_id:
        provider, model = model_id.split(":", 1)
        return provider.strip(), model.strip()
    return "ollama", model_id.strip()


async def _get_providers() -> dict:
    global _providers_cache
    now = time.time()
    if _providers_cache and (now - _providers_cache[1]) < _CACHE_TTL:
        return _providers_cache[0]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{_GATEWAY_URL}/api/v1/system-params/llm.providers"
            )
            if resp.status_code == 200:
                raw = resp.json().get("data", {}).get("param_value", "{}")
                providers = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(providers, dict) and providers:
                    _providers_cache = (providers, now)
                    return providers
    except Exception as e:
        logger.warning("Failed to fetch llm.providers: %s", e)

    fallback = {"ollama": {"base_url": "http://localhost:11434", "api_key_param": None}}
    _providers_cache = (fallback, now)
    return fallback


async def _get_model_providers() -> dict[str, dict]:
    global _model_providers_cache
    now = time.time()
    if _model_providers_cache and (now - _model_providers_cache[1]) < _CACHE_TTL:
        return _model_providers_cache[0]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{_GATEWAY_URL}/api/v1/model-providers")
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if isinstance(data, list):
                    indexed = {
                        p["code"]: p for p in data if isinstance(p, dict) and p.get("code")
                    }
                    _model_providers_cache = (indexed, now)
                    return indexed
    except Exception as e:
        logger.warning("Failed to fetch model_providers: %s", e)

    _model_providers_cache = ({}, now)
    return {}


def _build_endpoint(base_url: str) -> str:
    if base_url.endswith("/api/chat") or base_url.endswith("/chat/completions"):
        return base_url
    if "/v1" in base_url:
        return f"{base_url.rstrip('/')}/chat/completions"
    return f"{base_url.rstrip('/')}/api/chat"


async def resolve(model_id: str) -> ResolvedLLMConfig:
    provider_name, model_name = _parse_model_id(model_id)
    providers = await _get_providers()

    provider_cfg = providers.get(provider_name)
    if not provider_cfg:
        logger.warning(
            "Provider '%s' not found in llm.providers, falling back to ollama",
            provider_name,
        )
        provider_cfg = providers.get("ollama", {"base_url": "http://localhost:11434"})

    base_url = str(provider_cfg.get("base_url", "http://localhost:11434"))
    api_key_param = provider_cfg.get("api_key_param")

    # Priority 1: model_providers collection (user sets API key in UI)
    api_key = ""
    model_providers = await _get_model_providers()
    mp_cfg = model_providers.get(provider_name)
    if mp_cfg and mp_cfg.get("api_key"):
        api_key = str(mp_cfg["api_key"])

    # Priority 2: system_params referenced by api_key_param
    if not api_key and api_key_param:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{_GATEWAY_URL}/api/v1/system-params/{api_key_param}"
                )
                if resp.status_code == 200:
                    api_key = resp.json().get("data", {}).get("param_value", "")
        except Exception as e:
            logger.warning("Failed to fetch api_key %s: %s", api_key_param, e)

    endpoint = _build_endpoint(base_url)

    return ResolvedLLMConfig(
        provider=provider_name,
        model_name=model_name,
        endpoint=endpoint,
        api_key=api_key,
        base_url=base_url,
    )


def invalidate_cache() -> None:
    global _providers_cache, _model_providers_cache
    _providers_cache = None
    _model_providers_cache = None
