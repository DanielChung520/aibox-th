"""
@file        Learning Router
@description 提供 AIQ Learning Layer 的 user profile 查詢、更新與 turn-complete 端點。
@lastUpdate  2026-04-18 20:12:44
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from aiq_agent.learning.manager import LearningManager
from aiq_agent.learning.models import TurnCompleteRequest, UserProfileSummary
from shared.security import verify_internal_token

router = APIRouter(
    tags=["AIQ Learning"],
    dependencies=[Depends(verify_internal_token)],
)
manager = LearningManager()


@router.post("/learning/turn-complete", response_model=UserProfileSummary)
async def process_turn_complete(
    request: TurnCompleteRequest,
    x_user_key: str = Header(..., alias="X-User-Key"),
) -> UserProfileSummary:
    """Process a completed turn and update the user's learning summary."""
    return await manager.process_turn_complete(x_user_key, request)


@router.get("/user-profile", response_model=UserProfileSummary)
async def get_user_profile(
    x_user_key: str = Header(..., alias="X-User-Key"),
) -> UserProfileSummary:
    """Return the learning profile for the current user."""
    return await manager.get_profile(x_user_key)


@router.put("/user-profile", response_model=UserProfileSummary)
async def update_user_profile(
    profile: UserProfileSummary,
    x_user_key: str = Header(..., alias="X-User-Key"),
) -> UserProfileSummary:
    """Replace the learning profile for the current user."""
    profile_to_store = profile.model_copy(update={"user_key": x_user_key}, deep=True)
    return await manager.update_profile(x_user_key, profile_to_store)
