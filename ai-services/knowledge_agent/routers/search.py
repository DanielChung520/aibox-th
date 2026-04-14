from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx

router = APIRouter(tags=["Knowledge Search"])

OLLAMA_BASE_URL = "http://localhost:11434"
ARANGO_URL = "http://localhost:8529"
ARANGO_DB = "abc_desktop"
ARANGO_USER = "root"
ARANGO_PASSWORD = "abc_desktop_2026"


class KnowledgeRequest(BaseModel):
    query: str
    collection: Optional[str] = "knowledge"
    limit: Optional[int] = 5


class Document(BaseModel):
    key: str = ""
    content: str
    source: Optional[str] = None
    metadata: Optional[dict[str, object]] = None


class KnowledgeResponse(BaseModel):
    query: str
    results: list[Document]
    context: str
    answer: Optional[str] = None


async def get_embedding(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={"model": "bge-m3:latest", "input": text},
        )
        response.raise_for_status()
        data = response.json()
        embeddings = data.get("embeddings", [])
        if embeddings and len(embeddings) > 0:
            return list(embeddings[0])
        return []


async def search_similar(collection: str, limit: int) -> list[dict[str, object]]:
    aql = f"FOR doc IN {collection} SORT BM25(doc) DESC LIMIT {limit} RETURN doc"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": aql},
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
        response.raise_for_status()
        data = response.json()
        return data.get("result", [])


async def generate_answer(query: str, context: str) -> str:
    from knowledge_agent.main import DEFAULT_MODEL

    prompt = (
        f"Based on the following knowledge base context, "
        f"answer the user's question.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\nAnswer:"
    )
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": DEFAULT_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": 0.5,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "").strip()


@router.post("/search", response_model=KnowledgeResponse)
async def search(request: KnowledgeRequest) -> KnowledgeResponse:
    try:
        results = await search_similar(request.collection or "knowledge", request.limit or 5)

        if not results:
            return KnowledgeResponse(
                query=request.query,
                results=[],
                context="",
                answer="No relevant knowledge found.",
            )

        context_parts: list[str] = []
        documents: list[Document] = []

        for doc in results:
            content = str(doc.get("content", ""))
            context_parts.append(content)
            documents.append(
                Document(
                    key=str(doc.get("_key", "")),
                    content=content,
                    source=str(doc.get("source", "")) or None,
                    metadata=None,
                )
            )

        context = "\n\n".join(context_parts)
        answer = await generate_answer(request.query, context)

        return KnowledgeResponse(
            query=request.query,
            results=documents,
            context=context,
            answer=answer,
        )

    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Service unavailable: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add")
async def add_document(
    collection: str, content: str, source: Optional[str] = None
) -> dict[str, object]:
    doc = {
        "content": content,
        "source": source or "manual",
        "created_at": "2026-03-23",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/{collection}",
            json=doc,
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
        response.raise_for_status()
        return response.json()


@router.get("/collections")
async def list_collections() -> dict[str, object]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/collection",
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
        response.raise_for_status()
        return response.json()
