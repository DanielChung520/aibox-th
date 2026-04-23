import os
import httpx
import uuid
from datetime import datetime, timezone
from typing import Literal

SEAWEEDFS_URL = os.getenv("SEAWEEDFS_URL", "http://localhost:8888")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
VISION_MODEL = os.getenv("VISION_MODEL", "qwen3-vl:latest")
AUDIO_MODEL = os.getenv("AUDIO_MODEL", "whisper")


async def upload_to_seaweedfs(
    content: bytes,
    filename: str,
    mime_type: str,
    platform: str,
    user_id: str,
) -> str:
    bucket_path = f"/buckets/{platform}_media/{user_id}"
    full_path = f"{bucket_path}/{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{filename}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{SEAWEEDFS_URL}{full_path}",
            files={"file": (filename, content, mime_type)},
        )
        resp.raise_for_status()

    return f"{SEAWEEDFS_URL}{full_path}"


async def analyze_image(content: bytes, prompt: str = "請詳細描述這張圖片的內容") -> str:
    import base64
    image_b64 = base64.b64encode(content).decode("utf-8")

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")


async def analyze_video(content: bytes, prompt: str = "請詳細描述這段影片的內容") -> str:
    import base64
    video_b64 = base64.b64encode(content).decode("utf-8")

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:video/mp4;base64,{video_b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")


async def transcribe_audio(content: bytes, prompt: str = "") -> str:
    import base64
    audio_b64 = base64.b64encode(content).decode("utf-8")

    payload = {
        "model": AUDIO_MODEL,
        "input": audio_b64,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")


async def extract_file_text(content: bytes, filename: str) -> str:
    ext = filename.lower().split(".")[-1] if "." in filename else ""

    if ext in ("pdf", "doc", "docx", "txt", "md"):
        try:
            text = content.decode("utf-8", errors="ignore")
            return text[:2000] if len(text) > 2000 else text
        except Exception:
            return "[無法解讀檔案內容]"

    return f"[收到檔案: {filename}]"


class MultimediaResult:
    def __init__(
        self,
        description: str,
        seaweed_url: str | None = None,
        mime_type: str = "application/octet-stream",
        size: int = 0,
    ):
        self.description = description
        self.seaweed_url = seaweed_url
        self.mime_type = mime_type
        self.size = size


async def process_multimedia(
    content: bytes,
    media_type: Literal["image", "video", "audio", "file"],
    filename: str,
    platform: str,
    user_id: str,
    mime_type: str = "application/octet-stream",
) -> MultimediaResult:
    seaweed_url = await upload_to_seaweedfs(content, filename, mime_type, platform, user_id)

    description = ""

    if media_type == "image":
        description = await analyze_image(content)
    elif media_type == "video":
        description = await analyze_video(content)
    elif media_type == "audio":
        description = await transcribe_audio(content)
    elif media_type == "file":
        description = await extract_file_text(content, filename)

    return MultimediaResult(
        description=description,
        seaweed_url=seaweed_url,
        mime_type=mime_type,
        size=len(content),
    )