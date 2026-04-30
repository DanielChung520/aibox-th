"""
@file        訂單小秘 — 預購單管理（主表明細版）
@description 主表 order_preorders + 明細 order_preorder_items
             主表：訂購單號、客戶、日期、來源（chat/phone/website）、狀態、備註
             明細：項次、品名、規格、數量、單位、備註
@lastUpdate  2026-04-29 22:41:00
@author      AI Agent
@version     2.0.0
"""

import logging, os, base64, httpx
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Order Preorder"])

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")
SEQ_COLLECTION = "sequence_generator"
MASTER_COL = "order_preorders"
ITEM_COL = "order_preorder_items"


class PreorderItemIn(BaseModel):
    product_name: str
    quantity: float
    unit: str = ""
    spec: str = ""
    notes: str = ""


class PreorderCreate(BaseModel):
    user_id: str
    user_name: str = ""
    session_id: str = ""
    channel_key: str = ""
    source: str = "chat"  # chat / phone / website
    items: list[PreorderItemIn]
    notes: str = ""


class PreorderUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


def _auth() -> dict:
    cred = f"{ARANGO_USER}:{ARANGO_PASSWORD}"
    return {"Content-Type": "application/json", "Authorization": f"Basic {base64.b64encode(cred.encode()).decode()}"}


async def _next_preorder_id() -> str:
    today = datetime.now(timezone.utc).astimezone()
    prefix = today.strftime("PO-%y%m%d-")
    key = f"preorder_seq_{today.strftime('%Y%m%d')}"
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor", json={
            "query": "UPSERT { _key: @key } INSERT { _key: @key, seq: 1 } UPDATE { seq: OLD.seq + 1 } IN @@col OPTIONS { keepNull: false } RETURN { seq: OLD.seq + 1 }",
            "bindVars": {"key": key, "@col": SEQ_COLLECTION},
        }, headers=_auth())
        return f"{prefix}{r.json().get('result',[{}])[0].get('seq',1):04d}"


async def _write_master(doc: dict) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/{MASTER_COL}", headers=_auth(), json=doc)
        return r.json()


async def _write_items(preorder_id: str, items: list[dict]) -> list[dict]:
    docs = []
    for i, item in enumerate(items):
        doc = {"preorder_id": preorder_id, "line_no": i + 1, **item}
        docs.append(doc)
    async with httpx.AsyncClient(timeout=10.0) as c:
        for doc in docs:
            await c.post(f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/{ITEM_COL}", headers=_auth(), json=doc)
    return docs


async def _get_items(preorder_id: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor", json={
            "query": f"FOR i IN {ITEM_COL} FILTER i.preorder_id == @pid SORT i.line_no RETURN i",
            "bindVars": {"pid": preorder_id},
        }, headers=_auth())
        return r.json().get("result", [])


async def _delete_items(preorder_id: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as c:
        await c.post(f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor", json={
            "query": f"FOR i IN {ITEM_COL} FILTER i.preorder_id == @pid REMOVE i IN {ITEM_COL}",
            "bindVars": {"pid": preorder_id},
        }, headers=_auth())


async def _all_preorders() -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor", json={
            "query": f"FOR p IN {MASTER_COL} SORT p.created_at DESC RETURN p",
        }, headers=_auth())
        return r.json().get("result", [])


async def get_preorders_by_user(user_id: str) -> list[dict]:
    """查詢用戶的所有預購單（被 router.py 引用）"""
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor", json={
            "query": f"FOR p IN {MASTER_COL} FILTER p.user_id == @uid SORT p.created_at DESC RETURN p",
            "bindVars": {"uid": user_id},
        }, headers=_auth())
        return r.json().get("result", [])


async def create_preorder(doc: dict) -> dict:
    """直接寫入主表（被 router.py 的 _create_preorder_from_llm 引用）"""
    return await _write_master(doc)


@router.post("/preorders", response_model=dict)
async def create(req: PreorderCreate):
    now = datetime.now(timezone.utc).isoformat()
    preorder_id = await _next_preorder_id()
    master = {
        "preorder_id": preorder_id, "user_id": req.user_id,
        "user_name": req.user_name or req.user_id, "session_id": req.session_id,
        "channel_key": req.channel_key, "source": req.source,
        "message_date": now, "status": "開立", "notes": req.notes,
        "created_at": now, "updated_at": now,
    }
    m = await _write_master(master)
    item_docs = [i.model_dump() for i in req.items]
    await _write_items(preorder_id, item_docs)
    return {"preorder_id": preorder_id, "_key": m.get("_key", ""), "status": "開立"}


@router.get("/preorders", response_model=list[dict])
async def list_all():
    """取所有主表 + 各單明細筆數"""
    masters = await _all_preorders()
    return masters


@router.get("/preorders/{key}", response_model=dict)
async def get(key: str):
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/{MASTER_COL}/{key}", headers=_auth())
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="預購單不存在")
        master = r.json()
        master["items"] = await _get_items(master.get("preorder_id", ""))
        return master


@router.get("/preorders/{key}/items", response_model=list[dict])
async def get_items(key: str):
    """取明細（給前端折疊用）"""
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/{MASTER_COL}/{key}", headers=_auth())
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="預購單不存在")
        master = r.json()
        return await _get_items(master.get("preorder_id", ""))


@router.patch("/preorders/{key}", response_model=dict)
async def update(key: str, req: PreorderUpdate):
    now = datetime.now(timezone.utc).isoformat()
    patch = {"updated_at": now}
    if req.status: patch["status"] = req.status
    if req.notes is not None: patch["notes"] = req.notes
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.patch(f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/{MASTER_COL}/{key}", headers=_auth(), json=patch)
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="預購單不存在")
        return {"status": "updated", "key": key}


@router.delete("/preorders/{key}", response_model=dict)
async def delete(key: str):
    async with httpx.AsyncClient(timeout=10.0) as c:
        # 先查 preorder_id
        r = await c.get(f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/{MASTER_COL}/{key}", headers=_auth())
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="預購單不存在")
        preorder_id = r.json().get("preorder_id", key)
        # 刪明細
        await _delete_items(preorder_id)
        # 刪主表
        await c.delete(f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/{MASTER_COL}/{key}", headers=_auth())
        return {"status": "deleted", "key": key}
