"""
PDF 圖片抽取器（PyMuPDF）。

從 PDF 抽取內嵌圖片，含頁碼、bbox、xref，
並依 SHA256 去重（PDF 可能多次引用同一圖片）。

@lastUpdate  2026-04-04 21:00:00
@author      Daniel Chung
@version     5.0.0
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kb_pipeline.models import ImageRef

logger = logging.getLogger(__name__)


class PDFImageExtractor:
    def extract(self, file_path: str, max_pages: int | None = None) -> list[ImageRef]:
        """從 PDF 抽取所有內嵌圖片。

        Args:
            file_path: PDF 檔案路徑
            max_pages: 最大抽樣頁數（None = 全部頁面）

        Returns:
            ImageRef 列表，按 (page_no, image_index) 排序
        """
        import fitz

        images: list[ImageRef] = []
        seen_hashes: set[str] = set()

        try:
            with fitz.open(file_path) as doc:
                total = min(len(doc), max_pages) if max_pages else len(doc)
                for page_no in range(1, total + 1):
                    page = doc[page_no - 1]
                    page_images = page.get_images(full=True)

                    for img_index, img in enumerate(page_images):
                        xref = img[0]
                        try:
                            base_image = doc.extract_image(xref)
                        except Exception:
                            logger.warning(
                                "Failed to extract image xref=%d from %s",
                                xref,
                                file_path,
                            )
                            continue

                        image_bytes = base_image["image"]
                        img_hash = hashlib_sha256(image_bytes)

                        if img_hash in seen_hashes:
                            continue
                        seen_hashes.add(img_hash)

                        ext = base_image.get("ext", "jpg")
                        image_id = f"pdf_{xref}"
                        temp_path = self._write_temp(image_id, image_bytes, ext)

                        bbox = (0.0, 0.0, 0.0, 0.0)
                        try:
                            info_list = page.get_image_info(xrefs=True)
                            for info in info_list:
                                if info.get("xref") == xref:
                                    b = info.get("bbox")
                                    if b:
                                        bbox = (
                                            float(b[0]),
                                            float(b[1]),
                                            float(b[2]),
                                            float(b[3]),
                                        )
                                    break
                        except Exception:
                            pass

                        images.append(
                            ImageRef(
                                image_id=image_id,
                                page_no=page_no,
                                bbox=bbox,
                                width=base_image.get("width", 0),
                                height=base_image.get("height", 0),
                                sha256=img_hash,
                                temp_path=temp_path,
                                source_type="pdf",
                            )
                        )
        except Exception:
            logger.exception("Failed to open PDF: %s", file_path)

        return images

    def _write_temp(self, image_id: str, image_bytes: bytes, ext: str) -> str | None:
        try:
            import tempfile
            from pathlib import Path
            import hashlib

            temp_dir = tempfile.gettempdir()
            sha = hashlib.sha256(image_bytes).hexdigest()
            path = Path(temp_dir) / f"img_{sha[:12]}.{ext}"
            path.write_bytes(image_bytes)
            return str(path)
        except Exception:
            logger.exception("Failed to write temp image: %s", image_id)
            return None


def hashlib_sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
