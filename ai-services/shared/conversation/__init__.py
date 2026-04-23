"""
Platform-agnostic conversation storage module.

Supports hot/warm/cold data tiering:
- Hot: ArangoDB (recent messages, fast query)
- Cold: S3/SeaweedFS Parquet (archived messages)

All platforms (LINE, WhatsApp, WeCom, DingTalk, etc.) share the same
storage layer, distinguished by the `platform` field.
"""

from .models import ConversationMessage, Platform
from .storage import ConversationStorage
from .query import QueryEngine
from .archiver import Archiver

__all__ = [
    "ConversationMessage",
    "Platform",
    "ConversationStorage",
    "QueryEngine",
    "Archiver",
]