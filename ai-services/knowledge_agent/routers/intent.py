from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/intent", tags=["Knowledge Intent"])


class IntentMatchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 3


class IntentMatchResult(BaseModel):
    intent_id: str
    score: float
    intent_data: dict[str, object]


class IntentMatchResponse(BaseModel):
    query: str
    matches: list[IntentMatchResult]
    best_match: Optional[IntentMatchResult] = None


@router.post("/embed-sync")
async def intent_embed_sync() -> dict[str, object]:
    from knowledge_agent.knowledge_intent_rag import embed_sync

    return await embed_sync()


@router.post("/match", response_model=IntentMatchResponse)
async def intent_match(request: IntentMatchRequest) -> IntentMatchResponse:
    from knowledge_agent.knowledge_intent_rag import (
        IntentMatchResponse as KGIntentMatchResponse,
        IntentMatchResult as KGIntentMatchResult,
        match_intent,
    )

    result = await match_intent(
        query=request.query,
        top_k=request.top_k or 3,
    )

    return IntentMatchResponse(
        query=result.query,
        matches=[
            IntentMatchResult(
                intent_id=m.intent_id,
                score=m.score,
                intent_data=m.intent_data,
            )
            for m in result.matches
        ],
        best_match=IntentMatchResult(
            intent_id=result.best_match.intent_id,
            score=result.best_match.score,
            intent_data=result.best_match.intent_data,
        ) if result.best_match else None,
    )
