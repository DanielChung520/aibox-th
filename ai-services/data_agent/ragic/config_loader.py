"""
@file        config_loader.py
@description Multi-tenant configuration loader for Ragic accounts.
             Reads connection settings from system_params (ArangoDB),
             Ragic system management table (ragic-setup/6), or env vars.
@lastUpdate  2026-04-12 01:22:59
@author      Daniel Chung
@version     1.1.0
"""

import logging
import os
import time

from data_agent.config_reader import get_param
from data_agent.ragic.client import RagicAPIClient
from data_agent.ragic.models import RagicConnectionConfig, RagicQueryParams

logger = logging.getLogger(__name__)

_MASTER_ACCOUNT = os.getenv("RAGIC_MASTER_ACCOUNT", "2025shianyong")
_MASTER_API_KEY = os.getenv("RAGIC_MASTER_API_KEY", "")
_MASTER_SERVER = os.getenv("RAGIC_MASTER_SERVER", "ap15")
_CONFIG_TABLE_PATH = "ragic-setup"
_CONFIG_SHEET_INDEX = 6
_CACHE_TTL_SECONDS = 300


class RagicConfigLoader:
    def __init__(
        self,
        master_account: str | None = None,
        master_api_key: str | None = None,
        master_server: str | None = None,
        cache_ttl: int = _CACHE_TTL_SECONDS,
    ) -> None:
        self._master_account = master_account or _MASTER_ACCOUNT
        self._master_api_key = master_api_key or _MASTER_API_KEY
        self._master_server = master_server or _MASTER_SERVER
        self._cache_ttl = cache_ttl
        self._cache: dict[str, RagicConnectionConfig] = {}
        self._cache_ts: float = 0.0
        self._all_loaded: bool = False
        self._db_params_loaded: bool = False

    def _master_client(self) -> RagicAPIClient:
        config = RagicConnectionConfig(
            account=self._master_account,
            api_key=self._master_api_key,
            server_prefix=self._master_server,
        )
        return RagicAPIClient(config)

    def _is_cache_valid(self) -> bool:
        if not self._all_loaded:
            return False
        return (time.monotonic() - self._cache_ts) < self._cache_ttl

    async def _load_from_system_params(self) -> None:
        if self._db_params_loaded:
            return
        self._db_params_loaded = True
        try:
            api_key = await get_param("ragic.api_key")
            if api_key and not self._master_api_key:
                self._master_api_key = api_key
                logger.info("Loaded ragic.api_key from system_params")
            account = await get_param("ragic.database")
            if account and self._master_account == _MASTER_ACCOUNT:
                self._master_account = account
            server = await get_param("ragic.server_prefix")
            if server and self._master_server == _MASTER_SERVER:
                self._master_server = server
        except Exception as exc:
            logger.warning("Failed to load Ragic params from system_params: %s", exc)

    async def get_all_connections(self) -> list[RagicConnectionConfig]:
        if self._is_cache_valid():
            return list(self._cache.values())

        await self._load_from_system_params()

        if not self._master_api_key:
            logger.debug("No master API key, returning env-based fallback only")
            return self._env_fallback_list()

        client = self._master_client()
        params = RagicQueryParams(naming="EID", limit=100)

        try:
            result = await client.get_records(
                tab_path=_CONFIG_TABLE_PATH,
                sheet_index=_CONFIG_SHEET_INDEX,
                params=params,
            )
        except Exception as exc:
            logger.warning("Failed to load config from Ragic: %s", exc)
            return self._env_fallback_list()

        new_cache: dict[str, RagicConnectionConfig] = {}
        for record in result.records:
            conn = self._parse_connection(record.fields)
            if conn and conn.enabled:
                new_cache[conn.account] = conn

        if not new_cache:
            logger.info("No connections found in ragic-setup/6, using env fallback")
            return self._env_fallback_list()

        self._cache = new_cache
        self._cache_ts = time.monotonic()
        self._all_loaded = True
        logger.info("Loaded %d connections from ragic-setup/6", len(new_cache))
        return list(new_cache.values())

    async def get_connection(
        self, account_name: str
    ) -> RagicConnectionConfig | None:
        if account_name in self._cache and self._is_cache_valid():
            return self._cache.get(account_name)

        connections = await self.get_all_connections()
        for conn in connections:
            if conn.account == account_name:
                return conn

        return self._env_fallback(account_name)

    def reload(self) -> None:
        self._cache.clear()
        self._cache_ts = 0.0
        self._all_loaded = False
        logger.info("Config cache cleared")

    @staticmethod
    def _parse_connection(
        fields: dict[str, object],
    ) -> RagicConnectionConfig | None:
        account = str(fields.get("account_name", "")).strip()
        if not account:
            return None

        api_key = str(fields.get("api_key", "")).strip()
        server = str(fields.get("server_prefix", "ap15")).strip() or "ap15"
        enabled_raw = str(fields.get("enabled", "啟用")).strip()
        enabled = enabled_raw in ("啟用", "enabled", "true", "1", "Yes")
        description = str(fields.get("description", "")).strip()

        return RagicConnectionConfig(
            account=account,
            api_key=api_key,
            server_prefix=server,
            enabled=enabled,
            description=description,
        )

    def _env_fallback_list(self) -> list[RagicConnectionConfig]:
        fallback = self._env_fallback(self._master_account)
        if fallback:
            return [fallback]
        return []

    def _env_fallback(self, account: str) -> RagicConnectionConfig | None:
        api_key = os.getenv("RAGIC_API_KEY", "") or self._master_api_key
        if not api_key:
            return None
        server = os.getenv("RAGIC_DEFAULT_SERVER", self._master_server)
        return RagicConnectionConfig(
            account=account,
            api_key=api_key,
            server_prefix=server,
            description="env-fallback",
        )
