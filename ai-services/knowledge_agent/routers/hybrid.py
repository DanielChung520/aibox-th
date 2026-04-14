from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/hybrid", tags=["HybridRAG"])


class HybridSearchRequest(BaseModel):
    query: str
    collection: Optional[str] = "knowledge_default"
    top_k: Optional[int] = 10
    strategy: Optional[str] = "hybrid"
    min_relevance: Optional[float] = 0.0
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    root_id: Optional[str] = None


class HybridSearchResult(BaseModel):
    content: str
    source: str
    score: float
    metadata: Optional[dict[str, object]] = None


class HybridSearchResponse(BaseModel):
    query: str
    query_type: str
    strategy: str
    weights_used: dict[str, float]
    results: list[HybridSearchResult]
    total_vector_hits: int
    total_graph_hits: int
    fusion_time_ms: int


@router.post("/search", response_model=HybridSearchResponse)
async def hybrid_search(request: HybridSearchRequest) -> HybridSearchResponse:
    from knowledge_agent.hybrid_rag import HybridRAGService

    service = HybridRAGService()
    result = await service.hybrid_search(
        query=request.query,
        collection=request.collection or "knowledge_default",
        top_k=request.top_k or 10,
        strategy=request.strategy or "hybrid",
        min_relevance=request.min_relevance or 0.0,
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        root_id=request.root_id,
    )

    return HybridSearchResponse(
        query=result["query"],
        query_type=result["query_type"],
        strategy=result["strategy"],
        weights_used=result["weights_used"],
        results=[
            HybridSearchResult(
                content=r["content"],
                source=r["source"],
                score=r["score"],
                metadata=r.get("metadata"),
            )
            for r in result["results"]
        ],
        total_vector_hits=result["total_vector_hits"],
        total_graph_hits=result["total_graph_hits"],
        fusion_time_ms=result["fusion_time_ms"],
    )


class HybridConfigUpdateRequest(BaseModel):
    query_type: str
    vector_weight: float
    graph_weight: float


@router.get("/config")
async def get_hybrid_config() -> dict[str, object]:
    from knowledge_agent.hybrid_rag import get_config_service

    service = get_config_service()
    config = service.get_config()
    return {"weights": config.to_dict(), "scope": "system"}


@router.put("/config")
async def update_hybrid_config(request: HybridConfigUpdateRequest) -> dict[str, object]:
    from knowledge_agent.hybrid_rag import get_config_service

    service = get_config_service()

    if not service.validate_weights(request.vector_weight, request.graph_weight):
        raise HTTPException(
            status_code=400,
            detail="Invalid weights: must be between 0-1 and sum to 1.0",
        )

    success = service.save_weights(
        query_type=request.query_type,
        vector_weight=request.vector_weight,
        graph_weight=request.graph_weight,
        changed_by="api",
    )

    if success:
        weights = service.get_weights(request.query_type)
        return {
            "status": "ok",
            "query_type": request.query_type,
            "weights": weights.to_dict(),
        }
    raise HTTPException(status_code=500, detail="Failed to save config")


@router.get("/health")
async def hybrid_health() -> dict[str, object]:
    from knowledge_agent.hybrid_rag import get_hybrid_rag_service

    service = get_hybrid_rag_service()
    return await service.health_check()
