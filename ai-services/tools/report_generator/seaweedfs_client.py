import os
import httpx
from datetime import datetime


_GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:6500")
_seaweed_cache: dict[str, str] = {}
_CACHE_TTL = 300


async def _get_seaweed_param(key: str, env_key: str, default: str) -> str:
    if key in _seaweed_cache:
        return _seaweed_cache[key]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{_GATEWAY_URL}/api/v1/system-params/{key}")
            if resp.status_code == 200:
                val = resp.json().get("data", {}).get("param_value", "")
                if val:
                    _seaweed_cache[key] = val
                    return val
    except Exception:
        pass
    val = os.getenv(env_key, default)
    _seaweed_cache[key] = val
    return val


class SeaweedFSClient:
    def __init__(
        self,
        filer_url: str | None = None,
        bucket_base: str | None = None,
    ):
        self._filer_url = filer_url
        self._bucket_base = bucket_base
        self._initialized = False

    async def _ensure_initialized(self):
        if self._initialized:
            return
        self._initialized = True

        if self._filer_url:
            self.filer_url = self._filer_url
        else:
            if "report.seaweed_url" in _seaweed_cache:
                self.filer_url = _seaweed_cache["report.seaweed_url"]
            else:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(f"{_GATEWAY_URL}/api/v1/system-params/report.seaweed_url")
                        if resp.status_code == 200:
                            val = resp.json().get("data", {}).get("param_value", "")
                            if val:
                                self.filer_url = val
                                _seaweed_cache["report.seaweed_url"] = val
                except Exception:
                    pass
                if not hasattr(self, "filer_url") or not self.filer_url:
                    self.filer_url = os.getenv("SEAWEEDFS_URL", "http://localhost:8888")

        if self._bucket_base:
            self.bucket_base = self._bucket_base
        else:
            if "report.seaweed_bucket_base" in _seaweed_cache:
                self.bucket_base = _seaweed_cache["report.seaweed_bucket_base"]
            else:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.get(f"{_GATEWAY_URL}/api/v1/system-params/report.seaweed_bucket_base")
                        if resp.status_code == 200:
                            val = resp.json().get("data", {}).get("param_value", "")
                            if val:
                                self.bucket_base = val
                                _seaweed_cache["report.seaweed_bucket_base"] = val
                except Exception:
                    pass
                if not hasattr(self, "bucket_base") or not getattr(self, "bucket_base", None):
                    self.bucket_base = os.getenv("SEAWEEDFS_BUCKET_BASE", "/buckets/bucket-ai-box-assets")

    def _get_user_reports_path(self, username: str) -> str:
        safe_username = "".join(c for c in username.lower() if c.isalnum() or c in "-_")
        return f"{self.bucket_base}/user_{safe_username}/reports"

    async def upload_html(
        self,
        html_content: str,
        username: str,
        title: str,
    ) -> dict:
        await self._ensure_initialized()
        reports_path = self._get_user_reports_path(username)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c for c in title if c.isalnum() or c in "-_ ")[:30]
        filename = f"{timestamp}_{safe_title}.html"
        full_path = f"{reports_path}/{filename}"
        try:
            response = httpx.put(
                f"{self.filer_url}{full_path}",
                content=html_content.encode("utf-8"),
                headers={"Content-Type": "text/html"},
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


seaweed_client = SeaweedFSClient()
