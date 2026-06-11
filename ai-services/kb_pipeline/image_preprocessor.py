"""
圖片預處理器（Pillow）。

在送 VLM 前對圖片進行尺寸壓縮，節省記憶體並加快處理。
支援等比縮放、JPEG 品質控制。

@lastUpdate  2026-04-04 21:00:00
@author      Daniel Chung
@version     5.0.0
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kb_pipeline.models import ImageRef

logger = logging.getLogger(__name__)

DEFAULT_MAX_EDGE = 2048
DEFAULT_JPEG_QUALITY = 85


class ImagePreprocessor:
    def __init__(
        self,
        max_edge: int = DEFAULT_MAX_EDGE,
        jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    ) -> None:
        self.max_edge = max_edge
        self.jpeg_quality = jpeg_quality

    def preprocess(self, image_ref: ImageRef) -> str:
        """壓縮圖片，返回壓縮後檔案路徑。

        Args:
            image_ref: ImageRef（需有 temp_path）

        Returns:
            壓縮後的檔案路徑
        """
        if not image_ref.temp_path or not Path(image_ref.temp_path).exists():
            raise FileNotFoundError(f"Image file not found: {image_ref.temp_path}")

        from PIL import Image

        try:
            img = Image.open(image_ref.temp_path)
            img.thumbnail((self.max_edge, self.max_edge), Image.Resampling.LANCZOS)
            rgb_img = img.convert("RGB")

            out_path = image_ref.temp_path.replace(".png", "_compressed.jpg")
            rgb_img.save(out_path, "JPEG", quality=self.jpeg_quality, optimize=True)
            return out_path
        except Exception:
            logger.exception("Failed to preprocess image: %s", image_ref.image_id)
            return image_ref.temp_path
