"""
Data models for platform-agnostic conversation storage.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Platform(str, Enum):
    """Supported messaging platforms."""

    LINE = "line"
    WHATSAPP = "whatsapp"
    WECOM = "wecom"
    DINGTALK = "dingtalk"
    # Generic bot (default)
    BOT = "bot"


class ConversationMessage(BaseModel):
    """
    Unified conversation message model for all platforms.

    Attributes:
        session_id: Unique identifier for the conversation session.
            Format: "{platform}_{channel_id}_{timestamp}" (e.g., "line_ch_123_1712345678")
        platform: Messaging platform (line, whatsapp, wecom, dingtalk, bot).
        role: Message sender role ("user" or "assistant").
        message: The message content.
        metadata: Optional platform-specific data (e.g., LINE message type, media URL).
        created_at: Timestamp when the message was created.
    """

    session_id: str = Field(..., description="Unique session identifier")
    platform: Platform = Field(..., description="Messaging platform")
    role: str = Field(..., pattern="^(user|assistant)$", description="Sender role")
    message: str = Field(..., description="Message content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Platform-specific metadata")
    created_at: datetime = Field(default_factory=lambda: datetime.now(), description="Creation timestamp")

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "line_ch_abc123_1712345678",
                "platform": "line",
                "role": "user",
                "message": "Hello, I need help with my order",
                "metadata": {"message_type": "text", "reply_token": "abc123"},
                "created_at": "2026-04-21T10:30:00Z",
            }
        }
    }


class SessionSummary(BaseModel):
    """Summary of a conversation session."""

    session_id: str
    platform: Platform
    message_count: int
    first_message_at: datetime
    last_message_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArchiveConfig(BaseModel):
    """Configuration for data tiering / archiving."""

    hot_ttl_days: int = Field(default=7, description="Days to keep in ArangoDB (hot tier)")
    archive_path: str = Field(default="/buckets/bot_chat_archive", description="S3 path for cold storage")
    partition_by: str = Field(default="platform", description="Partition key for S3 Parquet files")
