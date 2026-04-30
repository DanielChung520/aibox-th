"""
@file        Ragic Cache
@description Ragic 資料通用快取讀寫 — 支援全部 263 張 Ragic 表格
             單一集合（ragic_cache），以 table_id 區分
@lastUpdate  2026-04-30 01:45:00
@author      Daniel Chung
@version     1.1.0
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ARANGO_URL = "http://localhost:8529"
ARANGO_DB = "abc_desktop"
ARANGO_USER = "root"
ARANGO_PASSWORD = "abc_desktop_2026"
RUST_API = "http://localhost:6500"
DEFAULT_TTL_SECONDS = 3600
CACHE_COLLECTION = "ragic_cache"


def _auth_header() -> dict[str, str]:
    cred = f"{ARANGO_USER}:{ARANGO_PASSWORD}"
    return {
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(cred.encode()).decode()}",
    }


async def _arango_query(aql: str, bind_vars: dict | None = None) -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": aql, "bindVars": bind_vars or {}},
            headers=_auth_header(),
        )
        if resp.status_code not in (200, 201):
            return []
        return resp.json().get("result", [])


async def _get_ttl() -> int:
    rows = await _arango_query(
        "FOR p IN system_params FILTER p.param_key == 'ragic.cache.ttl_seconds' LIMIT 1 RETURN p.param_value"
    )
    if rows:
        val = rows[0]
        if isinstance(val, str):
            return int(val)
    return DEFAULT_TTL_SECONDS


class RagicCache:
    _locks: dict[str, asyncio.Lock] = {}

    async def read(self, table_id: str) -> dict[str, Any] | None:
        """讀取快取，TTL 內直接回傳，過期或不存在回 None"""
        rows = await _arango_query(
            "FOR c IN ragic_cache FILTER c._key == @key LIMIT 1 RETURN c",
            {"key": table_id},
        )
        if not rows:
            return None
        doc = rows[0]
        cached_at = doc.get("cached_at", 0)
        ttl = await _get_ttl()
        if time.time() - cached_at > ttl:
            return None
        return doc

    async def is_fresh(self, table_id: str) -> bool:
        """檢查快取是否在 TTL 內"""
        rows = await _arango_query(
            "FOR c IN ragic_cache FILTER c._key == @key LIMIT 1 RETURN c.cached_at",
            {"key": table_id},
        )
        if not rows:
            return False
        raw = rows[0]
        if isinstance(raw, str):
            try:
                ts = datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
            except (ValueError, OSError):
                return False
        elif isinstance(raw, (int, float)):
            ts = float(raw)
        else:
            return False
        return (time.time() - ts) <= await _get_ttl()

    async def write(
        self,
        table_id: str,
        rows: list[dict[str, Any]],
        field_mapping: dict[str, str],
        table_name_cn: str = "",
    ) -> bool:
        """寫入快取（UPSERT）

        Args:
            table_id: Ragic 表格 ID（如 STOCK_16）
            rows: Ragic 原始資料列（欄位 ID 作為 key）
            field_mapping: 欄位 ID → 人類可讀名稱對應
            table_name_cn: 表格中文名稱（可選）
        """
        mapped_rows = []
        for i, raw_row in enumerate(rows):
            if not isinstance(raw_row, dict):
                continue
            mapped: dict[str, Any] = {"_key": f"{table_id}-{i:05d}", "_raw": raw_row}
            for field_id, value in raw_row.items():
                human_name = field_mapping.get(str(field_id), field_id)
                mapped[human_name] = value
            mapped_rows.append(mapped)

        now_iso = datetime.now(timezone.utc).isoformat()
        now_ts = time.time()
        ttl = await _get_ttl()

        upsert_aql = """
        UPSERT { _key: @key }
        INSERT {
            _key: @key,
            table_id: @table_id,
            table_name_cn: @table_name_cn,
            row_count: @row_count,
            field_mapping: @field_mapping,
            rows: @rows,
            cached_at: @ts,
            updated_at: @ts_str,
            ttl_seconds: @ttl
        }
        UPDATE {
            table_name_cn: @table_name_cn,
            row_count: @row_count,
            field_mapping: @field_mapping,
            rows: @rows,
            cached_at: @ts,
            updated_at: @ts_str,
            ttl_seconds: @ttl
        }
        IN ragic_cache
        """
        await _arango_query(upsert_aql, {
            "key": table_id,
            "table_id": table_id,
            "table_name_cn": table_name_cn,
            "row_count": len(mapped_rows),
            "field_mapping": field_mapping,
            "rows": mapped_rows,
            "ts": now_ts,
            "ts_str": now_iso,
            "ttl": ttl,
        })
        logger.info(f"[RagicCache] Written {len(mapped_rows)} rows for {table_id}")
        return True

    async def delete(self, table_id: str) -> bool:
        """刪除快取"""
        await _arango_query(
            "REMOVE { _key: @key } IN ragic_cache",
            {"key": table_id},
        )
        logger.info(f"[RagicCache] Deleted cache for {table_id}")
        return True

    async def _fetch_field_mapping(self, table_id: str) -> dict[str, str]:
        """從 da_field_info_ragic 取得欄位 ID → 名稱對應"""
        mapping: dict[str, str] = {}
        rows = await _arango_query(
            "FOR f IN da_field_info_ragic FILTER f.table_id == @table_id SORT f.field_id ASC RETURN f",
            {"table_id": table_id},
        )
        for row in rows:
            fid = str(row.get("field_id", ""))
            fname = row.get("field_name", fid)
            if fid:
                mapping[fid] = fname
        return mapping

    async def _fetch_from_ragic(self, table_id: str) -> list[dict[str, Any]]:
        """透過 Rust API Proxy 讀取 Ragic 原始資料"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{RUST_API}/api/v1/da/ragic/proxy/{table_id}/data",
                params={"offset": 0, "limit": 99999},
            )
            if resp.status_code != 200:
                logger.warning(f"[RagicCache] Ragic proxy failed for {table_id}: {resp.status_code}")
                return []
            body = resp.json()
            if isinstance(body, dict):
                return body.get("rows", [])
        return []

    async def refresh(self, table_id: str) -> bool:
        """強制從 Ragic API 重新拉取並寫入快取"""
        field_mapping = await self._fetch_field_mapping(table_id)
        rows = await self._fetch_from_ragic(table_id)
        if not rows:
            return False
        await self.write(table_id, rows, field_mapping)
        return True

    async def read_or_refresh(self, table_id: str) -> dict[str, Any] | None:
        if table_id not in self._locks:
            self._locks[table_id] = asyncio.Lock()
        async with self._locks[table_id]:
            data = await self.read(table_id)
            if data is None:
                await self.refresh(table_id)
                data = await self.read(table_id)
        return data
