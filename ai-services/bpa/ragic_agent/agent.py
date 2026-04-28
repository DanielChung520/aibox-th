import time, logging, httpx
from bpa.ragic_agent.config import KNOWLEDGE_AGENT_URL, OLLAMA_BASE_URL, RAGIC_KB_ROOT_ID, RAGIC_MODEL, SYSTEM_PROMPT

logger = logging.getLogger(__name__)
_client = httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0))
_conversations: dict[str, list[dict[str, str]]] = {}
MAX_TURNS = 20

def _search_hybrid_rag(query: str) -> list[dict[str, str]]:
    try:
        resp = _client.post(f"{KNOWLEDGE_AGENT_URL.rstrip('/')}/hybrid/search", json={"query": query, "top_k": 3, "root_id": RAGIC_KB_ROOT_ID})
        if resp.status_code == 200: return resp.json().get("results", [])
    except Exception as e: logger.warning(f"KA: {type(e).__name__}")
    return []

def _call_ollama(messages: list[dict[str, str]]) -> str:
    try:
        t0 = time.monotonic()
        resp = _client.post(f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat", json={"model": RAGIC_MODEL, "messages": messages, "stream": False})
        logger.info(f"Ollama: {resp.status_code} in {time.monotonic()-t0:.1f}s")
        if resp.status_code == 200: return str(resp.json().get("message", {}).get("content", ""))
    except Exception as e: logger.error(f"Ollama {type(e).__name__}: {e}")
    return "抱歉，暫時無法處理您的請求。"

def chat_with_ragic_sync(session_id: str, user_message: str, user_id: str = "anonymous") -> dict[str, object]:
    start = time.monotonic()
    history = _conversations.get(session_id, [])
    is_ragic = any(kw in user_message for kw in ["Ragic","表單","欄位","新增","修改","查詢","匯出"])
    is_complaint = any(kw in user_message for kw in ["抱怨","客訴"])

    if is_complaint:
        reply = _call_ollama([{"role": "system", "content": "溫暖回應。"}, {"role": "user", "content": user_message}])
    elif is_ragic:
        results = _search_hybrid_rag(user_message)
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        if results:
            kb = "KA HybridRAG 結果：\n" + "\n".join(f"[{r.get('source','?')}]: {r.get('content','')[:200]}" for r in results[:3])
            msgs.append({"role": "system", "content": kb})
        msgs.extend(history[-MAX_TURNS:])
        msgs.append({"role": "user", "content": user_message})
        reply = _call_ollama(msgs)
    else:
        reply = _call_ollama([{"role": "system", "content": SYSTEM_PROMPT}, *history[-MAX_TURNS:], {"role": "user", "content": user_message}])

    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": reply})
    _conversations[session_id] = history[-MAX_TURNS * 2:]
    logger.info(f"[Ragic] reply_len={len(reply)} elapsed={time.monotonic()-start:.1f}s")
    return {"session_id": session_id, "reply": reply, "sources": []}
