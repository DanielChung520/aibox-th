"""
@file        seed_llm_providers.py
@description 將 LLM Provider 及已啟用模型清單寫入 ArangoDB system_params
             供工具市集「LLM 模型」下拉選單使用
@lastUpdate  2026-05-01 00:00:00
@author      Sisyphus
@version     1.0.0
"""

import json
import httpx
from datetime import datetime, timezone

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = ("root", "abc_desktop_2026")
COLLECTION = "system_params"

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ── Provider 清冊：name → connection info ──────────────────────────
# 各工具執行時根據 provider name 查找 base_url / api_key
LLM_PROVIDERS = json.dumps(
    {
        "ollama": {
            "label": "Ollama",
            "base_url": "http://localhost:11434",
            "api_key_param": None,
        },
        "deepseek": {
            "label": "DeepSeek",
            "base_url": "https://api.deepseek.com/v1/chat/completions",
            "api_key_param": "report.llm_api_key",
        },
    },
    ensure_ascii=False,
)

# ── 已啟用模型清單：前端下拉選單選項 ────────────────────────────
# 每筆含 provider、實際 model name、UI 顯示 label
LLM_ACTIVATED_MODELS = json.dumps(
    [
        {"provider": "deepseek", "model": "deepseek-v4-flash", "label": "DeepSeek V4 Flash"},
        {"provider": "ollama", "model": "gemma4:31b", "label": "Gemma 4 31B"},
        {"provider": "ollama", "model": "qwen3-coder:30b", "label": "Qwen3 Coder 30B"},
        {"provider": "ollama", "model": "llama3.2:latest", "label": "Llama 3.2"},
        {"provider": "ollama", "model": "qwen3.5:0.8b", "label": "Qwen3.5 0.8B"},
    ],
    ensure_ascii=False,
)

PARAMS: list[dict] = [
    {
        "_key": "llm.providers",
        "param_key": "llm.providers",
        "param_value": LLM_PROVIDERS,
        "param_type": "json",
        "category": "llm",
        "description": "LLM Provider 連線設定，key=provider name, value={base_url, api_key_param}",
        "updated_at": NOW,
    },
    {
        "_key": "llm.activated_models",
        "param_key": "llm.activated_models",
        "param_value": LLM_ACTIVATED_MODELS,
        "param_type": "json",
        "category": "llm",
        "description": "已啟用模型清單，供前端下拉選單使用",
        "updated_at": NOW,
    },
]


def upsert_param(client: httpx.Client, doc: dict) -> None:
    key = doc["_key"]
    aql = """
    UPSERT { _key: @key }
    INSERT @doc
    UPDATE @doc
    IN system_params
    RETURN { action: OLD ? 'updated' : 'inserted', _key: NEW._key }
    """
    resp = client.post(
        f"{ARANGO_URL}/_db/{DB}/_api/cursor",
        json={"query": aql, "bindVars": {"key": key, "doc": doc}},
        auth=AUTH,
    )
    result = resp.json()
    if resp.status_code not in (200, 201) or result.get("error"):
        print(f"  ✗ {key}: {result}")
    else:
        action = result["result"][0]["action"] if result.get("result") else "?"
        print(f"  ✓ {key} [{action}]")


def main() -> None:
    print(f"=== Seed LLM Providers → ArangoDB ({DB}.{COLLECTION}) ===")
    with httpx.Client(timeout=15.0) as client:
        for doc in PARAMS:
            upsert_param(client, doc)
    print("✅ Done — LLM providers seeded.")


if __name__ == "__main__":
    main()
