#!/usr/bin/env python3
"""
@file        seed_intent_catalog_shared.py
@description Shared utilities for intent catalog seeding: constants, helper functions,
             and document builders used by SAP and Ragic intent modules.
@lastUpdate  2026-04-13 01:54:04
@author      Daniel Chung
@version     1.1.0
"""

import json
import subprocess

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = "root:abc_desktop_2026"
COLLECTION = "intent_catalog"
TS = "2026-03-29T00:00:00Z"

DA = "data_agent"
ORCH = "orchestrator"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def curl_post_doc(docs: list[dict[str, object]]) -> list[dict[str, object]]:
    payload = json.dumps(docs)
    r = subprocess.run(
        [
            "curl",
            "-s",
            "-u",
            AUTH,
            f"{ARANGO_URL}/_db/{DB}/_api/document/{COLLECTION}?overwriteMode=replace",
            "-X",
            "POST",
            "-H",
            "Content-Type: application/json",
            "-d",
            payload,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    result: list[dict[str, object]] = json.loads(r.stdout)
    return result


def insert_batch(docs: list[dict[str, object]], label: str) -> None:
    result = curl_post_doc(docs)
    errors = 0
    if isinstance(result, list):
        for i, r in enumerate(result):
            if r.get("error"):
                print(f"  ERROR [{docs[i]['_key']}]: {r.get('errorMessage', r)}")
                errors += 1
    elif isinstance(result, dict) and result.get("error"):
        print(f"  Batch error for {label}: {result}")
        errors += 1
    ok = len(docs) - errors
    print(f"  ✓ {label}: {ok}/{len(docs)} inserted/updated")


def make_doc(
    intent_id: str,
    agent_scope: str,
    name: str,
    description: str,
    intent_type: str,
    group: str,
    tables: list[str],
    generation_strategy: str,
    sql_template: str,
    core_fields: list[str],
    nl_examples: list[str],
    example_sqls: list[str] | None = None,
    tool_name: str = "",
    query_type: str = "simple_filter",
    tool_schema: dict[str, object] | None = None,
    involved_tables: list[str] | None = None,
    join_keys: list[dict[str, str]] | None = None,
    expected_output: dict[str, object] | None = None,
    difficulty_level: str = "",
    golden_sql: str = "",
    priority: int = 0,
) -> dict[str, object]:
    doc: dict[str, object] = {
        "_key": intent_id,
        "intent_id": intent_id,
        "agent_scope": agent_scope,
        "name": name,
        "description": description,
        "intent_type": intent_type,
        "group": group,
        "tables": tables,
        "generation_strategy": generation_strategy,
        "sql_template": sql_template,
        "core_fields": core_fields,
        "nl_examples": nl_examples,
        "example_sqls": example_sqls or [],
        "tool_name": tool_name,
        "query_type": query_type,
        "involved_tables": involved_tables or [],
        "join_keys": join_keys or [],
        "priority": priority,
        "status": "enabled",
        "created_at": TS,
        "updated_at": TS,
        "updated_by": "system",
    }
    if tool_schema:
        doc["tool_schema"] = tool_schema
    if expected_output:
        doc["expected_output"] = expected_output
    if difficulty_level:
        doc["difficulty_level"] = difficulty_level
    if golden_sql:
        doc["golden_sql"] = golden_sql
    return doc


def make_orch_doc(
    intent_id: str,
    name: str,
    description: str,
    intent_type: str,  # "chat" | "task"
    domain: str,  # "general" | "order" | "material" | "finance" | "data_query"
    bpa_id: str | None,
    capabilities: list[str],
    nl_examples: list[str],
    task_type: str = "",  # "query" | "action" | "workflow"（task 才填）
    confidence_threshold: float = 0.7,
    priority: int = 0,
    response_strategy: str = "",  # "direct_llm" | "handoff_bpa" | "confirm_then_execute" | "clarify_first"
    # TopIntentRAG 行動方案欄位
    action_type: str = "",  # "direct_answer" | "tool_call" | "process_orchestration"
    target_agent: str = "",  # "chat" | "tool" | "pdca" | "bpa" | "ca"
    tool_category: str = "",  # "web_search" | "data" | "knowledge" | "mcp"
    tool_name: str = "",
    pdca_id: str = "",
    ca_id: str = "",
    nl_patterns: list[str] | None = None,
) -> dict[str, object]:
    """Build an orchestrator intent document (BPA routing model v2).

    response_strategy 語義：
      direct_llm           - 直接由 LLM 回覆，不路由到任何 BPA（用於 chat）
      handoff_bpa          - 直接 handoff 給 BPA 執行，不需用戶確認（純查詢）
      confirm_then_execute - 展示計劃給用戶確認後再執行（寫入/操作類）
      clarify_first        - 先反問用戶釐清意圖（信心度低、意圖模糊時）

    action_type 語義：
      direct_answer        - 直接由 LLM 回覆
      tool_call            - 需要呼叫工具
      process_orchestration - 需要協調複雜流程（PDCA/BPA/CA）
    """
    doc: dict[str, object] = {
        "_key": intent_id,
        "intent_id": intent_id,
        "agent_scope": ORCH,
        "name": name,
        "description": description,
        "intent_type": intent_type,
        "domain": domain,
        "capabilities": capabilities,
        "nl_examples": nl_examples,
        "confidence_threshold": confidence_threshold,
        "priority": priority,
        "status": "enabled",
        "created_at": TS,
        "updated_at": TS,
        "updated_by": "system",
    }
    if bpa_id:
        doc["bpa_id"] = bpa_id
    if task_type:
        doc["task_type"] = task_type
    if response_strategy:
        doc["response_strategy"] = response_strategy
    if action_type:
        doc["action_type"] = action_type
    if target_agent:
        doc["target_agent"] = target_agent
    if tool_category:
        doc["tool_category"] = tool_category
    if tool_name:
        doc["tool_name"] = tool_name
    if pdca_id:
        doc["pdca_id"] = pdca_id
    if ca_id:
        doc["ca_id"] = ca_id
    if nl_patterns:
        doc["nl_patterns"] = nl_patterns
    return doc
