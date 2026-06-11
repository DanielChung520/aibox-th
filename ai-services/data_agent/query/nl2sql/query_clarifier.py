"""
NL→SQL Pipeline - Pre-query Clarification

LLM judges whether the NL query is semantically complete enough to
generate SQL.  If ambiguous or missing critical info, returns structured
clarification questions so the frontend can prompt the user.

Rule-based pre-filter skips LLM for queries containing business keywords.

# Last Update: 2026-03-24 19:50:39
# Author: Daniel Chung
# Version: 1.3.0
"""

import json
import logging
import re

import httpx

from data_agent.query.nl2sql.models import (
    ClarificationQuestion,
    ClarificationResponse,
    PipelineConfig,
)

logger = logging.getLogger(__name__)

_BUSINESS_KEYWORDS: set[str] = {
    "採購", "訂單", "物料", "供應商", "庫存", "收貨", "發貨", "入庫", "出庫",
    "PO", "PR", "GR", "MARA", "EKKO", "EKPO", "LFA1", "MARD", "MSEG", "MKPF",
    "金額", "數量", "價格", "成本", "排名", "統計", "彙總", "明細",
    "vendor", "material", "purchase", "inventory", "stock", "order",
    "MAKT", "MCHB", "T001", "EBAN",
    "倉庫", "料架", "品項", "交易對象",
    "收貨", "進貨", "銷貨", "盤點", "入庫", "出庫", "客戶",
}

_KEYWORD_PATTERN = re.compile(
    "|".join(re.escape(k) for k in _BUSINESS_KEYWORDS),
    re.IGNORECASE,
)

_MIN_LENGTH_FOR_SKIP = 4
_MAX_LENGTH_FOR_FORCE_CLARIFY = 10


def _is_likely_valid(query: str) -> bool:
    """Fast rule-based check: skip LLM if query looks valid."""
    stripped = query.strip()
    if len(stripped) < _MIN_LENGTH_FOR_SKIP:
        return False
    return bool(_KEYWORD_PATTERN.search(stripped))


def _is_too_short_without_keywords(query: str) -> bool:
    stripped = query.strip()
    if len(stripped) > _MAX_LENGTH_FOR_FORCE_CLARIFY:
        return False
    return not bool(_KEYWORD_PATTERN.search(stripped))

CLARIFY_SYSTEM = (
    "你是一個資料查詢助手。使用者會用自然語言描述想查詢的資料。\n"
    "你的任務：判斷使用者的查詢是否有足夠的語義資訊來生成 SQL 查詢。\n\n"
    "可用的資料領域：SAP MM（物料管理），包含採購訂單(EKKO/EKPO)、"
    "物料主檔(MARA/MAKT)、供應商(LFA1)、庫存(MARD/MCHB)、"
    "收貨/發貨(MKPF/MSEG)等。\n\n"
    "判斷標準：\n"
    "1. 查詢目標明確（能對應到具體的表和欄位）→ OK\n"
    "2. 含有時間範圍或可推斷預設範圍 → OK\n"
    "3. 常見簡寫能被理解（如 PO=採購訂單） → OK\n"
    "4. 過於模糊（如「查一下資料」「幫我看看」） → 需要澄清\n"
    "5. 涉及不存在的資料領域 → 需要澄清\n"
    "6. 缺少關鍵篩選條件且無法設定合理預設 → 需要澄清\n\n"
    "回傳格式（嚴格 JSON，不要多餘文字）：\n"
    '{"needs_clarification": false, "reason": ""}\n'
    "或\n"
    '{"needs_clarification": true, "reason": "說明原因", '
    '"questions": [{"field": "欄位名", "question": "問題"}]}'
)


async def check_query_clarity(
    query: str, config: PipelineConfig,
) -> ClarificationResponse:
    """Ask LLM whether the NL query needs clarification before SQL generation."""
    if _is_likely_valid(query):
        logger.debug("Clarifier skipped (rule-based pass): %s", query[:60])
        return ClarificationResponse(needs_clarification=False)

    if _is_too_short_without_keywords(query):
        logger.debug("Clarifier forced (short + no keywords): %s", query[:60])
        return ClarificationResponse(
            needs_clarification=True,
            reason="查詢過於簡短且缺乏業務關鍵詞，無法確定查詢目標",
            questions=[
                ClarificationQuestion(
                    field="query_target",
                    question="請說明您想查詢哪類資料（採購訂單、物料、供應商、庫存或收發貨）？",
                )
            ],
        )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{config.ollama_base_url}/api/chat",
                json={
                    "model": config.small_model,
                    "messages": [
                        {"role": "system", "content": CLARIFY_SYSTEM},
                        {"role": "user", "content": query},
                    ],
                    "stream": False,
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            content = str(resp.json().get("message", {}).get("content", ""))

        return _parse_clarification(content)

    except (httpx.HTTPError, Exception) as e:
        logger.warning("Clarifier LLM call failed: %s — skipping clarification", e)
        return ClarificationResponse(needs_clarification=False)


def _parse_clarification(raw: str) -> ClarificationResponse:
    """Parse LLM JSON response into ClarificationResponse."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                logger.warning("Cannot parse clarifier output: %s", cleaned[:200])
                return ClarificationResponse(needs_clarification=False)
        else:
            return ClarificationResponse(needs_clarification=False)

    needs = bool(data.get("needs_clarification", False))
    reason = str(data.get("reason", ""))
    raw_questions = data.get("questions", [])
    questions = [
        ClarificationQuestion(
            field=str(q.get("field", "")),
            question=str(q.get("question", "")),
        )
        for q in raw_questions
        if isinstance(q, dict) and q.get("question")
    ]

    return ClarificationResponse(
        needs_clarification=needs,
        reason=reason,
        questions=questions,
    )
