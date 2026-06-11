"""
@file        訂單小秘 — 訂單預購單收集技能
@description 接收使用者輸入的訂購資訊（文字/圖片/結構化 JSON），解析後檢查完整性，
              完整則寫入 order_preorders，不完整則回傳缺少欄位。
              所有預購單建立操作必須透過此技能，禁止直接呼叫 preorder.py raw API。
@lastUpdate  2026-04-30 02:50:00
@author      AI Agent
@version     1.1.0

# Skill 規範

## 用途
任何需要建立預購單的情境，統一呼叫本技能：
- LINE 文字/圖片 → 經 LLM 解析後寫入
- 前端表單（PreorderBoard） → 結構化 JSON 直接寫入
- Chat Agent 提取訂單資訊 → 結構化 JSON 直接寫入

## 輸入
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| content | string | ✅ | 文字、JSON 字串或 base64 圖片/檔案 |
| media_type | enum | ✅ | text / image / file / structured |
| session_id | string | ❌ | 對話 session |
| user_id | string | ❌ | 使用者 ID |
| user_name | string | ❌ | 使用者名稱 |
| filename | string | ❌ | 檔案名稱 |
| reference_llm | object | ❌ | LLM 參考設定（含 model / api_base / api_key / provider_type），不傳則自動從 DB 查詢 |

當 media_type=structured 時，content 須為 JSON 格式：
{"items": [{"product_name": "...", "quantity": 10, "unit": "噸", "spec": "..."}], "notes": "..."}

當 media_type=file 時，content 須為 base64 編碼的檔案 binary，filename 須含副檔名（.pdf/.xlsx/.xls/.csv/.docx）。

## 輸出
| 欄位 | 類型 | 說明 |
|------|------|------|
| status | string | success / error |
| order_id | string | 成功時回傳預購單編號 |
| message | string | 給使用者的訊息 |
| missing_fields | array | 不完整時列出缺少欄位 |

## 回應流程（兩階段）
呼叫端處理長時間操作（如圖片/檔案解析）時，應先回覆 ack 訊息再進行處理：

```
Step 1: 立即 reply ack_message
    「收到您的檔案，我會盡快解析您的檔案後，回覆給您，並建立預購單。」

Step 2: 處理完成後 push/send result_message
    成功 → 「已為您建立預購單 PO-XXX，狀態：開立。」
    失敗 → 「無法識別訂購資訊，請確認包含品名、數量和單位」
```

ack 訊息定義於 `ACK_MESSAGE_FILE` / `ACK_MESSAGE_TEXT` 常數中，
呼叫端應直接引用這些常數，不可自行 hardcode。

## 路由
- HTTP: POST /order-secretary/skills/order_preorder_collect
- Skills Framework: SkillRegistry.execute("order_preorder_collect", params)

## 呼叫範例
結構化輸入（前端表單 / Chat Agent）：
```json
POST /order-secretary/skills/order_preorder_collect
{
  "content": "{\"items\":[{\"product_name\":\"鋼板\",\"quantity\":20,\"unit\":\"噸\",\"spec\":\"5mm\"}],\"notes\":\"急單\"}",
  "media_type": "structured",
  "user_id": "u001",
  "user_name": "王小明",
  "session_id": "sess_001"
}
```

原始文字輸入（LINE / 對話）：
```json
POST /order-secretary/skills/order_preorder_collect
{
  "content": "我要訂購鋼板20噸，厚度5mm",
  "media_type": "text",
  "user_id": "line_user_001",
  "user_name": "王小明",
  "session_id": "line:ch_demo:user_001"
}
```
"""

import base64
import csv
import io
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MULTIMEDIA_ANALYZER_URL = os.getenv(
    "MULTIMEDIA_ANALYZER_URL", "http://127.0.0.1:8011/mcp/multimedia-analyzer"
)
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")
REQUIRED_FIELDS = ["product_name", "quantity", "unit"]

# 技能定義中的標準 ack 訊息（呼叫端在長時間處理前應先回覆使用者）
ACK_MESSAGE_FILE = "收到您的檔案，我會盡快解析您的檔案後，回覆給您，並建立預購單。"
ACK_MESSAGE_TEXT = "收到您的訊息，正在處理中，請稍後..."

