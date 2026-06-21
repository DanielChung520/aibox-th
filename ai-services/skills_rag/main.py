import asyncio
import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel

app = FastAPI(title="SkillsRAG Service", version="1.0.0")

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")
QDRANT_COLLECTION = "action_skills"
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:6500")


class SkillSearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SkillSearchResult(BaseModel):
    skill_no: str
    title: str
    content: str
    score: float
    metadata: dict[str, Any] = {}


class SkillSearchResponse(BaseModel):
    results: list[SkillSearchResult]


async def _ensure_qdrant_collection():
    async with httpx.AsyncClient(timeout=5.0) as c:
        resp = await c.get(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}")
        if resp.status_code == 404:
            await c.put(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}", json={
                "vectors": {"size": 1024, "distance": "Cosine"},
            })


async def _embed(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30.0) as c:
        resp = await c.post(f"{OLLAMA_URL}/v1/embeddings", json={
            "model": EMBED_MODEL, "input": text,
        })
        resp.raise_for_status()
        data = resp.json()
        return data.get("embeddings", [data.get("embedding", [])])[0]


@app.on_event("startup")
async def startup():
    await _ensure_qdrant_collection()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "skills_rag"}


@app.post("/upload", summary="上傳 skill.md 並索引到 SkillsRAG")
async def upload_skill(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="僅支援 .md 檔案")

    content = await file.read()
    text = content.decode("utf-8")

    # Parse YAML frontmatter
    metadata: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            front = parts[1].strip()
            body = parts[2].strip()
            for line in front.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    metadata[k.strip()] = v.strip().strip('"').strip("'")

    skill_no = metadata.get("skill_no") or metadata.get("id") or file.filename.replace(".md", "")
    title = metadata.get("title") or metadata.get("name") or skill_no

    # Chunk: split by ## headings
    chunks = []
    current_section = "前言"
    current_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if current_lines:
                chunks.append((current_section, "\n".join(current_lines).strip()))
            current_section = line.strip("# ")
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        chunks.append((current_section, "\n".join(current_lines).strip()))

    # Embed and index to Qdrant
    async with httpx.AsyncClient(timeout=60.0) as c:
        for i, (section, chunk_text) in enumerate(chunks):
            if not chunk_text:
                continue
            emb = await _embed(f"{title} {section} {chunk_text[:512]}")
            point = {
                "id": f"{skill_no}_{i}",
                "vector": emb,
                "payload": {
                    "skill_no": skill_no,
                    "title": title,
                    "section": section,
                    "content": chunk_text,
                    "metadata": metadata,
                },
            }
            await c.put(
                f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points",
                json={"points": [point]},
            )

    # Save to ArangoDB action_scripts
    async with httpx.AsyncClient(timeout=5.0) as c:
        await c.post(
            f"{GATEWAY_URL}/api/v1/action-scripts",
            json={
                "skill_no": skill_no,
                "title": title,
                "name": title,
                "skill_type": metadata.get("skill_type", "tool"),
                "description": metadata.get("description", ""),
                "tags": [t.strip() for t in metadata.get("tags", "").split(",") if t.strip()],
                "steps": body.splitlines(),
                "guardrails": [g.strip() for g in metadata.get("guardrails", "").split(",") if g.strip()],
                "version": metadata.get("version", "1.0.0"),
                "status": "live",
            },
        )

    return {
        "skill_no": skill_no,
        "title": title,
        "chunks": len(chunks),
        "status": "indexed",
    }


