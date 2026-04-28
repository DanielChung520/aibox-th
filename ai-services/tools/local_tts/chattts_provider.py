"""
@file        ChatTTS local provider
@description 封裝 ChatTTS 的本地語音合成流程，支援腳本切段、停頓標記與多音色樣本輸出。
@lastUpdate  2026-04-25 16:25:01
@author      Hephaestus
@version     1.0.0
"""

from __future__ import annotations

import importlib
import os
import re
import unicodedata
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SAMPLE_RATE = 24000
DEFAULT_VOICE_SEEDS = [11, 23, 47, 89]
PAUSE_TOKEN_PATTERN = re.compile(r"\[\[⏱️(\d+)\]\]")

REPLACEMENT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bEEA\b", re.IGNORECASE), "伊伊誒"),
    (re.compile(r"\bAI\b", re.IGNORECASE), "人工智慧"),
    (re.compile(r"\bIT\b", re.IGNORECASE), "資訊團隊"),
    (re.compile(r"\bPDCA\b", re.IGNORECASE), "P D C A"),
    (re.compile(r"\bGraphRAG\b", re.IGNORECASE), "Graph Rag"),
    (re.compile(r"\bRagic\b", re.IGNORECASE), "Ragic"),
    (re.compile(r"\bOntology\b", re.IGNORECASE), "Ontology"),
    (re.compile(r"\bKnowledge Assets\b", re.IGNORECASE), "Knowledge Assets"),
    (re.compile(r"\bSemantic Structure\b", re.IGNORECASE), "Semantic Structure"),
    (re.compile(r"\bTraceability\b", re.IGNORECASE), "Traceability"),
    (re.compile(r"\bContext-aware\b", re.IGNORECASE), "Context aware"),
    (re.compile(r"\bHuman-AI Collaboration\b", re.IGNORECASE), "Human AI Collaboration"),
]

CHARACTER_REPLACEMENTS = {
    "；": "，",
    ";": ",",
    "-": " ",
    "–": " ",
    "—": "，",
    "／": " 或 ",
    "/": " 或 ",
    "&": " 和 ",
    "·": "，",
    "（": "，",
    "）": "，",
    "(": "，",
    ")": "，",
}


class ChatTTSProviderError(RuntimeError):
    """Raised when ChatTTS runtime or synthesis fails."""


@dataclass(slots=True)
class ScriptSegment:
    text: str | None = None
    pause_ms: int = 0


