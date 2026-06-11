"""
兩階段文件分類器。

Phase A（MIME 初步分流）：根據副檔名和 MIME Type 快速分類。
Phase B（頁面抽樣統計）：對 PDF/DOCX 抽樣計算文字覆蓋率與圖片覆蓋率。

不使用 LLM，純規則判斷，快速且可解釋。

@lastUpdate  2026-04-04 21:00:00
@author      Daniel Chung
@version     5.0.0
"""

from __future__ import annotations

import logging

from kb_pipeline.models import (
    ClassificationPhaseA,
    ClassificationPhaseB,
    DocumentClassification,
)

logger = logging.getLogger(__name__)

TEXT_COVERAGE_THRESHOLD = 0.70
IMAGE_COVERAGE_THRESHOLD = 0.30
AVG_IMAGES_PER_PAGE_THRESHOLD = 2.0


class DocumentClassifier:
    def classify(
        self,
        file_path: str,
        mime_type: str,
        file_ext: str,
    ) -> DocumentClassification:
        """兩階段文件分類。

        Phase A: MIME 初步分流（image/* 直接回 IMAGE_BASED）
        Phase B: PDF/DOCX 抽樣統計，計算覆蓋率後判定

        Args:
            file_path: 檔案路徑（用於 Phase B 抽樣）
            mime_type: MIME 類型
            file_ext: 副檔名（如 ".pdf", ".docx"）

        Returns:
            DocumentClassification: text_only / mixed / image_based
        """
        phase_a = self._phase_a(mime_type, file_ext)
        if phase_a["initial_type"] in ("image", "video"):
            return (
                DocumentClassification.IMAGE_BASED
                if phase_a["initial_type"] == "image"
                else DocumentClassification.VIDEO
            )

        phase_b = self._phase_b(file_path, file_ext)
        if phase_b is None:
            return DocumentClassification.TEXT_ONLY

        return self._decide(phase_a, phase_b)

    def _phase_a(self, mime_type: str, file_ext: str) -> ClassificationPhaseA:
        if mime_type.startswith("image/"):
            return ClassificationPhaseA(initial_type="image")
        if mime_type.startswith("video/"):
            return ClassificationPhaseA(initial_type="video")
        if mime_type == "application/pdf":
            return ClassificationPhaseA(initial_type="pdf_unknown")
        if file_ext.lower() in (".docx", ".doc"):
            return ClassificationPhaseA(initial_type="docx")
        return ClassificationPhaseA(initial_type="text")

    def _phase_b(
        self,
        file_path: str,
        file_ext: str,
    ) -> ClassificationPhaseB | None:
        if file_ext.lower() == ".pdf":
            return self._sample_pdf(file_path)
        if file_ext.lower() in (".docx", ".doc"):
            return self._sample_docx(file_path)
        return None

    def _sample_pdf(self, file_path: str) -> ClassificationPhaseB | None:
        try:
            import fitz

            with fitz.open(file_path) as doc:
                total_pages = len(doc)
                if total_pages == 0:
                    return ClassificationPhaseB(
                        text_coverage=0.0,
                        image_coverage=0.0,
                        image_count=0,
                        avg_images_per_page=0.0,
                    )
                sample_size = min(5, total_pages)
                sample_pages = doc[:sample_size]
                total_text_chars = 0
                total_image_area = 0.0
                total_page_area = 0.0
                total_image_count = 0

                for page in sample_pages:
                    page_rect = page.rect
                    page_area = page_rect.width * page_rect.height
                    total_page_area += page_area

                    text = page.get_text("text")
                    total_text_chars += len(text.strip())

                    for img in page.get_images(full=True):
                        xref = img[0]
                        try:
                            img_info = page.get_image_info(xrefs=[xref])
                            if img_info:
                                bbox = img_info[0].get("bbox")
                                if bbox:
                                    w = float(bbox[2] - bbox[0])
                                    h = float(bbox[3] - bbox[1])
                                    total_image_area += w * h
                                    total_image_count += 1
                        except Exception:
                            total_image_count += 1

                scale = sample_size / max(total_pages, 1)
                scaled_text_chars = int(total_text_chars * scale)
                text_coverage = min(
                    scaled_text_chars / max(total_page_area, 1) * 500, 1.0
                )
                image_coverage = total_image_area / max(total_page_area, 1)
                avg_images = total_image_count / sample_size

                return ClassificationPhaseB(
                    text_coverage=text_coverage,
                    image_coverage=image_coverage,
                    image_count=total_image_count,
                    avg_images_per_page=avg_images,
                )
        except Exception:
            logger.exception("Failed to sample PDF: %s", file_path)
            return None

    def _sample_docx(self, file_path: str) -> ClassificationPhaseB | None:
        try:
            import docx

            doc = docx.Document(file_path)
            total_text_chars = sum(len(p.text.strip()) for p in doc.paragraphs)
            image_count = 0
            for para in doc.paragraphs:
                for run in para.runs:
                    if run._element.findall(
                        ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing"
                    ):
                        image_count += 1

            avg_images = image_count / max(len(doc.paragraphs), 1) * 10
            text_coverage = min(
                total_text_chars / max(image_count * 100 + total_text_chars, 1), 1.0
            )

            return ClassificationPhaseB(
                text_coverage=text_coverage,
                image_coverage=0.0,
                image_count=image_count,
                avg_images_per_page=avg_images,
            )
        except Exception:
            logger.exception("Failed to sample DOCX: %s", file_path)
            return None

    def _decide(
        self,
        phase_a: ClassificationPhaseA,
        phase_b: ClassificationPhaseB,
    ) -> DocumentClassification:
        if (
            phase_b["text_coverage"] > TEXT_COVERAGE_THRESHOLD
            and phase_b["avg_images_per_page"] <= AVG_IMAGES_PER_PAGE_THRESHOLD
        ):
            return DocumentClassification.TEXT_ONLY
        if (
            phase_b["avg_images_per_page"] > AVG_IMAGES_PER_PAGE_THRESHOLD
            or phase_b["image_coverage"] > IMAGE_COVERAGE_THRESHOLD
        ):
            return DocumentClassification.IMAGE_BASED
        return DocumentClassification.MIXED