SKILL_DEFINITION = {
    "name": "order_preorder_collect",
    "description": "收集客戶的訂購資訊（文字/圖片/結構化 JSON），檢查完整性後建立預購單。所有預購單建立操作必須透過此技能。",
    "ack_messages": {
        "file": ACK_MESSAGE_FILE,
        "text": ACK_MESSAGE_TEXT,
    },
    "input_schema": {
        "content": {
            "type": "string",
            "description": "文字內容、JSON 字串或 base64 編碼的圖片",
        },
        "media_type": {
            "type": "string",
            "enum": ["text", "image", "file", "structured"],
            "description": "輸入類型：text=原始文字, image=圖片（經 LLM 解析）, file=PDF/Excel/CSV/DOCX（直接解析文字）, structured=結構化 JSON（前端表單/Agent 直接傳入）",
        },
        "session_id": {"type": "string", "description": "對話 session（選填）"},
        "user_id": {"type": "string", "description": "使用者 ID"},
        "user_name": {"type": "string", "description": "使用者名稱"},
        "filename": {"type": "string", "description": "檔案名稱（選填）"},
        "reference_llm": {
            "type": "object",
            "description": "LLM 參考設定物件，含 model / api_base / api_key / provider_type。不傳則自動從 DB 查詢。",
            "properties": {
                "model": {"type": "string"},
                "api_base": {"type": "string"},
                "api_key": {"type": "string"},
                "provider_type": {"type": "string", "enum": ["openai", "ollama"]},
            },
        },
    },
    "output_schema": {
        "status": {"type": "string", "enum": ["success", "error"]},
        "order_id": {"type": "string", "description": "成功時回傳預購單 ID"},
        "message": {"type": "string", "description": "給使用者的訊息"},
        "missing_fields": {"type": "array", "description": "不完整時列出缺少欄位"},
        "error_code": {"type": "string", "description": "失敗時的錯誤代碼"},
    },
}


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    """執行訂單預購單收集技能

    所有預購單建立操作必須透過此技能入口，禁止直接呼叫 preorder.py raw API。
    依 media_type 分流：
    - structured：content 為 JSON，直接驗證後寫入
    - text：content 為原始文字，經 LLM 解析後寫入
    - image：content 為 base64 圖片，經多媒體分析器 + LLM 解析後寫入

    Args:
        params: 包含 content, media_type, session_id, user_id, user_name, filename
                reference_llm（選填）：{model, api_base, api_key, provider_type}

    Returns:
        {status, order_id?, message, missing_fields?, error_code?}
    """
    content = params.get("content", "").strip()
    media_type = params.get("media_type", "text")
    session_id = params.get("session_id", "")
    user_id = params.get("user_id", "anonymous")
    user_name = params.get("user_name", user_id)
    reference_llm = params.get("reference_llm")

    if not content:
        return {
            "status": "error",
            "message": "輸入內容為空",
            "missing_fields": ["content"],
        }

    # ============ 分流：結構化輸入 ============
    if media_type == "structured":
        return await _handle_structured(content, user_id, user_name, session_id)

    # ============ 分流：圖片輸入 ============
    if media_type == "image":
        return await _handle_image(
            content,
            user_id,
            user_name,
            session_id,
            params.get("filename", "order_image"),
            reference_llm=reference_llm,
        )

    # ============ 分流：檔案輸入（PDF/Excel/CSV/DOCX）============
    if media_type == "file":
        return await _handle_file(
            content,
            user_id,
            user_name,
            session_id,
            params.get("filename", "document"),
            reference_llm=reference_llm,
        )

    # ============ 預設：文字輸入 ============
    return await _handle_text(
        content, user_id, user_name, session_id, reference_llm=reference_llm
    )


