from typing import Any

from celery_app.app import app


def _notify_session_webhook(session_key: str, file_id: str, arango: Any) -> None:
    import httpx
    import os

    arango_url = os.getenv("ARANGO_URL", "http://localhost:8529")
    arango_db = os.getenv("ARANGO_DATABASE", "abc_desktop")
    arango_user = os.getenv("ARANGO_USER", "root")
    arango_password = os.getenv("ARANGO_PASSWORD", "")
    api_base = "http://localhost:6500"

    graph_stats = None
    try:
        with httpx.Client(timeout=15.0) as client:
            file_resp = client.post(
                f"{arango_url}/_db/{arango_db}/_api/document/knowledge_files/{file_id}",
                auth=(arango_user, arango_password),
            )
            if file_resp.status_code == 200:
                file_doc = file_resp.json()
                vector_status = file_doc.get("vector_status", "completed")

                node_resp = client.post(
                    f"{arango_url}/_db/{arango_db}/_api/cursor",
                    auth=(arango_user, arango_password),
                    json={
                        "query": "RETURN LENGTH(FOR g IN knowledge_graphs FILTER g.file_id == @f RETURN 1)",
                        "bindVars": {"f": file_id},
                    },
                )
                edge_resp = client.post(
                    f"{arango_url}/_db/{arango_db}/_api/cursor",
                    auth=(arango_user, arango_password),
                    json={
                        "query": "RETURN LENGTH(FOR e IN knowledge_graph_edges FILTER e.file_id == @f RETURN 1)",
                        "bindVars": {"f": file_id},
                    },
                )
                nodes = (
                    node_resp.json().get("result", [0])[0]
                    if node_resp.status_code == 200
                    else 0
                )
                edges = (
                    edge_resp.json().get("result", [0])[0]
                    if edge_resp.status_code == 200
                    else 0
                )
                graph_stats = {"nodes": nodes, "edges": edges}

                client.post(
                    f"{api_base}/api/v1/chat/sessions/{session_key}/files/status-webhook",
                    json={
                        "file_key": file_id,
                        "vector_status": vector_status,
                        "graph_status": None,
                        "graph_stats": graph_stats,
                    },
                )
    except Exception:
        pass


@app.task(bind=True, max_retries=3)  # type: ignore[misc]
def vectorize_task(
    self: Any,
    file_id: str,
    local_path: str,
    root_id: str,
    session_key: str | None = None,
) -> dict[str, Any]:
    from kb_pipeline.pipeline import Pipeline

    pipeline = Pipeline()
    result = pipeline.vectorize(file_id, local_path, root_id)
    if session_key:
        _notify_session_webhook(session_key, file_id, None)
    return {"file_id": file_id, **result}


