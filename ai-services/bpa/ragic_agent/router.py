import logging, os, time, httpx
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Ragic Agent"])
_conversations: dict[str, list[dict[str, str]]] = {}
MAX_TURNS = 10
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")

# Defaults (fallback when no agent_key)
FALLBACK_MODEL = os.getenv("RAGIC_AGENT_MODEL", "qwen3-next:latest")
FALLBACK_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
FALLBACK_SYSTEM_PROMPT = "你是一個專業的 Ragic 操作助手，專注於回答使用者關於 Ragic 軟體的操作問題。請用繁體中文回答，提供具體步驟。"


class ChatRequest(BaseModel):
    session_id: str
    message: str
    user_id: str = "anonymous"
    agent_key: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    sources: list[str] = []


async def query_arango(aql: str, bind_vars: dict | None = None) -> list[dict]:
    auth_cred = f"{ARANGO_USER}:{ARANGO_PASSWORD}"
    import base64
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(auth_cred.encode()).decode()}",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": aql, "bindVars": bind_vars or {}},
            headers=headers,
        )
        if resp.status_code not in (200, 201):
            return []
        return resp.json().get("result", [])


async def resolve_llm_config(agent_key: str | None) -> tuple[str, str, str, str]:
    model = FALLBACK_MODEL
    api_base = FALLBACK_OLLAMA_URL
    system_prompt = FALLBACK_SYSTEM_PROMPT
    api_key = ""

    if not agent_key:
        return model, api_base, system_prompt, api_key

    agents = await query_arango(
        "FOR a IN agents FILTER a._key == @key LIMIT 1 RETURN a",
        {"key": agent_key},
    )
    if not agents:
        return model, api_base, system_prompt, api_key

    agent = agents[0]
    agent_model = agent.get("llm_model") or ""
    if agent_model:
        model = agent_model
    agent_prompt = agent.get("system_prompt") or ""
    if agent_prompt:
        system_prompt = agent_prompt

    providers = await query_arango(
        "FOR p IN model_providers FILTER p.status == 'enabled' RETURN p",
    )
    for p in providers:
        p_models = p.get("models") or []
        for m in p_models:
            if isinstance(m, dict) and m.get("model_id") == model:
                api_base = (p.get("base_url") or "").rstrip("/")
                api_key = p.get("api_key") or ""
                break
        if api_base != FALLBACK_OLLAMA_URL:
            break

    return model, api_base, system_prompt, api_key


async def call_llm(messages: list[dict], model: str, api_base: str, api_key: str = "") -> str:
    if "localhost" in api_base or "127.0.0.1" in api_base:
        url = f"{api_base}/api/chat"
        payload = {"model": model, "messages": messages, "stream": False}
        async with httpx.AsyncClient(timeout=180.0) as c:
            r = await c.post(url, json=payload)
            if r.status_code == 200:
                return str(r.json().get("message", {}).get("content", ""))
    else:
        url = f"{api_base}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {"model": model, "messages": messages, "stream": False}
        async with httpx.AsyncClient(timeout=180.0) as c:
            r = await c.post(url, json=payload, headers=headers)
            if r.status_code == 200:
                choices = r.json().get("choices", [])
                if choices:
                    return str(choices[0].get("message", {}).get("content", ""))
    return "抱歉，暫時無法處理您的請求。"


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    start = time.monotonic()
    msg = request.message
    sid = request.session_id
    agent_key = request.agent_key
    history = _conversations.get(sid, [])

    # 基本內建能力：時間查詢
    from datetime import datetime, timezone
    time_keywords = ["時間", "幾點", "日期", "今天幾號", "星期幾", "現在", "time", "date"]
    if any(k in msg for k in time_keywords):
        now = datetime.now(timezone.utc).astimezone()
        tw_now = now.astimezone(__import__('zoneinfo', fromlist=['']).ZoneInfo('Asia/Taipei'))
        time_reply = f"現在時間是 {tw_now.strftime('%Y年%m月%d日 %H:%M:%S')}（台灣時間，UTC+8）"
        history.append({"role": "user", "content": msg})
        history.append({"role": "assistant", "content": time_reply})
        _conversations[sid] = history[-MAX_TURNS * 2:]
        return ChatResponse(session_id=sid, reply=time_reply, sources=[])

    # 從 bot_chat_sessions 載入持久化上下文
    try:
        from shared.conversation import QueryEngine
        engine = QueryEngine()
        # 取足夠多的歷史，再取最新 N 條（get_history 是 ASC 排序）
        db_all = await engine.get_history(sid, limit=100, include_metadata=False)
        if db_all:
            history = db_all[-MAX_TURNS * 2:]  # 最新 20 條
    except Exception:
        pass

    is_ragic = any(kw in msg for kw in ["Ragic", "表單", "欄位", "新增", "修改", "刪除", "查詢", "匯出", "報表", "權限", "篩選"])
    is_complaint = any(kw in msg for kw in ["抱怨", "客訴", "不滿"])

    ka = []
    if is_ragic:
        ka_url = os.getenv("KNOWLEDGE_AGENT_URL", "http://127.0.0.1:8011/ka")
        kb_root = os.getenv("RAGIC_KB_ROOT_ID", "kb_1776656567810")
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.post(f"{ka_url.rstrip('/')}/hybrid/search",
                                 json={"query": msg, "top_k": 2, "root_id": kb_root})
                if r.status_code == 200:
                    ka = r.json().get("results", [])
        except Exception:
            pass

    model, api_base, system_prompt, api_key = await resolve_llm_config(agent_key)

    msgs = [{"role": "system", "content": system_prompt}]
    if ka:
        context = "; ".join(str(i.get("content", ""))[:150] for i in ka[:2])
        msgs.append({"role": "system", "content": f"相關知識：{context}"})
    if is_complaint:
        msgs = [{"role": "system", "content": "溫暖回應抱怨，簡短。"}, {"role": "user", "content": msg}]
    else:
        msgs.extend(history[-MAX_TURNS:])
        msgs.append({"role": "user", "content": msg})

    reply = await call_llm(msgs, model, api_base, api_key)

    history.append({"role": "user", "content": msg})
    history.append({"role": "assistant", "content": reply})
    _conversations[sid] = history[-MAX_TURNS * 2:]
    logger.info(f"[Ragic] agent_key={agent_key} model={model} ka={len(ka)} reply_len={len(reply)} elapsed={time.monotonic()-start:.1f}s")
    return ChatResponse(session_id=sid, reply=reply, sources=[])