async def _handle_structured(
    content: str, user_id: str, user_name: str, session_id: str
) -> dict[str, Any]:
    """處理結構化 JSON 輸入（前端表單 / Chat Agent 直接傳入）

    content 格式：
    {"items": [{"product_name": "...", "quantity": 10, "unit": "...", "spec": "..."}], "notes": "..."}
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "結構化資料格式錯誤，須為 JSON",
            "missing_fields": [],
            "error_code": "INVALID_JSON",
        }

    items = data.get("items", [])
    if not items or not isinstance(items, list):
        return {
            "status": "error",
            "message": "缺少訂購品項（items）",
            "missing_fields": ["items"],
            "error_code": "MISSING_ITEMS",
        }

    # 驗證每個品項的必填欄位
    all_missing = set()
    for i, item in enumerate(items):
        for field in REQUIRED_FIELDS:
            if not item.get(field):
                all_missing.add(f"{field}[{i}]")

    if all_missing:
        return {
            "status": "error",
            "message": f"訂購資訊不完整，缺少：{'、'.join(sorted(all_missing))}，請補充後重新提交",
            "missing_fields": sorted(all_missing),
        }

    # 寫入主表 + 明細
    return await _write_preorder_db(
        items, user_id, user_name, session_id, data.get("notes", "")
    )


async def _handle_image(
    content: str,
    user_id: str,
    user_name: str,
    session_id: str,
    filename: str,
    reference_llm: dict | None = None,
) -> dict[str, Any]:
    """處理圖片輸入 → 多媒體分析 → LLM 解析 → 寫入"""
    order_text = ""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{MULTIMEDIA_ANALYZER_URL}/analyze",
                json={
                    "content": content,
                    "media_type": "image",
                    "filename": filename,
                    "platform": "line",
                    "user_id": user_id,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                order_text = data.get("description", "")
                logger.info(f"[Skill] Image analyzed: {len(order_text)} chars")
            else:
                return {
                    "status": "error",
                    "message": "圖片解析失敗，請重新上傳清晰的訂購截圖",
                    "missing_fields": [],
                    "error_code": "MEDIA_PARSE_FAILED",
                }
    except Exception as e:
        logger.error(f"[Skill] Multimedia analyzer error: {e}")
        return {
            "status": "error",
            "message": "圖片解析服務暫時無法使用，請稍後再試",
            "missing_fields": [],
            "error_code": "MEDIA_PARSE_FAILED",
        }

    if not order_text.strip():
        return {
            "status": "error",
            "message": "無法從圖片中提取訂購資訊",
            "missing_fields": ["product_name", "quantity", "unit"],
            "error_code": "NO_TEXT_EXTRACTED",
        }

    return await _parse_and_write(
        order_text, user_id, user_name, session_id, reference_llm=reference_llm
    )


async def _handle_text(
    content: str,
    user_id: str,
    user_name: str,
    session_id: str,
    reference_llm: dict | None = None,
) -> dict[str, Any]:
    """處理原始文字輸入 → LLM 解析 → 寫入"""
    if not content.strip():
        return {
            "status": "error",
            "message": "無法從輸入中提取訂購資訊，請提供更清楚的描述",
            "missing_fields": ["product_name", "quantity", "unit"],
        }
    return await _parse_and_write(
        content, user_id, user_name, session_id, reference_llm=reference_llm
    )


async def _handle_file(
    content: str,
    user_id: str,
    user_name: str,
    session_id: str,
    filename: str,
    reference_llm: dict | None = None,
) -> dict[str, Any]:
    """處理檔案輸入（PDF/Excel/CSV/DOCX）→ 直接解析文字 → LLM 解析 → 寫入"""
    try:
        binary = base64.b64decode(content)
    except Exception:
        return {
            "status": "error",
            "message": "檔案格式錯誤，無法解碼",
            "missing_fields": [],
            "error_code": "INVALID_FILE",
        }

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    order_text = ""

    try:
        if ext == "pdf":
            order_text = await _extract_pdf_text(binary)
        elif ext in ("xlsx", "xls"):
            order_text = await _extract_excel_text(binary)
        elif ext == "csv":
            order_text = await _extract_csv_text(binary)
        elif ext == "docx":
            order_text = await _extract_docx_text(binary)
        else:
            return {
                "status": "error",
                "message": f"不支援的檔案格式：.{ext}，支援格式：PDF、Excel、CSV、DOCX",
                "missing_fields": [],
                "error_code": "UNSUPPORTED_FILE_TYPE",
            }
    except Exception as e:
        logger.error(f"[Skill] File extraction error ({ext}): {e}")
        return {
            "status": "error",
            "message": f"檔案解析失敗（.{ext}），請確認檔案內容包含文字",
            "missing_fields": [],
            "error_code": "FILE_PARSE_FAILED",
        }

    if not order_text.strip():
        return {
            "status": "error",
            "message": "無法從檔案中提取文字，請確認檔案包含可讀取的文字內容",
            "missing_fields": ["product_name", "quantity", "unit"],
            "error_code": "NO_TEXT_EXTRACTED",
        }

    return await _parse_and_write(
        order_text, user_id, user_name, session_id, reference_llm=reference_llm
    )


async def _extract_pdf_text(binary: bytes) -> str:
    """從 PDF 提取文字（使用 pdfplumber）"""
    import pdfplumber

    with pdfplumber.open(io.BytesIO(binary)) as pdf:
        pages = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages) if pages else ""


async def _extract_excel_text(binary: bytes) -> str:
    """從 Excel 提取文字（使用 openpyxl）"""
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(binary), data_only=True)
    parts = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) if c is not None else "" for c in row]
            line = " | ".join(cells).strip()
            if line:
                parts.append(line)
    return "\n".join(parts) if parts else ""


async def _extract_csv_text(binary: bytes) -> str:
    """從 CSV 提取文字（使用標準 csv module）"""
    decoded = binary.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(decoded))
    parts = [" | ".join(row) for row in reader if row]
    return "\n".join(parts) if parts else ""


async def _extract_docx_text(binary: bytes) -> str:
    """從 DOCX 提取文字（使用 python-docx）"""
    import docx

    doc = docx.Document(io.BytesIO(binary))
    parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(parts) if parts else ""


async def _parse_and_write(
    order_text: str,
    user_id: str,
    user_name: str,
    session_id: str,
    reference_llm: dict | None = None,
) -> dict[str, Any]:
    """通用流程：LLM 解析文字（支援多品項）→ 驗證 → 寫入"""
    items = await _extract_order_items(order_text, reference_llm=reference_llm)
    if not items:
        return {
            "status": "error",
            "message": "無法識別訂購資訊，請確認包含品名、數量和單位",
            "missing_fields": REQUIRED_FIELDS,
        }

    # 驗證每個品項的必填欄位
    all_missing = set()
    notes_list = []
    customer_name_from_items = ""
    for item in items:
        for field in REQUIRED_FIELDS:
            if not item.get(field):
                all_missing.add(field)
        note = item.get("notes", "")
        if note:
            notes_list.append(note)
            # 從 notes 中提取客戶名稱（如「客戶：寧衫商行」）
            if not customer_name_from_items and "客戶：" in note:
                customer_name_from_items = (
                    note.split("客戶：")[1].split("；")[0].split("，")[0].strip()
                )

    if all_missing:
        return {
            "status": "error",
            "message": f"訂購資訊不完整，缺少：{'、'.join(sorted(all_missing))}，請補充後重新提交",
            "missing_fields": sorted(all_missing),
        }

    # 若 LLM 從圖片描述中提取到客戶名稱，優先作為 user_name
    actual_user_name = user_name
    if customer_name_from_items and customer_name_from_items not in user_name:
        actual_user_name = f"{customer_name_from_items}({user_name})"
        logger.info(
            f"[Skill] Customer detected from image: {customer_name_from_items}, user_name={actual_user_name}"
        )

    items_data = [
        {
            "product_name": item["product_name"],
            "quantity": item["quantity"],
            "unit": item.get("unit", ""),
            "spec": item.get("spec", ""),
            "notes": item.get("notes", ""),
        }
        for item in items
    ]
    combined_notes = "；".join(n for n in notes_list if n) if notes_list else ""
    return await _write_preorder_db(
        items_data, user_id, actual_user_name, session_id, combined_notes
    )


async def _write_preorder_db(
    items: list[dict], user_id: str, user_name: str, session_id: str, notes: str
) -> dict[str, Any]:
    """核心：寫入主表 order_preorders + 明細 order_preorder_items"""
    try:
        from bpa.order_secretary.preorder import (
            create_preorder,
            _next_preorder_id,
            _write_items,
        )

        now = datetime.now(timezone.utc).isoformat()
        preorder_id = await _next_preorder_id()
        master = {
            "preorder_id": preorder_id,
            "user_id": user_id,
            "user_name": user_name,
            "session_id": session_id,
            "source": "chat",
            "message_date": now,
            "status": "開立",
            "notes": notes,
            "created_at": now,
            "updated_at": now,
        }
        await create_preorder(master)
        items_data = [
            {
                "product_name": i.get("product_name", i.get("name", "")),
                "quantity": float(i.get("quantity", 0)),
                "unit": i.get("unit", ""),
                "spec": i.get("spec", ""),
                "notes": i.get("notes", ""),
            }
            for i in items
        ]
        await _write_items(preorder_id, items_data)
        logger.info(f"[Skill] Preorder created: {preorder_id}")

        # 建立訂購摘要
        summary_lines = []
        for i, item in enumerate(items_data, 1):
            spec_str = f"（{item['spec']}）" if item.get("spec") else ""
            note_str = f" [{item['notes']}]" if item.get("notes") else ""
            summary_lines.append(
                f"{i}. {item['product_name']} × {item['quantity']}{item['unit']}{spec_str}{note_str}"
            )
        summary = "\n".join(summary_lines)

        return {
            "status": "success",
            "order_id": preorder_id,
            "message": f"已為您解析訂購資訊：\n{summary}\n\n已建立預購單 {preorder_id}，我們會盡快進行回單確認！",
            "summary": summary_lines,
        }
    except Exception as e:
        logger.error(f"[Skill] Preorder creation failed: {e}")
        return {
            "status": "error",
            "message": "預購單建立失敗，請稍後再試",
            "missing_fields": [],
            "error_code": "DB_WRITE_ERROR",
        }


async def _query_arango(aql: str, bind_vars: dict | None = None) -> list[dict]:
    """查詢 ArangoDB（技能內部使用，查 agent 與 model_providers）"""
    import base64

    auth_cred = f"{ARANGO_USER}:{ARANGO_PASSWORD}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(auth_cred.encode()).decode()}",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": aql, "bindVars": bind_vars or {}},
                headers=headers,
            )
            if resp.status_code in (200, 201):
                return resp.json().get("result", [])
    except Exception as e:
        logger.warning(f"[Skill] Arango query failed: {e}")
    return []


async def _extract_order_info(text: str) -> dict | None:
    """使用 LLM 從文字中提取結構化訂購資訊（單品項，相容舊呼叫）"""
    items = await _extract_order_items(text)
    if items and len(items) > 0:
        return items[0]
    return None


async def _resolve_llm_config(
    reference_llm: dict | None = None,
) -> tuple[str, str, str, str]:
    """查詢 ArangoDB model_providers，找出 deepseek-v4-flash 的 API 設定

    Returns:
        (model_name, api_base, api_key, provider_type)
        provider_type: "openai" | "ollama"

    若傳入 reference_llm（含 model / api_base / api_key / provider_type），直接使用，不查 DB。
    """
    # 若 caller 有傳 reference_llm，直接使用
    if reference_llm and isinstance(reference_llm, dict) and reference_llm.get("model"):
        return (
            reference_llm.get("model", "deepseek-v4-flash"),
            reference_llm.get(
                "api_base", os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
            ),
            reference_llm.get("api_key", ""),
            reference_llm.get("provider_type", "openai"),
        )

    default_model = "deepseek-v4-flash"
    default_base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    # 先查 agent 設定的模型
    agent_key = os.getenv(
        "ORDER_SECRETARY_AGENT_KEY", "efa9f03a-3953-4ff2-89cc-7cb19e658b90"
    )
    try:
        agents = await _query_arango(
            "FOR a IN agents FILTER a._key == @key LIMIT 1 RETURN a",
            {"key": agent_key},
        )
        if agents:
            model = agents[0].get("llm_model") or default_model
        else:
            model = default_model
    except Exception:
        model = default_model

    # 從 model_providers 找這個模型的 provider
    try:
        providers = await _query_arango(
            "FOR p IN model_providers FILTER p.status == 'enabled' RETURN p",
        )
        for p in providers:
            p_models = p.get("models") or []
            for m in p_models:
                if isinstance(m, dict) and m.get("model_id") == model:
                    base_url = (p.get("base_url") or "").rstrip("/")
                    api_key = p.get("api_key") or ""
                    is_local = "localhost" in base_url or "127.0.0.1" in base_url
                    provider_type = "ollama" if is_local else "openai"
                    return model, base_url, api_key, provider_type
    except Exception:
        pass

    return model, default_base, "", "ollama"


async def _call_llm_json(
    messages: list[dict], model: str, api_base: str, api_key: str, provider_type: str
) -> str:
    """呼叫 LLM 並回傳 JSON 字串（支援 Ollama 與 OpenAI 兩種 API）"""
    if provider_type == "ollama":
        url = f"{api_base}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "format": "json",
        }
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(url, json=payload)
            if r.status_code == 200:
                return r.json().get("message", {}).get("content", "[]")
    else:
        url = f"{api_base}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {"model": model, "messages": messages, "stream": False}
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(url, json=payload, headers=headers)
            if r.status_code == 200:
                choices = r.json().get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "[]")
    return "[]"


async def _extract_order_items(
    text: str, reference_llm: dict | None = None
) -> list[dict] | None:
    """使用 LLM（deepseek-v4-flash）從冗長描述（表格/多行）中提取多筆結構化訂購資訊

    支援：
    - 單行訂單文字：「我要訂購鋼板20噸」
    - 多行/表格描述：「切芽 18k 裸包:9K裝 ... 小卷 120包 已預訂」
    - 多媒體分析器輸出的冗長表格描述

    Returns:
        [{"product_name": "...", "quantity": 10.0, "unit": "噸", "spec": "...", "notes": "..."}, ...]
        若完全無法識別則回傳 None
    """
    model, api_base, api_key, provider_type = await _resolve_llm_config(
        reference_llm=reference_llm
    )

    prompt = f"""你是一個訂單資訊提取器。請從以下文字中提取所有訂購品項，以 JSON 陣列回覆。