class ChatTTSProvider:
    """Thin wrapper around ChatTTS for local narration generation."""

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self.sample_rate = sample_rate
        self._runtime: tuple[Any, Any, Any] | None = None
        self._chat: Any | None = None

    def synthesize_to_wav(
        self,
        text: str,
        output_path: str | Path,
        voice_seed: int | None = None,
        paragraph_pause_ms: int = 900,
        max_chars_per_chunk: int = 180,
    ) -> int:
        chat, torch, np = self._load_runtime()
        infer_params = self._build_infer_params(chat, torch, voice_seed)
        script_segments = self._build_script_segments(
            text=text,
            paragraph_pause_ms=paragraph_pause_ms,
            max_chars_per_chunk=max_chars_per_chunk,
        )

        audio_chunks: list[Any] = []
        spoken_segment_count = 0

        for segment in script_segments:
            if segment.pause_ms > 0:
                silence_length = int(self.sample_rate * (segment.pause_ms / 1000.0))
                audio_chunks.append(np.zeros(silence_length, dtype=np.float32))
                continue

            if not segment.text:
                continue

            wav = self._infer_single_segment(chat, segment.text, infer_params)
            audio_chunks.append(np.asarray(wav, dtype=np.float32).reshape(-1))
            spoken_segment_count += 1

        if not audio_chunks:
            raise ChatTTSProviderError("No audio chunks were generated from input text")

        combined = np.concatenate(audio_chunks)
        self._write_wav(Path(output_path), combined)
        return spoken_segment_count

    def synthesize_voice_samples(
        self,
        text: str,
        output_dir: str | Path,
        voice_seeds: list[int] | None = None,
        paragraph_pause_ms: int = 900,
        max_chars_per_chunk: int = 180,
    ) -> list[tuple[int, str]]:
        seeds = voice_seeds or DEFAULT_VOICE_SEEDS
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)

        generated_files: list[tuple[int, str]] = []
        for seed in seeds:
            output_path = output_root / f"voice_seed_{seed}.wav"
            self.synthesize_to_wav(
                text=text,
                output_path=output_path,
                voice_seed=seed,
                paragraph_pause_ms=paragraph_pause_ms,
                max_chars_per_chunk=max_chars_per_chunk,
            )
            generated_files.append((seed, str(output_path)))

        return generated_files

    def _load_runtime(self) -> tuple[Any, Any, Any]:
        if self._runtime is not None and self._chat is not None:
            return self._chat, self._runtime[1], self._runtime[2]

        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

        try:
            chattts_module = importlib.import_module("ChatTTS")
            torch_module = importlib.import_module("torch")
            numpy_module = importlib.import_module("numpy")
        except ImportError as exc:
            raise ChatTTSProviderError(
                "ChatTTS runtime is not installed. Install requirements-local-tts.txt first."
            ) from exc

        chat = chattts_module.Chat()
        try:
            chat.load(compile=False)
        except Exception as exc:  # pragma: no cover - runtime-dependent
            raise ChatTTSProviderError(f"Failed to load ChatTTS model: {exc}") from exc

        self._runtime = (chattts_module, torch_module, numpy_module)
        self._chat = chat
        return chat, torch_module, numpy_module

    def _build_infer_params(self, chat: Any, torch: Any, voice_seed: int | None) -> Any | None:
        if voice_seed is None:
            return None

        torch.manual_seed(voice_seed)
        try:
            infer_params = chat.__class__.InferCodeParams(spk_emb=chat.sample_random_speaker())
        except AttributeError:
            infer_params = None
        return infer_params

    def _infer_single_segment(self, chat: Any, text: str, infer_params: Any | None) -> Any:
        try:
            if infer_params is not None:
                wavs = chat.infer([text], params_infer_code=infer_params)
            else:
                wavs = chat.infer([text])
        except TypeError:
            wavs = chat.infer([text])
        except Exception as exc:  # pragma: no cover - runtime-dependent
            raise ChatTTSProviderError(f"ChatTTS inference failed: {exc}") from exc

        if not wavs:
            raise ChatTTSProviderError("ChatTTS returned empty audio output")
        return wavs[0]

    def _build_script_segments(
        self,
        text: str,
        paragraph_pause_ms: int,
        max_chars_per_chunk: int,
    ) -> list[ScriptSegment]:
        cleaned_text = self._clean_script_text(text)
        raw_segments = self._tokenize_pauses(cleaned_text)

        script_segments: list[ScriptSegment] = []
        for raw_segment in raw_segments:
            if raw_segment.pause_ms > 0:
                script_segments.append(raw_segment)
                continue

            if not raw_segment.text:
                continue

            for chunk in self._split_text(raw_segment.text, max_chars_per_chunk):
                script_segments.append(ScriptSegment(text=chunk))
                script_segments.append(ScriptSegment(pause_ms=paragraph_pause_ms))

        while script_segments and script_segments[-1].pause_ms > 0:
            script_segments.pop()

        return script_segments

    def _clean_script_text(self, text: str) -> str:
        lines = text.splitlines()
        cleaned_lines: list[str] = []
        in_frontmatter = False
        frontmatter_consumed = False

        for index, raw_line in enumerate(lines):
            stripped = raw_line.strip()

            if index == 0 and stripped == "---":
                in_frontmatter = True
                frontmatter_consumed = True
                continue

            if in_frontmatter:
                if stripped == "---":
                    in_frontmatter = False
                continue

            if stripped.startswith("#"):
                continue
            if stripped == "---":
                continue
            if stripped == "（全文完）":
                continue
            if frontmatter_consumed and not stripped and not cleaned_lines:
                continue

            cleaned_lines.append(raw_line)

        cleaned_text = "\n".join(cleaned_lines).strip()
        return self._normalize_for_spoken_chinese(cleaned_text)

    def _normalize_for_spoken_chinese(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text)

        for source, target in CHARACTER_REPLACEMENTS.items():
            normalized = normalized.replace(source, target)

        for pattern, replacement in REPLACEMENT_PATTERNS:
            normalized = pattern.sub(replacement, normalized)

        normalized = re.sub(r"\b5W1H\b", "五個 W 一個 H", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\b30B\b", "三十 B", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bCLI\b", "C L I", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"\n\s+", "\n", normalized)
        normalized = re.sub(r"，{2,}", "，", normalized)
        normalized = re.sub(r"。{2,}", "。", normalized)
        return normalized.strip()

    def _tokenize_pauses(self, text: str) -> list[ScriptSegment]:
        segments: list[ScriptSegment] = []
        last_index = 0
        for match in PAUSE_TOKEN_PATTERN.finditer(text):
            before = text[last_index:match.start()].strip()
            if before:
                segments.append(ScriptSegment(text=before))
            segments.append(ScriptSegment(pause_ms=int(match.group(1))))
            last_index = match.end()

        tail = text[last_index:].strip()
        if tail:
            segments.append(ScriptSegment(text=tail))
        return segments

    def _split_text(self, text: str, max_chars_per_chunk: int) -> list[str]:
        normalized_lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not normalized_lines:
            return []

        chunks: list[str] = []
        for line in normalized_lines:
            remaining = line
            while len(remaining) > max_chars_per_chunk:
                split_at = self._find_split_point(remaining, max_chars_per_chunk)
                chunks.append(remaining[:split_at].strip())
                remaining = remaining[split_at:].strip()
            if remaining:
                chunks.append(remaining)
        return chunks

    def _find_split_point(self, text: str, max_chars_per_chunk: int) -> int:
        punctuation_marks = ["。", "！", "？", "；", ",", "，", ":", "："]
        window = text[: max_chars_per_chunk + 1]
        candidate_positions = [window.rfind(mark) for mark in punctuation_marks]
        best_position = max(candidate_positions)
        if best_position > 20:
            return best_position + 1
        return max_chars_per_chunk

    def _write_wav(self, output_path: Path, audio_data: Any) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        numpy_module = importlib.import_module("numpy")
        clipped = numpy_module.clip(audio_data, -1.0, 1.0)
        pcm16 = (clipped * 32767).astype(numpy_module.int16)

        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm16.tobytes())