@app.task(bind=True, max_retries=3)  # type: ignore[misc]
def graph_task(
    self: Any, file_id: str, local_path: str, session_key: str | None = None
) -> dict[str, Any]:
    from kb_pipeline.arango_ops import ArangoOps

    arango = ArangoOps()

    if session_key:
        file_doc = arango.get_file(file_id)
        rid = file_doc.get("knowledge_root_id") if file_doc else None
        result = _extract_5w1h(file_id, local_path, arango, root_id=rid)
    else:
        from kb_pipeline.pipeline import Pipeline

        pipeline = Pipeline()
        result = pipeline.extract_graph(file_id, local_path)

    if session_key:
        import httpx
        import os

        arango_url = os.getenv("ARANGO_URL", "http://localhost:8529")
        arango_db = os.getenv("ARANGO_DATABASE", "abc_desktop")
        arango_user = os.getenv("ARANGO_USER", "root")
        arango_password = os.getenv("ARANGO_PASSWORD", "")
        api_base = "http://localhost:6500"
        graph_stats = None
        graph_status = "completed"
        failed_reason = None

        try:
            with httpx.Client(timeout=15.0) as client:
                file_resp = client.post(
                    f"{arango_url}/_db/{arango_db}/_api/document/knowledge_files/{file_id}",
                    auth=(arango_user, arango_password),
                )
                if file_resp.status_code == 200:
                    file_doc = file_resp.json()
                    graph_status = file_doc.get("graph_status", "completed")
                    failed_reason = file_doc.get("failed_reason")

                node_resp = client.post(
                    f"{arango_url}/_db/{arango_db}/_api/cursor",
                    auth=(arango_user, arango_password),
                    json={
                        "query": "RETURN LENGTH(FOR g IN knowledge_graphs FILTER g.file_id == @f RETURN 1)",
                        "bindVars": {"f": file_id},
                    },
                )
                edge_resp = client.post(
                    f"{arango_url}/_db/{arango_db}/_api/cursor",
                    auth=(arango_user, arango_password),
                    json={
                        "query": "RETURN LENGTH(FOR e IN knowledge_graph_edges FILTER e.file_id == @f RETURN 1)",
                        "bindVars": {"f": file_id},
                    },
                )
                nodes = (
                    node_resp.json().get("result", [0])[0]
                    if node_resp.status_code == 200
                    else 0
                )
                edges = (
                    edge_resp.json().get("result", [0])[0]
                    if edge_resp.status_code == 200
                    else 0
                )
                graph_stats = {"nodes": nodes, "edges": edges}

                client.post(
                    f"{api_base}/api/v1/chat/sessions/{session_key}/files/status-webhook",
                    json={
                        "file_key": file_id,
                        "vector_status": None,
                        "graph_status": graph_status,
                        "failed_reason": failed_reason,
                        "graph_stats": graph_stats,
                    },
                )
        except Exception:
            pass

    return {"file_id": file_id, **result}


def _extract_5w1h(file_id: str, local_path: str, arango: Any, root_id: str | None = None) -> dict[str, Any]:
    import json
    import os

    import httpx

    arango.update_status(file_id, graph_status="processing")

    raw_text = arango.read_file(file_id)
    if raw_text is None:
        raw_text = " ".join(arango.read_file_chunks(file_id))
    if not raw_text:
        arango.update_status(file_id, graph_status="completed")
        return {"entities": 0, "relations": 0, "status": "no_content"}

    PROMPT = (
        "從以下文本提取 5W1H 資訊，回覆嚴格 JSON 格式：\n"
        '{"who":"...","what":"...","when":"...","where":"...","why":"...","how":"..."}\n\n'
        f"文本：\n{raw_text[:3000]}"
    )

    model = os.getenv("OLLAMA_LLM_MODEL", "llama3.2:latest")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": PROMPT,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 512},
            },
        )
        resp.raise_for_status()
        content = resp.json().get("response", "").strip()

    if not content:
        arango.update_status(
            file_id, graph_status="failed", failed_reason="empty LLM response"
        )
        return {"entities": 0, "relations": 0, "status": "failed"}

    try:
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end != -1:
            parsed = json.loads(content[start : end + 1])
        else:
            parsed = json.loads(content)
    except json.JSONDecodeError:
        arango.update_status(
            file_id, graph_status="failed", failed_reason="invalid JSON from LLM"
        )
        return {"entities": 0, "relations": 0, "status": "parse_failed"}

    type_map = {
        "who": "人物",
        "what": "事件",
        "when": "事件",
        "where": "地點",
        "why": "概念",
        "how": "技術",
    }
    nodes = [
        {"entity": str(v), "entity_type": type_map.get(k, "概念"), "description": k}
        for k, v in parsed.items()
        if v and str(v).strip() and str(v).strip() not in ("未知", "N/A", "null")
    ]

    if nodes:
        arango.upsert_graph(file_id, nodes, [], root_id=root_id)
        arango.update_status(file_id, graph_status="completed")
    else:
        arango.update_status(file_id, graph_status="completed")

    return {"entities": len(nodes), "relations": 0, "status": "completed"}


@app.task(bind=True, max_retries=3)  # type: ignore[misc]
def process_file_task(
    self: Any, file_id: str, local_path: str, root_id: str
) -> dict[str, Any]:
    from kb_pipeline.pipeline import Pipeline

    pipeline = Pipeline()
    v_result = pipeline.vectorize(file_id, local_path, root_id)
    g_result = pipeline.extract_graph(file_id, local_path)
    return {"file_id": file_id, "vector": v_result, "graph": g_result}
