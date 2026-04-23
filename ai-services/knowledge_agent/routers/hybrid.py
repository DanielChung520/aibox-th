from typing import Optional, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from shared.security import verify_internal_token
from shared.logging import get_structured_logger, log_hybrid_rag_request, log_knowledge_retrieval

router = APIRouter(
    prefix="/hybrid",
    tags=["HybridRAG"],
    dependencies=[Depends(verify_internal_token)],
)


class HybridSearchRequest(BaseModel):
    query: str
    collection: Optional[str] = "knowledge_default"
    top_k: Optional[int] = 10
    strategy: Optional[str] = "hybrid"
    min_relevance: Optional[float] = 0.0
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    root_id: Optional[str] = None
    user_role: Optional[str] = None


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
    from knowledge_agent import service as kms_service
    from knowledge_agent.hybrid_rag import HybridRAGService

    logger = get_structured_logger("knowledge_agent", "hybrid_rag")
    timer = log_hybrid_rag_request(
        logger,
        query=request.query,
        strategy=request.strategy or "hybrid",
        top_k=request.top_k or 10,
        user_id=request.user_id,
        root_id=request.root_id,
    )

    if request.root_id:
        try:
            kms = kms_service.get_knowledge_management_service()
            kms.check_access(request.root_id, request.user_role, operation="query")
        except ValueError as exc:
            timer.stop(success=False, error=str(exc))
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
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
            llm_provider="ollama",
            user_role=getattr(request, "user_role", None),
        )

        timer.stop(
            success=True,
            result_count=len(result["results"]),
            vector_hits=result["total_vector_hits"],
            graph_hits=result["total_graph_hits"],
        )

        log_knowledge_retrieval(
            logger,
            query=request.query,
            collection=request.collection or "knowledge_default",
            top_k=request.top_k or 10,
            hits=len(result["results"]),
            user_id=request.user_id,
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
                    metadata=cast(dict[str, object] | None, r.get("metadata")),
                )
                for r in result["results"]
            ],
            total_vector_hits=result["total_vector_hits"],
            total_graph_hits=result["total_graph_hits"],
            fusion_time_ms=result["fusion_time_ms"],
        )
    except Exception as exc:
        timer.stop(success=False, error=str(exc))
        raise


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


@router.post("/evidence")
async def evidence_search(request: dict) -> dict[str, object]:
    from knowledge_agent.hybrid_rag.models.inquiry import (
        Boundary,
        ContextSignals,
        EvidenceSearchRequest,
        Hypothesis,
        InquiryPlan,
        InquiryStrategy,
    )

    boundary = Boundary(
        root_id=request.get("boundary", {}).get("root_id", ""),
        allowed_roles=request.get("boundary", {}).get("allowed_roles", []),
        ontology_scope=request.get("boundary", {}).get("ontology_scope", {}),
        lifecycle_scope=request.get("boundary", {}).get("lifecycle_scope", []),
        usage_scope=request.get("boundary", {}).get("usage_scope", []),
        max_hops=request.get("boundary", {}).get("max_hops", 2),
        max_top_k=request.get("boundary", {}).get("max_top_k", 10),
        time_budget_ms=request.get("boundary", {}).get("time_budget_ms", 2000),
    )

    hyp_data = request.get("hypothesis", {})
    hypothesis = Hypothesis(
        hypothesis_id=hyp_data.get("hypothesis_id"),
        statement=hyp_data.get("statement", ""),
        candidate_anchors=hyp_data.get("candidate_anchors", []),
        required_evidence_types=hyp_data.get("required_evidence_types", []),
        falsifiable_by=hyp_data.get("falsifiable_by", []),
    )

    inquiry_plan = None
    if "inquiry_plan" in request and request["inquiry_plan"]:
        ip_data = request["inquiry_plan"]
        strategy_str = ip_data.get("strategy", "hybrid")
        try:
            strategy = InquiryStrategy(strategy_str)
        except ValueError:
            strategy = InquiryStrategy.HYBRID
        inquiry_plan = InquiryPlan(
            plan_id=ip_data.get("plan_id"),
            strategy=strategy,
            sub_questions=ip_data.get("sub_questions", []),
            allowed_channels=ip_data.get("allowed_channels", ["vector", "graph", "raw"]),
            stop_when=ip_data.get("stop_when", ["evidence_sufficient", "boundary_unclear", "budget_exhausted"]),
        )

    context_signals = None
    if "context_signals" in request and request["context_signals"]:
        cs_data = request["context_signals"]
        context_signals = ContextSignals(
            recent_action_trail=cs_data.get("recent_action_trail", []),
            active_page=cs_data.get("active_page"),
            active_table=cs_data.get("active_table"),
            current_working_set=cs_data.get("current_working_set", []),
            candidate_anchors=cs_data.get("candidate_anchors", []),
        )

    evidence_request = EvidenceSearchRequest(
        boundary=boundary,
        hypothesis=hypothesis,
        inquiry_plan=inquiry_plan,
        context_signals=context_signals,
        query=request.get("query", ""),
        user_role=request.get("user_role"),
    )

    from knowledge_agent import service as kms_service
    from knowledge_agent.hybrid_rag import HybridRAGService

    root_id = evidence_request.boundary.root_id
    if root_id:
        try:
            kms = kms_service.get_knowledge_management_service()
            kms.check_access(root_id, evidence_request.user_role, operation="query")
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    service = HybridRAGService()
    result = await service.evidence_search(evidence_request)
    return result.to_dict()


@router.get("/health")
async def hybrid_health() -> dict[str, object]:
    from knowledge_agent.hybrid_rag import get_hybrid_rag_service

    service = get_hybrid_rag_service()
    return await service.health_check()