文字內容：
{text}

回覆格式（JSON 陣列，每項一個 object）：
[
  {{
    "product_name": "品名",
    "quantity": 數量（純數字，不含單位）,
    "unit": "單位（如噸、公斤、包、箱、斤）",
    "spec": "規格（若無則空字串）",
    "notes": "備註（如效期、包裝方式、已預訂等，若無則空字串）"
  }}
]

規則：
1. 只要文字中有明確的品名+數量+單位，就提取出來
2. 若文字中有提到**客戶/商家名稱**（如「XX商行」、「XX公司」），在每個品項的 notes 開頭加上「客戶：XX」
3. 盡可能保留原始表格中的備註資訊（效期、包裝方式、預訂狀態等）
4. 若無法識別任何品項，回覆空陣列 []
5. 只回 JSON，不要其他內容"""

    try:
        content = await _call_llm_json(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            api_base=api_base,
            api_key=api_key,
            provider_type=provider_type,
        )
        parsed = json.loads(content)
        if not isinstance(parsed, list):
            return None
        # 清理並驗證
        valid = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            name = str(item.get("product_name", "")).strip()
            if not name:
                continue
            qty = item.get("quantity", 0)
            try:
                qty = float(qty) if qty else 0
            except (ValueError, TypeError):
                qty = 0
            valid.append(
                {
                    "product_name": name,
                    "quantity": qty,
                    "unit": str(item.get("unit", "")),
                    "spec": str(item.get("spec", "")),
                    "notes": str(item.get("notes", "")),
                }
            )
        return valid if valid else None
    except Exception as e:
        logger.warning(f"[Skill] LLM extraction failed: {e}")
    return None
