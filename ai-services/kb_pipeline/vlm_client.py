"""
Ollama VLM Client（qwen3-vl）。

統一封裝 qwen3-vl 圖片描述能力，含以下關鍵設計：
- thinking 欄位 Bug 兼容：qwen3-vl 處理圖片時輸出可能跑到 thinking 而非 response
- JSON 輸出支援：要求 JSON 格式，失敗時回退純文字
- VLM Image Desc Prompt：繁體中文，結構化輸出

@lastUpdate  2026-04-04 21:00:00
@author      Daniel Chung
@version     5.0.0
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from kb_pipeline.models import ImageRef, Span

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_VLM_MODEL", "qwen3-vl:latest")
DEFAULT_TIMEOUT = 120.0

VLM_PROMPT_TEMPLATE = """你是文件理解助手。請用繁體中文描述這張圖片。

圖片元數據：
- 來源：{source_type}
- 頁碼：{page_no}
- 圖序：{image_index}
{optional_context}

請以 JSON 格式返回（只返回 JSON，不要其他文字）：
{{
  "summary": "1-3句描述這張圖在表達什麼",
  "details": ["要點1", "要點2"],
  "entities": ["實體1", "實體2"],
  "relations": ["關係1", "關係2"],
  "confidence": 0.85
}}

若無法描述，請返回：{{"summary": "", "details": [], "entities": [], "relations": [], "confidence": 0}}"""


class OllamaVLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url or OLLAMA_BASE_URL
        self.model = model or DEFAULT_MODEL
        self.timeout = timeout

    def describe(
        self, image_path: str, metadata: dict[str, object]
    ) -> dict[str, object]:
        """對單張圖片生成描述。

        Args:
            image_path: 圖片檔案路徑
            metadata: 圖片元數據，包含 source_type, page_no, image_index, context

        Returns:
            VLM 結構化回應：
            {
              "summary": str,
              "details": list[str],
              "entities": list[str],
              "relations": list[str],
              "confidence": float
            }
        """
        if not Path(image_path).exists():
            logger.warning("Image file not found: %s", image_path)
            return self._empty_result()

        try:
            image_bytes = Path(image_path).read_bytes()
        except Exception:
            logger.exception("Failed to read image: %s", image_path)
            return self._empty_result()

        img_b64 = base64.b64encode(image_bytes).decode()
        context = metadata.get("context", "")
        optional_context = f"\n鄰近文字：{context}" if context else ""

        prompt = VLM_PROMPT_TEMPLATE.format(
            source_type=metadata.get("source_type", "pdf"),
            page_no=metadata.get("page_no", 1),
            image_index=metadata.get("image_index", 1),
            optional_context=optional_context,
        )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "images": [img_b64],
                        "stream": False,
                        "options": {"temperature": 0.2, "num_predict": 1024},
                    },
                )
                response.raise_for_status()
                result = response.json()
        except Exception:
            logger.exception("VLM request failed for: %s", image_path)
            return self._empty_result()

        return self._parse_response(result)

    def _parse_response(self, result: dict[str, object]) -> dict[str, object]:
        raw_text = str(result.get("response") or result.get("thinking") or "")
        if not raw_text:
            return self._empty_result()

        raw_text = raw_text.strip()
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

        try:
            data: dict[str, Any] = json.loads(raw_text)
            return {
                "summary": str(data.get("summary", "")),
                "details": list(data.get("details", [])),
                "entities": list(data.get("entities", [])),
                "relations": list(data.get("relations", [])),
                "confidence": float(data.get("confidence", 0.0)),
            }
        except (json.JSONDecodeError, ValueError, TypeError):
            return {
                "summary": raw_text[:500],
                "details": [],
                "entities": [],
                "relations": [],
                "confidence": 0.3,
            }

    def _empty_result(self) -> dict[str, object]:
        return {
            "summary": "",
            "details": [],
            "entities": [],
            "relations": [],
            "confidence": 0.0,
        }

    def image_ref_to_span(
        self,
        image_ref: ImageRef,
        vlm_result: dict[str, Any],
        file_id: str,
        context: str = "",
    ) -> Span:
        from kb_pipeline.models import Span, SpanKind

        summary = vlm_result.get("summary", "")
        formatted_desc = (
            f"【圖片｜第{image_ref.page_no}頁｜{image_ref.image_id}】{summary}"
        )
        details = list(vlm_result.get("details") or [])
        if details:
            formatted_desc += "\n要點：" + "；".join(str(d) for d in details)

        return Span(
            kind=SpanKind.IMAGE_DESC,
            page_no=image_ref.page_no,
            order_key=image_ref.bbox[1],
            text=formatted_desc,
            file_id=file_id,
            source_ref={"bbox": image_ref.bbox, "image_id": image_ref.image_id},
        )
