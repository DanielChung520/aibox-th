"""
DOCX 圖片抽取器（python-docx）。

從 DOCX 抽取 inline 圖片，含段落近似位置。
DOCX 無精準頁碼，以段落索引作為 order_key。

@lastUpdate  2026-04-04 21:00:00
@author      Daniel Chung
@version     5.0.0
"""

from __future__ import annotations

import hashlib
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kb_pipeline.models import ImageRef

logger = logging.getLogger(__name__)

NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


class DOCXImageExtractor:
    def extract(self, file_path: str) -> list[ImageRef]:
        """從 DOCX 抽取所有 inline 圖片。

        Args:
            file_path: DOCX 檔案路徑

        Returns:
            ImageRef 列表，按段落順序排列
        """
        import docx

        images: list[ImageRef] = []
        seen_hashes: set[str] = set()

        try:
            doc = docx.Document(file_path)
            part_map: dict[str, object] = {}

            for para_idx, para in enumerate(doc.paragraphs):
                for run in para.runs:
                    element = run._element
                    drawings = element.findall(f".//{NS_W}drawing")
                    for drawing in drawings:
                        blips = drawing.findall(f".//{NS_A}blip")
                        for blip in blips:
                            r_id = blip.get(f"{NS_R}embed")
                            if not r_id:
                                continue

                            if not part_map:
                                try:
                                    part_map = run._element.getparent.getparent._part.related_parts
                                except Exception:
                                    continue

                            image_part = part_map.get(r_id)
                            if not image_part:
                                continue

                            try:
                                part_any: Any = image_part
                                image_bytes = part_any.blob
                            except Exception:
                                continue

                            img_hash = hashlib.sha256(image_bytes).hexdigest()
                            if img_hash in seen_hashes:
                                continue
                            seen_hashes.add(img_hash)

                            content_type = getattr(
                                image_part, "content_type", "image/jpeg"
                            )
                            ext = content_type.split("/")[-1]
                            if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
                                ext = "jpg"

                            image_id = f"docx_{r_id}"
                            temp_path = self._write_temp(image_id, image_bytes, ext)

                            images.append(
                                ImageRef(
                                    image_id=image_id,
                                    page_no=1,
                                    bbox=(
                                        0.0,
                                        float(para_idx * 20),
                                        0.0,
                                        float(para_idx * 20 + 20),
                                    ),
                                    width=0,
                                    height=0,
                                    sha256=img_hash,
                                    temp_path=temp_path,
                                    source_type="docx",
                                )
                            )
        except Exception:
            logger.exception("Failed to extract images from DOCX: %s", file_path)

        return images

    def _write_temp(self, image_id: str, image_bytes: bytes, ext: str) -> str | None:
        try:
            temp_dir = tempfile.gettempdir()
            path = Path(temp_dir) / f"img_{image_id}.{ext}"
            path.write_bytes(image_bytes)
            return str(path)
        except Exception:
            logger.exception("Failed to write temp image: %s", image_id)
            return None
