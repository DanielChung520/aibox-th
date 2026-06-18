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


@app.task(bind=True, max_retries=1)  # type: ignore[misc]
def generate_report_task(
    self: Any,
    report_key: str,
    params: dict[str, Any],
    gateway_url: str = "http://localhost:6500",
) -> dict[str, Any]:
    import asyncio
    import httpx
    from datetime import datetime, timezone

    from tools.report_generator.llm_analyzer import analyze_and_generate
    from tools.report_generator.html_generator import generate_report_html
    from tools.report_generator.seaweedfs_client import seaweed_client

    def _patch_report(payload: dict[str, Any]) -> None:
        try:
            with httpx.Client(timeout=10.0) as client:
                client.patch(
                    f"{gateway_url}/api/v1/da/schema-reports/{report_key}",
                    json=payload,
                )
        except Exception:
            pass

    try:
        llm_result = asyncio.run(analyze_and_generate(
            dataset=params["dataset"],
            report_goal=params["report_goal"],
            preferred_chart=params.get("preferred_chart"),
            domain_context=params.get("knowledge_domain"),
            field_hints=params.get("field_hints"),
            special_notes=params.get("special_notes"),
        ))

        title = params.get("title") or params["report_goal"][:30]

        html_content = generate_report_html(
            title=title,
            chart_data=llm_result["chart_data"],
            chart_type=llm_result["chart_type"],
            analysis_summary=llm_result["analysis_summary"],
            author=params.get("author", "system"),
            hints=params.get("hints"),
            legend_show=params.get("legend_show", True),
            legend_position=params.get("legend_position", "bottom"),
        )

        upload_result = asyncio.run(seaweed_client.upload_html(
            html_content=html_content,
            username=params.get("username", "anonymous"),
            title=title,
        ))

        _patch_report({
            "status": "completed",
            "report_url": upload_result.get("url"),
            "chart_type": llm_result["chart_type"],
            "analysis_summary": llm_result["analysis_summary"],
            "size_bytes": upload_result.get("size"),
            "filename": upload_result.get("filename"),
        })

        return {"report_key": report_key, "status": "completed"}

    except Exception as e:
        _patch_report({
            "status": "error",
            "error_message": str(e)[:500],
        })
        raise


@app.task(bind=True, max_retries=1)  # type: ignore[misc]
def check_scheduled_reports(self: Any) -> dict[str, Any]:
    import json as _json
    import httpx
    from datetime import datetime

    ARANGO_URL = "http://localhost:8529"
    ARANGO_DB = "abc_desktop"
    ARANGO_AUTH = ("root", "abc_desktop_2026")
    GATEWAY = "http://localhost:6500"

    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_dow = now.weekday()  # 0=Mon ... 6=Sun  → map to 0=Sun..6=Sat

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={
                    "query": (
                        "FOR r IN schema_reports "
                        "FILTER r.schedule_type != null "
                        "FILTER r.schedule_time != null "
                        "FILTER r.status != 'generating' "
                        "RETURN r"
                    ),
                },
                auth=ARANGO_AUTH,
            )
            resp.raise_for_status()
            reports = resp.json().get("result", [])
    except Exception:
        return {"scheduled": 0, "triggered": 0}

    triggered = 0
    for r in reports:
        sched_type = r.get("schedule_type")
        sched_time = r.get("schedule_time")
        if sched_time != current_time:
            continue

        if sched_type == "weekly":
            sched_days = r.get("schedule_days", [])
            if current_dow not in sched_days:
                continue

        schedule_params_raw = r.get("schedule_params")
        if not schedule_params_raw:
            continue
        try:
            sched_params = _json.loads(schedule_params_raw) if isinstance(schedule_params_raw, str) else schedule_params_raw
        except Exception:
            continue

        table_id = r.get("table_id", "unknown")
        username = r.get("username", "anonymous")

        try:
            with httpx.Client(timeout=30.0) as client:
                data_resp = client.get(
                    f"{GATEWAY}/api/v1/da/ragic/proxy/{table_id}/data?offset=0&limit=100",
                    timeout=30.0,
                )
                if data_resp.status_code != 200:
                    continue
                ragic_data = data_resp.json().get("data", {})
                raw_rows = ragic_data.get("rows", [])
                fields = ragic_data.get("fields", [])

            field_map = {}
            for f in fields:
                if f.get("field_id") and f.get("field_name"):
                    field_map[f["field_id"]] = f["field_name"]

            dataset = []
            for row in raw_rows:
                mapped = {}
                for k, v in row.items():
                    mapped[field_map.get(k, k)] = v
                dataset.append(mapped)

            if not dataset:
                continue

            new_report_name = sched_params.get("report_goal", "排程報表")[:20]
            with httpx.Client(timeout=10.0) as client:
                create_resp = client.post(
                    f"{GATEWAY}/api/v1/da/schema-reports",
                    json={
                        "table_id": table_id,
                        "report_name": new_report_name,
                        "username": username,
                        "status": "generating",
                    },
                )
                if create_resp.status_code not in (200, 201):
                    continue
                new_report = create_resp.json().get("data", {})

            generate_report_task.delay(
                report_key=new_report["_key"],
                params={
                    "dataset": dataset,
                    "report_goal": sched_params.get("report_goal", new_report_name),
                    "preferred_chart": sched_params.get("preferred_chart"),
                    "field_hints": sched_params.get("field_hints"),
                    "special_notes": sched_params.get("special_notes"),
                    "legend_show": sched_params.get("legend_show", True),
                    "legend_position": sched_params.get("legend_position", "bottom"),
                    "hints": sched_params.get("hints"),
                    "title": sched_params.get("report_goal", "")[:30],
                    "author": "schedule",
                    "username": username,
                    "table_id": table_id,
                },
                gateway_url=GATEWAY,
            )
            triggered += 1
        except Exception:
            continue

    return {"scheduled": len(reports), "triggered": triggered}