@app.post("/match", response_model=SkillSearchResponse)
async def match_skill(req: SkillSearchRequest):
    emb = await _embed(req.query)
    async with httpx.AsyncClient(timeout=10.0) as c:
        resp = await c.post(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/search",
            json={
                "vector": emb,
                "limit": req.top_k,
                "with_payload": True,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for pt in data.get("result", []):
        payload = pt.get("payload", {})
        results.append(SkillSearchResult(
            skill_no=payload.get("skill_no", ""),
            title=payload.get("title", ""),
            content=payload.get("content", ""),
            score=pt.get("score", 0),
            metadata=payload.get("metadata", {}),
        ))

    return SkillSearchResponse(results=results)


@app.get("/skills", summary="列出所有已索引的技能")
async def list_skills():
    async with httpx.AsyncClient(timeout=10.0) as c:
        resp = await c.post(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/scroll",
            json={"limit": 100, "with_payload": True},
        )
        resp.raise_for_status()
        data = resp.json()

    seen = set()
    skills = []
    for pt in data.get("result", []):
        payload = pt.get("payload", {})
        sno = payload.get("skill_no", "")
        if sno not in seen:
            seen.add(sno)
            skills.append({"skill_no": sno, "title": payload.get("title", "")})
    return {"skills": skills}


@app.post("/sync/{skill_no}", summary="同步指定技能到 Qdrant")
async def sync_skill(skill_no: str):
    async with httpx.AsyncClient(timeout=10.0) as c:
        resp = await c.get(f"{GATEWAY_URL}/api/v1/action-scripts/by-no/{skill_no}")
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Skill {skill_no} not found")
        resp.raise_for_status()
        skill_data = resp.json().get("data", {})

    title = skill_data.get("title") or skill_data.get("name", "")
    steps_raw = skill_data.get("steps", [])
    goal = skill_data.get("goal", "")
    description = skill_data.get("description", "")
    guardrails = skill_data.get("guardrails", [])

    chunks = []
    for i, step_str in enumerate(steps_raw):
        step_title = f"步驟 {i+1}"
        step_content = step_str
        try:
            parsed = json.loads(step_str)
            if isinstance(parsed, dict):
                step_title = parsed.get("title", step_title) or step_title
                desc = parsed.get("description", "")
                prompt = parsed.get("prompt", "")
                parts = [p for p in [step_title, desc, prompt] if p]
                step_content = ": ".join(parts) if len(parts) > 1 else parts[0]
        except (json.JSONDecodeError, TypeError):
            pass
        chunks.append((step_title, step_content))

    async with httpx.AsyncClient(timeout=60.0) as c:
        scroll_resp = await c.post(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/scroll",
            json={
                "limit": 100,
                "with_payload": True,
                "filter": {"must": [{"key": "skill_no", "match": {"value": skill_no}}]},
            },
        )
        if scroll_resp.status_code == 200:
            existing = scroll_resp.json().get("result", [])
            existing_ids = [pt["id"] for pt in existing]
            if existing_ids:
                await c.post(
                    f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/delete",
                    json={"points": existing_ids},
                )

        for i, (section, chunk_text) in enumerate(chunks):
            if not chunk_text:
                continue
            emb = await _embed(f"{title} {section} {description} {chunk_text[:512]}")
            point = {
                "id": f"{skill_no}_{i}",
                "vector": emb,
                "payload": {
                    "skill_no": skill_no,
                    "title": title,
                    "section": section,
                    "content": chunk_text,
                    "metadata": {
                        "skill_no": skill_no,
                        "title": title,
                        "goal": goal,
                        "guardrails": guardrails,
                    },
                },
            }
            await c.put(
                f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points",
                json={"points": [point]},
            )

    sync_at = datetime.now(timezone.utc).isoformat()
    async with httpx.AsyncClient(timeout=5.0) as c:
        await c.patch(
            f"{GATEWAY_URL}/api/v1/action-scripts/by-no/{skill_no}",
            json={"last_sync_at": sync_at},
        )

    return {
        "skill_no": skill_no,
        "chunks": len(chunks),
        "sync_at": sync_at,
    }


@app.post("/check/{skill_no}", summary="檢查技能完整性")
async def check_skill(skill_no: str):
    async with httpx.AsyncClient(timeout=10.0) as c:
        skill_resp = await c.get(f"{GATEWAY_URL}/api/v1/action-scripts/by-no/{skill_no}")
        if skill_resp.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Skill {skill_no} not found")
        skill_data = skill_resp.json().get("data", {})

        tools_resp = await c.get(f"{GATEWAY_URL}/api/v1/tools")
        tools_data = tools_resp.json().get("data", []) if tools_resp.status_code == 200 else []

        agents_resp = await c.get(f"{GATEWAY_URL}/api/v1/agents")
        agents_data = agents_resp.json().get("data", []) if agents_resp.status_code == 200 else []

    # Use CHECK_MODEL env var, fallback to a known-good model for evaluation
    check_model = os.getenv("CHECK_MODEL", "llama3.2:latest")
    asyncio.create_task(_run_check(skill_no, skill_data, tools_data, agents_data, check_model))

    return {"status": "checking", "skill_no": skill_no}


async def _run_check(
    skill_no: str,
    skill_data: dict,
    tools: list,
    agents: list,
    model: str,
):
    try:
        title = skill_data.get("title") or skill_data.get("name", "")
        description = skill_data.get("description", "")
        steps = skill_data.get("steps", [])
        guardrails = skill_data.get("guardrails", [])
        goal = skill_data.get("goal", "")

        tool_names = [t.get("name", "") for t in tools]
        agent_names = [a.get("name", "") for a in agents]

        prompt = f"""You are a skill evaluator. Analyze the following skill and provide structured feedback.

Skill Title: {title}
Description: {description}
Goal: {goal}
Steps: {json.dumps(steps, ensure_ascii=False)}
Guardrails: {json.dumps(guardrails, ensure_ascii=False)}

Available Tools: {json.dumps(tool_names, ensure_ascii=False)}
Available Agents: {json.dumps(agent_names, ensure_ascii=False)}

Evaluate on FOUR dimensions:

1. Design Quality — Is this skill a single coherent process?
   - Does the goal describe multiple UNRELATED capabilities? (e.g., "query items OR check order status")
   - Is the description aligned with the goal?
   - Is the goal specific enough to derive concrete steps?

2. Completeness — Are steps, goal, and guardrails clearly defined?

3. Feasibility — Logical ordering, dependency handling, error paths?

4. Resource Availability — Do referenced tools/agents exist in the system?

Status rules (strictly follow these thresholds):
- "failed": Any dimension score < 5, OR critical issues (e.g. goal has multiple unrelated capabilities)
- "warning": All scores >= 5 but any score < 7, OR non-critical issues exist (e.g. missing error handling, unclear step ordering, missing resources)
- "passed": ALL scores >= 7 AND no unresolved issues

Respond in JSON only:
{{
    "design": {{"score": 0-10, "issues": [], "suggestions": []}},
    "completeness": {{"score": 0-10, "issues": [], "suggestions": []}},
    "feasibility": {{"score": 0-10, "issues": [], "suggestions": []}},
    "resources": {{"score": 0-10, "missing": [], "available": []}},
    "summary": "...",
    "status": "passed" | "failed" | "warning"
}}"""

        # Use subprocess+curl instead of httpx/urllib to avoid DNS/connectivity issues
        try:
            import subprocess
            req_data = json.dumps({"model": model, "prompt": prompt, "stream": False})
            curl_args = ["curl", "-s", "--max-time", "120",
                f"{OLLAMA_URL}/api/generate",
                "-d", req_data]
            curl_result = subprocess.run(curl_args, capture_output=True, text=True, timeout=130)
            if curl_result.returncode != 0:
                raise RuntimeError(f"curl failed (exit {curl_result.returncode}): {curl_result.stderr[:200]}")
            ollama_response = json.loads(curl_result.stdout)
            response_text = ollama_response.get("response", "{}")
        except Exception as curl_e:
            logging.error(f"Ollama call failed: {curl_e}")
            raise

        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError:
            parsed = {"status": "failed", "summary": "Failed to parse LLM response"}

        check_status = parsed.get("status", "failed")
        check_at = datetime.now(timezone.utc).isoformat()

        async with httpx.AsyncClient(timeout=5.0) as c:
            await c.patch(
                f"{GATEWAY_URL}/api/v1/action-scripts/by-no/{skill_no}",
                json={
                    "check_status": check_status,
                    "last_check_at": check_at,
                    "check_result": parsed,
                },
            )
    except Exception as exc:
        logging.error(f"Check error for {skill_no}: {exc}", exc_info=True)
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                await c.patch(
                    f"{GATEWAY_URL}/api/v1/action-scripts/by-no/{skill_no}",
                    json={
                        "check_status": "failed",
                        "last_check_at": datetime.now(timezone.utc).isoformat(),
                        "check_result": {"status": "failed", "summary": "LLM call failed"},
                    },
                )
        except Exception:
            pass
