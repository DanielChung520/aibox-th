"""
多模態文件處理資料模型。

定義 Timeline Spans 核心資料結構，用於統一封裝文件的
文字、圖片描述、OCR 文字、影片截圖等各種內容片段。

@lastUpdate  2026-04-04 21:00:00
@author      Daniel Chung
@version     5.0.0
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class SpanKind(str, Enum):
    """Span 片段類型枚舉。"""

    TEXT = "text"
    """純文字片段（來自 PDF/DOCX/TXT 等）"""

    IMAGE_DESC = "image_desc"
    """VLM 生成的圖片描述"""

    OCR_TEXT = "ocr_text"
    """OCR 識別的文字（掃描件）"""

    VIDEO_DESC = "video_desc"
    """影片截圖描述（未來擴展）"""


@dataclass
class Span:
    """Timeline Spans 最小單位。

    將文件的各種內容統一封裝為帶有位置與順序資訊的片段，
    是 TimelineBuilder、Chunker、GraphExtractor 的通用資料抽象。

    Attributes:
        kind: 片段類型（text / image_desc / ocr_text / video_desc）
        page_no: 頁碼（影片為時間戳，video_desc 使用 0）
        order_key: 頁內排序鍵（y座標 / 段落索引 / timestamp）
        text: 內容文字
        source_ref: 來源引用（bbox / xref / paragraph_id / timestamp）
        file_id: 所屬文件 ID
    """

    kind: SpanKind
    page_no: int
    order_key: float
    text: str
    file_id: str
    source_ref: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "page_no": self.page_no,
            "order_key": self.order_key,
            "text": self.text,
            "file_id": self.file_id,
            "source_ref": self.source_ref,
        }


@dataclass
class ImageRef:
    """圖片引用（從 PDF/DOCX/Video 抽取後，尚未經過 VLM）。

    Attributes:
        image_id: 唯一識別（xref / rId / hash）
        page_no: 所在頁碼（影片為時間戳，video_desc 使用 0）
        bbox: 左上右下座標 (x1, y1, x2, y2)
        width: 圖片寬度（像素）
        height: 圖片高度（像素）
        sha256: 圖片去重 Hash
        temp_path: 暫存路徑（送 VLM 前）
        source_type: 來源類型（"pdf" / "docx" / "video"）
    """

    image_id: str
    page_no: int
    bbox: tuple[float, float, float, float]
    width: int
    height: int
    sha256: str
    temp_path: str | None = None
    source_type: str = "pdf"

    @classmethod
    def from_bytes(
        cls,
        image_id: str,
        page_no: int,
        bbox: tuple[float, float, float, float],
        image_bytes: bytes,
        source_type: str = "pdf",
    ) -> ImageRef:
        """從圖片位元組建立 ImageRef（自動計算 SHA256）。"""
        sha = hashlib.sha256(image_bytes).hexdigest()
        ext = "jpg"
        if image_bytes[:4] == b"\x89PNG":
            ext = "png"
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"img_{sha[:12]}.{ext}")
        Path(temp_path).write_bytes(image_bytes)
        return cls(
            image_id=image_id,
            page_no=page_no,
            bbox=bbox,
            width=0,
            height=0,
            sha256=sha,
            temp_path=temp_path,
            source_type=source_type,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_id": self.image_id,
            "page_no": self.page_no,
            "bbox": self.bbox,
            "width": self.width,
            "height": self.height,
            "sha256": self.sha256,
            "temp_path": self.temp_path,
            "source_type": self.source_type,
        }


class DocumentClassification(str, Enum):
    """文件分類枚舉。"""

    TEXT_ONLY = "text_only"
    """純文字：文字覆蓋率高，圖片少或無，跳過圖片處理"""

    MIXED = "mixed"
    """混合：文字與圖片共存，進入完整圖片處理流程"""

    IMAGE_BASED = "image_based"
    """圖片為主：掃描件、截圖，需 OCR 處理"""

    VIDEO = "video"
    """影片（未來擴展）"""


class ClassificationPhaseA(TypedDict):
    """Phase A 分類結果（MIME 初步分流）。"""

    initial_type: str
    """初步分類：text / image / video / pdf_unknown"""


class ClassificationPhaseB(TypedDict):
    """Phase B 分類結果（頁面抽樣統計）。"""

    text_coverage: float
    """文字覆蓋率（0.0 - 1.0）"""

    image_coverage: float
    """圖片覆蓋率（0.0 - 1.0）"""

    image_count: int
    """圖片總數"""

    avg_images_per_page: float
    """每頁平均圖片數"""


class ProcessingError(TypedDict):
    """處理錯誤記錄。"""

    step: str
    """失敗步驟：parse / classify_a / classify_b / extract_image / vlm / ocr"""

    item_id: str
    """失敗項目 ID：file_id / image_id / page_no"""

    error: str
    """錯誤描述"""

    recoverable: bool
    """是否可恢復"""


@dataclass
class ProcessingReport:
    """每個文件的處理報告。

    記錄多模態處理管線各階段的處理結果與錯誤，
    供後續重試、監控與分析使用。

    Attributes:
        file_id: 文件 ID
        classification: 分類結果
        pages_processed: 已處理頁數
        images_extracted: 已抽取圖片數
        images_vlm_described: VLM 成功描述數
        images_vlm_failed: VLM 失敗數
        ocr_pages: OCR 處理頁數
        total_text_chars: 總文字字元數
        total_spans: 總 Span 數
        duration_ms: 處理耗時（毫秒）
        errors: 錯誤列表
    """

    file_id: str
    classification: DocumentClassification
    pages_processed: int = 0
    images_extracted: int = 0
    images_vlm_described: int = 0
    images_vlm_failed: int = 0
    ocr_pages: int = 0
    total_text_chars: int = 0
    total_spans: int = 0
    duration_ms: int = 0
    errors: list[ProcessingError] = field(default_factory=list)

    @property
    def can_retry(self) -> bool:
        """是否有可重試步驟。"""
        return any(e["recoverable"] for e in self.errors)

    @property
    def has_vlm_failures(self) -> bool:
        """是否有 VLM 失敗（可供重試）。"""
        return any(e["step"] == "vlm" and e["recoverable"] for e in self.errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "classification": self.classification.value,
            "pages_processed": self.pages_processed,
            "images_extracted": self.images_extracted,
            "images_vlm_described": self.images_vlm_described,
            "images_vlm_failed": self.images_vlm_failed,
            "ocr_pages": self.ocr_pages,
            "total_text_chars": self.total_text_chars,
            "total_spans": self.total_spans,
            "duration_ms": self.duration_ms,
            "errors": self.errors,
            "can_retry": self.can_retry,
        }