@app.task(bind=True, max_retries=1, acks_late=True)
def market_intel_refresh(self, keywords: list[str] | None = None) -> dict:
    """Celery 任務：市場觀察搜尋+摘要+儲存（背景執行，可監控狀態）"""
    import asyncio
    from market_intel.scraper import search, fetch_page_content
    from market_intel.summarizer import summarize_article, generate_daily_report, reset_token_usage, get_token_usage
    from datetime import datetime, timezone, date
    import httpx

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    reset_token_usage()

    try:
        results = loop.run_until_complete(search(keywords=keywords))
        if not results:
            return {"status": "no_results"}

        items = []
        for i, r in enumerate(results[:8]):
            self.update_state(state="PROGRESS", meta={"step": f"fetching {i+1}/{len(results[:8])}"})
            content = loop.run_until_complete(fetch_page_content(r.url))
            analysis = loop.run_until_complete(summarize_article(r.title, content))
            items.append({
                "title": r.title, "url": r.url, "source": r.source,
                "summary": analysis.get("summary", r.snippet[:200]),
                "relevance": analysis.get("relevance", "medium"),
                "action": analysis.get("action"),
                "impact": analysis.get("impact", "neutral"),
            })

        self.update_state(state="PROGRESS", meta={"step": "analyzing"})
        report_data = loop.run_until_complete(generate_daily_report(items))

        today = date.today().isoformat()
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        report_key = f"report_{today}_{ts}"
        doc = {
            "_key": report_key, "date": today, "items": items,
            "daily_focus": report_data.get("daily_focus", ""),
            "key_trends": report_data.get("key_trends", []),
            "attention_points": report_data.get("attention_points", []),
            "opportunities": report_data.get("opportunities", []),
            "overall_assessment": report_data.get("overall_assessment", ""),
            "token_usage": get_token_usage(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "task_id": self.request.id,
        }

        # 寫入 ArangoDB（每次建立新記錄，保留歷史）
        import base64
        auth_b64 = base64.b64encode(b"root:abc_desktop_2026").decode()
        headers = {"Authorization": f"Basic {auth_b64}", "Content-Type": "application/json"}
        with httpx.Client(timeout=20) as client:
            client.post(
                "http://localhost:8529/_db/abc_desktop/_api/document/market_intel_reports",
                json=doc, headers=headers,
            )

        return {"status": "completed", "items_count": len(items), "token_usage": get_token_usage()}

    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        loop.close()
