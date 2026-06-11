from __future__ import annotations

import base64
from typing import Literal

from tools.base import BaseTool, ToolInput, ToolOutput
from shared.multimedia import process_multimedia, MultimediaResult


class MultimediaAnalyzerInput(ToolInput):
    content_b64: str
    media_type: Literal["image", "video", "audio"]
    filename: str = "unnamed"
    platform: str = "unknown"
    user_id: str = "agent"
    mime_type: str = "application/octet-stream"
    prompt: str | None = None
    vision_model: str | None = None


class MultimediaAnalyzerOutput(ToolOutput):
    description: str
    seaweed_url: str | None = None
    media_type: str
    size: int


class MultimediaAnalyzerTool(BaseTool[MultimediaAnalyzerInput, MultimediaAnalyzerOutput]):

    @property
    def name(self) -> str:
        return "multimedia_analyzer"

    @property
    def description(self) -> str:
        return "Analyze and describe images and videos using AI vision models, transcribe audio. Backs up original to SeaweedFS."

    async def execute(self, input_data: MultimediaAnalyzerInput) -> MultimediaAnalyzerOutput:
        content = base64.b64decode(input_data.content_b64)

        result: MultimediaResult = await process_multimedia(
            content=content,
            media_type=input_data.media_type,
            filename=input_data.filename,
            platform=input_data.platform,
            user_id=input_data.user_id,
            mime_type=input_data.mime_type,
            vision_model=input_data.vision_model,
        )

        return MultimediaAnalyzerOutput(
            description=result.description,
            seaweed_url=result.seaweed_url,
            media_type=input_data.media_type,
            size=result.size,
        )
