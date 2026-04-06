"""
TimelineBuilder — 依 page_no + order_key 將 TextSpan 與 ImageDescSpan 交錯排列。

負責接收多模態管線各階段的產出（文字片段、圖片描述、OCR 文字），
按閱讀順序整合為統一的 Timeline Spans，並支援依 Span 邊界分塊。

@lastUpdate  2026-04-04 21:00:00
@author      Daniel Chung
@version     5.0.0
"""

from __future__ import annotations

from kb_pipeline.models import Span


class TimelineBuilder:
    def build(self, text_spans: list[Span], image_desc_spans: list[Span]) -> list[Span]:
        """將文字片段與圖片描述片段依 page_no + order_key 交錯排列。

        合併後按 (page_no, order_key) 排序，確保：
        - 同頁內按閱讀順序（y座標）排列
        - 跨頁不混合，頁與頁之間保持順序

        Args:
            text_spans: 純文字片段列表
            image_desc_spans: VLM 生成的圖片描述片段列表

        Returns:
            交錯排序後的統一 Span 列表
        """
        all_spans = list(text_spans) + list(image_desc_spans)
        all_spans.sort(key=lambda s: (s.page_no, s.order_key))
        return all_spans

    def chunk_by_spans(
        self,
        spans: list[Span],
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> list[str]:
        """依 Span 邊界分塊，優先在 Span 邊界切分。

        確保：
        - 不同類型 Span（如 image_desc）不會被硬切成一半
        - 跨頁時在新頁開始新 chunk
        - 重疊區取前一個 chunk 的末尾 overlap 字元

        Args:
            spans: TimelineBuilder.build() 產出的交錯 Span 列表
            chunk_size: 每塊最大字元數（預設 500）
            chunk_overlap: 重疊區字元數（預設 100）

        Returns:
            分塊後的文字字串列表
        """
        chunks: list[str] = []
        current_page = -1
        current_lines: list[str] = []
        current_len = 0

        for span in spans:
            if span.page_no != current_page and current_lines:
                chunks.append("".join(current_lines))
                overlap = "".join(current_lines)[-chunk_overlap:]
                current_lines = [overlap]
                current_len = len(overlap)
                current_page = span.page_no

            text = span.text
            if current_len + len(text) > chunk_size and current_lines:
                chunks.append("".join(current_lines))
                overlap = "".join(current_lines)[-chunk_overlap:]
                current_lines = [overlap]
                current_len = len(overlap)
                current_page = span.page_no

            current_lines.append(text)
            current_len += len(text)

        if current_lines:
            chunks.append("".join(current_lines))

        return chunks
