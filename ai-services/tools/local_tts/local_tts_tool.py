"""
@file        Local TTS tool
@description 提供可整合至專案工具鏈的本地 TTS 介面，並保留 CLI-first 使用方式。
@lastUpdate  2026-04-25 16:25:01
@author      Hephaestus
@version     1.0.0
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from tools.base import BaseTool, ToolInput, ToolOutput
from tools.local_tts.chattts_provider import ChatTTSProvider


class GeneratedAudioFile(BaseModel):
    path: str
    voice_seed: int | None = None


class LocalTTSInput(ToolInput):
    text: str | None = None
    file_path: str | None = None
    output_path: str
    voice_seed: int | None = None
    sample_voices: bool = False
    sample_text: str | None = None
    voice_seeds: list[int] = Field(default_factory=lambda: [11, 23, 47, 89])
    paragraph_pause_ms: int = 900
    max_chars_per_chunk: int = 180

    @model_validator(mode="after")
    def validate_text_source(self) -> "LocalTTSInput":
        if not self.text and not self.file_path:
            raise ValueError("Either text or file_path must be provided")
        if self.sample_voices and not self.sample_text and not self.text and not self.file_path:
            raise ValueError("sample_voices mode requires sample_text, text, or file_path")
        return self


class LocalTTSOutput(ToolOutput):
    provider: str = "chattts"
    sample_rate: int = 24000
    segment_count: int = 0
    files: list[GeneratedAudioFile]
    mode: str


class LocalTTSTool(BaseTool[LocalTTSInput, LocalTTSOutput]):
    def __init__(self, provider: ChatTTSProvider | None = None) -> None:
        self._provider = provider or ChatTTSProvider()

    @property
    def name(self) -> str:
        return "local_tts"

    @property
    def description(self) -> str:
        return "Generate local Traditional Chinese narration audio with ChatTTS-compatible workflow"

    async def execute(self, input_data: LocalTTSInput) -> LocalTTSOutput:
        text = self._resolve_text(input_data)

        if input_data.sample_voices:
            sample_files = self._provider.synthesize_voice_samples(
                text=input_data.sample_text or text,
                output_dir=input_data.output_path,
                voice_seeds=input_data.voice_seeds,
                paragraph_pause_ms=input_data.paragraph_pause_ms,
                max_chars_per_chunk=input_data.max_chars_per_chunk,
            )
            return LocalTTSOutput(
                files=[GeneratedAudioFile(path=path, voice_seed=seed) for seed, path in sample_files],
                mode="sample_voices",
            )

        segment_count = self._provider.synthesize_to_wav(
            text=text,
            output_path=input_data.output_path,
            voice_seed=input_data.voice_seed,
            paragraph_pause_ms=input_data.paragraph_pause_ms,
            max_chars_per_chunk=input_data.max_chars_per_chunk,
        )
        return LocalTTSOutput(
            files=[GeneratedAudioFile(path=input_data.output_path, voice_seed=input_data.voice_seed)],
            segment_count=segment_count,
            mode="synthesize",
        )

    def _resolve_text(self, input_data: LocalTTSInput) -> str:
        if input_data.text:
            return input_data.text
        if input_data.file_path:
            return Path(input_data.file_path).read_text(encoding="utf-8")
        raise ValueError("No text source available")
