"""
@file        market_intel/main.py
@description 市場觀察服務 — FastAPI 入口
@lastUpdate  2026-06-14
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from market_intel.scraper import search, fetch_page_content, SearchResult
from market_intel.summarizer import summarize_article, generate_daily_report

logger = logging.getLogger(__name__)

app = FastAPI(title="Market Intel", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── ArangoDB helpers ─────────────────────────────

ARANGO_URL = "http://localhost:8529"
ARANGO_DB = "abc_desktop"
ARANGO_USER = "root"
ARANGO_PASSWORD = "abc_desktop_2026"


async def _aql(query: str, bind: dict | None = None) -> list[dict]:
    import httpx as _httpx
    import base64
    auth = base64.b64encode(f"{ARANGO_USER}:{ARANGO_PASSWORD}".encode()).decode()
    async with _httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": query, "bindVars": bind or {}},
            headers={"Authorization": f"Basic {auth}"},
        )
        if resp.status_code not in (200, 201):
            raise Exception(f"AQL error: {resp.text}")
        return resp.json().get("result", [])


async def _upsert(collection: str, key: str, data: dict) -> None:
    import httpx as _httpx
    import base64
    auth = base64.b64encode(f"{ARANGO_USER}:{ARANGO_PASSWORD}".encode()).decode()
    async with _httpx.AsyncClient(timeout=20) as client:
        await client.put(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/{collection}/{key}",
            json={"_key": key, **data},
            headers={"Authorization": f"Basic {auth}"},
        )


# ─── Pydantic models ──────────────────────────────


class ReportItem(BaseModel):
    title: str
    url: str
    source: str
    summary: str = ""
    relevance: str = "medium"
    action: str | None = None
    impact: str = "neutral"


class DailyReport(BaseModel):
    date: str
    items: list[ReportItem]
    daily_focus: str = ""
    key_trends: list[str] = []
    attention_points: list[str] = []
    opportunities: list[str] = []
    overall_assessment: str = ""
    created_at: str = ""
    token_usage: dict[str, int] = {}


# ─── Endpoints ────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/refresh-celery")
async def refresh_celery(body: dict) -> dict:
    """透過 Celery 背景執行市場觀察任務"""
    keywords = body.get("keywords")
    user_key = body.get("user_key")
    import sys, os
    _dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _dir not in sys.path: sys.path.insert(0, _dir)
    from celery_app.tasks import market_intel_refresh
    task = market_intel_refresh.delay(keywords=keywords, user_key=user_key)
    return {"task_id": task.id, "status": "submitted"}


@app.get("/task/{task_id}")
async def get_task_status(task_id: str) -> dict:
    """查詢 Celery 任務狀態"""
    import sys, os
    _dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _dir not in sys.path: sys.path.insert(0, _dir)
    from celery_app.app import app as celery_app
    result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.state,
        "info": result.info if result.info else None,
    }
    """提交背景執行任務，立即回傳 job_id"""
    import asyncio
    import uuid

    job_id = str(uuid.uuid4())[:8]
    today = date.today().isoformat()

    # 建立 job 記錄
    job_doc = {
        "_key": f"mi_{job_id}",
        "job_id": job_id,
        "status": "running",
        "progress": "init",
        "date": today,
        "keywords": keywords or [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await _upsert("market_intel_jobs", f"mi_{job_id}", job_doc)
    except Exception:
        pass

    # 背景執行
    asyncio.create_task(_run_refresh_job(job_id, keywords))

    return {"job_id": job_id, "status": "running", "message": "任務已提交，請輪詢查詢結果"}


async def _run_refresh_job(job_id: str, keywords: list[str] | None) -> None:
    """背景執行搜尋+摘要+儲存（不阻擋前端）"""
    from market_intel.scraper import search, fetch_page_content
    from market_intel.summarizer import summarize_article, generate_daily_report, reset_token_usage, get_token_usage
    from datetime import datetime, timezone

    reset_token_usage()  # 重設計數器

    try:
        await _update_job(job_id, "running", "searching")

        results = await search(keywords=keywords)
        if not results:
            await _update_job(job_id, "completed", "no_results")
            return

        items = []
        for i, r in enumerate(results[:8]):
            await _update_job(job_id, "running", f"fetching {i+1}/{len(results[:8])}")
            content = await fetch_page_content(r.url)
            analysis = await summarize_article(r.title, content)
            items.append({
                "title": r.title, "url": r.url, "source": r.source,
                "summary": analysis.get("summary", r.snippet[:200]),
                "relevance": analysis.get("relevance", "medium"),
                "action": analysis.get("action"),
                "impact": analysis.get("impact", "neutral"),
            })

        await _update_job(job_id, "running", "analyzing")
        report_data = await generate_daily_report(items)

        today = date.today().isoformat()
        doc = {
            "date": today, "items": items,
            "daily_focus": report_data.get("daily_focus", ""),
            "key_trends": report_data.get("key_trends", []),
            "attention_points": report_data.get("attention_points", []),
            "opportunities": report_data.get("opportunities", []),
            "overall_assessment": report_data.get("overall_assessment", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await _upsert("market_intel_reports", f"report_{today}", doc)

        # 記錄 token 用量
        tokens = get_token_usage()
        await _update_job_tokens(job_id, tokens)
        await _update_job(job_id, "completed", "done")

    except Exception as e:
        logger.error("Refresh job %s failed: %s", job_id, e)
        await _update_job(job_id, "failed", str(e))


async def _update_job_tokens(job_id: str, tokens: dict) -> None:
    try:
        await _aql(
            "UPDATE @key WITH {token_usage: @t, updated_at: @now} IN market_intel_jobs",
            {"key": f"mi_{job_id}", "t": tokens, "now": datetime.now(timezone.utc).isoformat()},
        )
    except Exception:
        pass


async def _update_job(job_id: str, status: str, progress: str) -> None:
    """更新 job 狀態"""
    try:
        await _aql(
            "UPDATE @key WITH {status: @s, progress: @p, updated_at: @now} IN market_intel_jobs",
            {"key": f"mi_{job_id}", "s": status, "p": progress, "now": datetime.now(timezone.utc).isoformat()},
        )
    except Exception:
        pass


@app.get("/job/{job_id}")
async def get_job_status(job_id: str) -> dict:
    """查詢背景任務狀態"""
    try:
        rows = await _aql(
            "FOR j IN market_intel_jobs FILTER j.job_id == @id LIMIT 1 RETURN {job_id: j.job_id, status: j.status, progress: j.progress, date: j.date, token_usage: j.token_usage}",
            {"id": job_id},
        )
        if rows:
            return rows[0]
    except Exception:
        pass
    return {"status": "not_found", "job_id": job_id}


@app.get("/report/{date_str}")
async def get_report(date_str: str) -> dict:
    """取得指定日期的快報（回傳該日期第一筆）"""
    try:
        rows = await _aql(
            "FOR r IN market_intel_reports FILTER r.date == @d LIMIT 1 RETURN r",
            {"d": date_str},
        )
        if rows:
            return {k: v for k, v in rows[0].items() if not k.startswith("_")}
    except Exception:
        pass
    return {"status": "not_found", "date": date_str}


@app.get("/report-by-key/{key}")
async def get_report_by_key(key: str) -> dict:
    """取得指定 _key 的快報"""
    try:
        rows = await _aql(
            "FOR r IN market_intel_reports FILTER r._key == @k LIMIT 1 RETURN r",
            {"k": key},
        )
        if rows:
            return {k: v for k, v in rows[0].items() if not k.startswith("_")}
    except Exception:
        pass
    return {"status": "not_found", "key": key}


@app.get("/latest")
async def get_latest(user_key: str | None = None, supervisor_key: str | None = None) -> dict:
    """取得最新的快報。可指定 user_key 只取該使用者產生的，或 supervisor_key 取特定主管產生的。"""
    try:
        if user_key:
            rows = await _aql(
                "FOR r IN market_intel_reports FILTER r.created_by == @uk SORT r.created_at DESC LIMIT 1 RETURN r",
                {"uk": user_key},
            )
        elif supervisor_key:
            rows = await _aql(
                "FOR r IN market_intel_reports FILTER r.created_by == @sk SORT r.created_at DESC LIMIT 1 RETURN r",
                {"sk": supervisor_key},
            )
        else:
            rows = await _aql(
                "FOR r IN market_intel_reports SORT r.created_at DESC LIMIT 1 RETURN r",
            )
        if rows:
            return {k: v for k, v in rows[0].items() if not k.startswith("_")}
    except Exception:
        pass
    return {"status": "not_found", "message": "尚無快報"}


@app.get("/history")
async def list_history(limit: int = 30, user_key: str | None = None) -> list[dict]:
    """取得歷史快報列表（含 token 用量與任務 ID）。可指定 user_key 只取該使用者的記錄。"""
    try:
        if user_key:
            rows = await _aql(
                "FOR r IN market_intel_reports FILTER r.created_by == @uk SORT r.created_at DESC LIMIT @n RETURN {_key: r._key, date: r.date, daily_focus: r.daily_focus, items_count: LENGTH(r.items), token_usage: r.token_usage, task_id: r.task_id, created_at: r.created_at, created_by: r.created_by}",
                {"uk": user_key, "n": limit},
            )
        else:
            rows = await _aql(
                "FOR r IN market_intel_reports SORT r.created_at DESC LIMIT @n RETURN {_key: r._key, date: r.date, daily_focus: r.daily_focus, items_count: LENGTH(r.items), token_usage: r.token_usage, task_id: r.task_id, created_at: r.created_at, created_by: r.created_by}",
                {"n": limit},
            )
        return rows
    except Exception:
        return []


@app.post("/delete-reports")
async def delete_reports(body: dict) -> dict:
    """批次刪除指定的快報記錄"""
    keys = body.get("keys", [])
    if not keys or not isinstance(keys, list):
        return {"status": "error", "message": "keys must be a non-empty list"}
    try:
        import httpx as _httpx, base64
        auth = base64.b64encode(f"{ARANGO_USER}:{ARANGO_PASSWORD}".encode()).decode()
        deleted = 0
        async with _httpx.AsyncClient(timeout=30) as client:
            for k in keys:
                resp = await client.delete(
                    f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/market_intel_reports/{k}",
                    headers={"Authorization": f"Basic {auth}"},
                )
                if resp.status_code in (200, 202):
                    deleted += 1
        return {"status": "ok", "deleted": deleted}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/cleanup")
async def cleanup_old_reports() -> dict:
    """刪除超過保留天數的舊快報（預設 10 天）"""
    try:
        from datetime import datetime, timezone, timedelta
        import httpx as _httpx, base64

        # 讀取保留天數設定
        try:
            rows = await _aql(
                "FOR p IN system_params FILTER p._key == @k LIMIT 1 RETURN p.param_value",
                {"k": "market_intel.retention_days"},
            )
            days = int(rows[0]) if rows else 10
        except:
            days = 10

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        keys_to_delete = await _aql(
            "FOR r IN market_intel_reports FILTER r.created_at < @cutoff RETURN r._key",
            {"cutoff": cutoff},
        )
        if not keys_to_delete:
            return {"status": "ok", "deleted": 0, "message": "無需清理"}

        auth = base64.b64encode(f"{ARANGO_USER}:{ARANGO_PASSWORD}".encode()).decode()
        deleted = 0
        async with _httpx.AsyncClient(timeout=60) as client:
            for k in keys_to_delete:
                resp = await client.delete(
                    f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/market_intel_reports/{k}",
                    headers={"Authorization": f"Basic {auth}"},
                )
                if resp.status_code in (200, 202):
                    deleted += 1
        return {"status": "ok", "deleted": deleted}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/push")
async def push_report() -> dict:
    """推播今日快報到所有業務員 LINE"""
    from market_intel.pusher import push_daily_report_to_all
    return await push_daily_report_to_all()


@app.post("/daily-run")
async def daily_run() -> dict:
    """每日排程執行：搜尋 → 摘要 → 儲存 → 推播"""
    from market_intel.pusher import push_daily_report_to_all

    # 1. 搜尋+摘要+儲存（自我呼叫 refresh 邏輯）
    from market_intel.scraper import search, fetch_page_content
    from market_intel.summarizer import summarize_article, generate_daily_report
    from datetime import datetime, timezone

    today = date.today().isoformat()
    results = await search()
    if not results:
        return {"status": "no_results"}

    items = []
    for r in results[:8]:
        content = await fetch_page_content(r.url)
        analysis = await summarize_article(r.title, content)
        items.append({
            "title": r.title, "url": r.url, "source": r.source,
            "summary": analysis.get("summary", r.snippet[:200]),
            "relevance": analysis.get("relevance", "medium"),
            "action": analysis.get("action"),
            "impact": analysis.get("impact", "neutral"),
        })

    report_data = await generate_daily_report(items)
    doc = {
        "date": today, "items": items,
        "daily_focus": report_data.get("daily_focus", ""),
        "key_trends": report_data.get("key_trends", []),
        "attention_points": report_data.get("attention_points", []),
        "opportunities": report_data.get("opportunities", []),
        "overall_assessment": report_data.get("overall_assessment", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _upsert("market_intel_reports", f"report_{today}", doc)

    # 2. 推播
    push_result = await push_daily_report_to_all()

    return {"status": "ok", "items_count": len(items), "push": push_result}


@app.post("/reminders")
async def run_reminders() -> dict:
    """執行所有每日提醒（行程+跟進）"""
    from market_intel.reminders import run_all_reminders
    return await run_all_reminders()


# ─── 啟動排程（APScheduler）────────────────────

@app.on_event("startup")
async def start_scheduler():
    """啟動背景排程，每天早上 08:00 執行 daily_run"""
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()
        scheduler.add_job(daily_run, "cron", hour=8, minute=0, id="market_intel_daily")
        scheduler.add_job(run_reminders, "cron", hour=8, minute=5, id="daily_reminders")
        scheduler.start()
        logger.info("Market Intel scheduler started (daily at 08:00)")
    except ImportError:
        logger.info("APScheduler not installed, scheduler disabled")
