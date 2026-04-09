import os
import httpx
from datetime import datetime
import uuid


class SeaWeedFSClient:
    def __init__(
        self,
        filer_url: str = None,
        bucket_base: str = None,
    ):
        self.filer_url = filer_url or os.getenv("SEAWEEDFS_URL", "http://localhost:8888")
        self.bucket_base = bucket_base or os.getenv("SEAWEEDFS_BUCKET_BASE", "/buckets")

    def _get_user_bucket(self, username: str) -> str:
        safe_username = "".join(c for c in username if c.isalnum() or c in "-_")
        return f"{self.bucket_base}/user_{safe_username}/reports"

    def _ensure_bucket_exists(self, bucket_path: str) -> None:
        try:
            resp = httpx.head(f"{self.filer_url}{bucket_path}", timeout=5.0)
            if resp.status_code == 404:
                httpx.put(f"{self.filer_url}{bucket_path}", timeout=5.0)
        except Exception:
            pass

    async def upload_html(
        self,
        html_content: str,
        username: str,
        title: str,
    ) -> dict:
        bucket_path = self._get_user_bucket(username)
        self._ensure_bucket_exists(bucket_path)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c for c in title if c.isalnum() or c in "-_ ")[:30]
        filename = f"{timestamp}_{safe_title}.html"
        full_path = f"{bucket_path}/{filename}"

        files = {"file": (filename, html_content, "text/html")}
        try:
            response = httpx.post(
                f"{self.filer_url}{full_path}",
                files=files,
                timeout=30.0,
            )
            response.raise_for_status()

            file_url = f"{self.filer_url}{full_path}"
            return {
                "url": file_url,
                "filename": filename,
                "path": full_path,
                "size": len(html_content),
            }
        except httpx.HTTPError as e:
            return {
                "error": str(e),
                "fallback_url": f"data:text/html;base64,{html_content[:100]}...",
            }


seaweed_client = SeaWeedFSClient()
