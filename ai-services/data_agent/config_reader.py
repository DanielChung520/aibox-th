"""
Data Agent Config Reader — ArangoDB system_params with cache + env fallback.

# Last Update: 2026-04-16 17:50:29
# Author: Daniel Chung
# Version: 1.1.0
"""

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

_GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:6500")
_CACHE_TTL = int(os.getenv("DA_CONFIG_CACHE_TTL", "300"))
_cache: dict[str, tuple[str, float]] = {}

DA_PARAM_KEYS = {
    "embedding_model": "da.embedding_model",
    "embedding_dimension": "da.embedding_dimension",
    "small_llm_model": "da.small_llm_model",
    "large_llm_model": "da.large_llm_model",
    "data_source": "da.data_source",
}

_ENV_FALLBACKS: dict[str, tuple[str, str]] = {
    "da.embedding_model": ("EMBEDDING_MODEL", "bge-m3:latest"),
    "da.embedding_dimension": ("EMBEDDING_DIM", "1024"),
    "da.small_llm_model": ("NL2SQL_SMALL_MODEL", "mistral-nemo:12b"),
    "da.large_llm_model": ("NL2SQL_LARGE_MODEL", "qwen3-coder:30b"),
    "da.data_source": ("DA_DATA_SOURCE", "sap"),
    "intent.match_threshold": ("MATCH_THRESHOLD", "0.45"),
    "ragic.api_key": ("RAGIC_API_KEY", ""),
    "ragic.database": ("RAGIC_MASTER_ACCOUNT", "2025shianyong"),
    "ragic.server_prefix": ("RAGIC_MASTER_SERVER", "ap15"),
    "da.sql_model": ("DA_SQL_MODEL", "duckdb-nsql:latest"),
    "da.sql_model_provider": ("DA_SQL_MODEL_PROVIDER", "ollama"),
    "da.sql_fallback_model": ("DA_SQL_FALLBACK_MODEL", "sqlcoder:7b"),
    "da.sql_fallback_provider": ("DA_SQL_FALLBACK_PROVIDER", "ollama"),
    "da.sql_temperature": ("DA_SQL_TEMPERATURE", "0.1"),
    "da.sql_max_retries": ("DA_SQL_MAX_RETRIES", "2"),
    "da.query_source": ("DA_QUERY_SOURCE", "server_cache"),
}


def _get_cached(key: str) -> str | None:
    if key in _cache:
        value, ts = _cache[key]
        if time.time() - ts < _CACHE_TTL:
            return value
    return None


def _set_cached(key: str, value: str) -> None:
    _cache[key] = (value, time.time())


async def get_param(param_key: str) -> str:
    """Fetch a single system_param value: cache → Rust API → env var fallback."""
    cached = _get_cached(param_key)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{_GATEWAY_URL}/api/v1/system-params/{param_key}",
            )
            if resp.status_code == 200:
                data = resp.json()
                value = str(data.get("data", {}).get("param_value", ""))
                if value:
                    _set_cached(param_key, value)
                    return value
    except (httpx.HTTPError, Exception) as e:
        logger.warning("Failed to read param %s from API: %s", param_key, e)

    env_key, default = _ENV_FALLBACKS.get(param_key, ("", ""))
    value = os.getenv(env_key, default) if env_key else default
    if value:
        _set_cached(param_key, value)
    return value


async def get_da_config() -> dict[str, str]:
    result: dict[str, str] = {}
    for local_key, param_key in DA_PARAM_KEYS.items():
        result[local_key] = await get_param(param_key)
    return result


def invalidate_cache(param_key: str | None = None) -> None:
    """Clear cached config — single key or all DA keys."""
    if param_key:
        _cache.pop(param_key, None)
    else:
        for pk in DA_PARAM_KEYS.values():
            _cache.pop(pk, None)
