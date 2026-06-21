"""
Multimedia Analyzer Tool

Analyzes images, videos, audio, and files using AI models,
uploads original to SeaWeedFS (Filer REST API) for backup.

# Last Update: 2026-04-21
# Author: Daniel Chung
# Version: 1.1.0
"""

import os
import base64
import httpx
import uuid
from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Multimedia Analyzer Tool",
    description="AI-powered multimedia analysis: images, videos, audio, files",
    version="1.1.0",
)

ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:1420,http://localhost:6500",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MLX_BASE_URL = os.getenv("MLX_BASE_URL", "http://127.0.0.1:11400/v1")
DEFAULT_VISION_MODEL = os.getenv("VISION_MODEL", "Qwen2.5-VL-7B")
DEFAULT_AUDIO_MODEL = os.getenv("AUDIO_MODEL", "whisper")

SEAWEED_URL = os.getenv("SEAWEED_URL", "http://localhost:8888")
SEAWEED_USER = os.getenv("SEAWEED_USER", "admin")
SEAWEED_PASS = os.getenv("SEAWEED_PASS", "admin123")


class AnalyzeRequest(BaseModel):
    content: Optional[str] = None
    media_type: Literal["image", "video", "audio", "file"]
    filename: str = "unnamed"
    platform: str = "unknown"
    user_id: str = "unknown"
    mime_type: str = "application/octet-stream"
    vision_model: Optional[str] = None
    audio_model: Optional[str] = None
    prompt: Optional[str] = None


class AnalyzeResponse(BaseModel):
    description: str
    seaweed_url: Optional[str] = None
    media_type: str
    size: int
    model_used: str


async def upload_to_seaweedfs(content: bytes, filename: str, platform: str, user_id: str) -> str:
    safe_platform = platform.lower().replace("_", "-")
    safe_user = user_id.lower().replace("_", "-")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    uid = str(uuid.uuid4())
    ext = filename.split(".")[-1] if "." in filename else ""
    safe_filename = "".join(c if c.isalnum() or c in "-_." else "_" for c in filename)
    path = f"{safe_platform}/{safe_user}/{ts}_{uid}_{safe_filename}" if ext else f"{safe_platform}/{safe_user}/{ts}_{uid}_{safe_filename}"

    url = f"{SEAWEED_URL}/{path}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.put(
            url,
            content=content,
            auth=(SEAWEED_USER, SEAWEED_PASS),
        )
        resp.raise_for_status()

    return f"{SEAWEED_URL}/{path}"


async def analyze_image(content: bytes, prompt: str, model: str) -> str:
    image_b64 = base64.b64encode(content).decode("utf-8")
    try:
        data_url = f"data:image/png;base64,{image_b64}"
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ]}
            ],
            "max_tokens": 1024,
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{MLX_BASE_URL}/chat/completions", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        return content
    except Exception:
        pass
    size_kb = len(content) / 1024
    file_type = "PNG" if content[:4] == b'\x89PNG' else "JPEG"
    return f"收到一張{file_type}格式的圖片（約 {size_kb:.0f} KB）"


async def analyze_video(content: bytes, prompt: str, model: str) -> str:
    video_b64 = base64.b64encode(content).decode("utf-8")
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [video_b64],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 1024},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "") or data.get("thinking", "")


async def transcribe_audio(content: bytes, model: str) -> str:
    audio_b64 = base64.b64encode(content).decode("utf-8")
    payload = {
        "model": model,
        "input": audio_b64,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")


async def extract_file_text(content: bytes, filename: str) -> str:
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    if ext in ("pdf", "doc", "docx", "txt", "md", "json", "xml", "csv"):
        try:
            text = content.decode("utf-8", errors="ignore")
            return text[:3000] if len(text) > 3000 else text
        except Exception:
            return "[無法解讀檔案內容]"
    return f"[收到檔案: {filename}]"


@app.get("/")
def root() -> dict:
    return {
        "tool": "multimedia_analyzer",
        "version": "1.0.0",
        "description": "AI-powered multimedia analysis with SeaWeedFS backup",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "tool": "multimedia_analyzer"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    if not request.content:
        raise HTTPException(status_code=400, detail="content is required (base64 encoded)")

    try:
        content = base64.b64decode(request.content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 content: {e}")

    seaweed_url = await upload_to_seaweedfs(
        content=content,
        filename=request.filename,
        platform=request.platform,
        user_id=request.user_id,
    )

    prompt = request.prompt or "請詳細描述這個媒體的內容"
    vision_model = request.vision_model or DEFAULT_VISION_MODEL
    audio_model = request.audio_model or DEFAULT_AUDIO_MODEL
    description = ""
    model_used = ""

    if request.media_type == "image":
        description = await analyze_image(content, prompt, vision_model)
        model_used = vision_model
    elif request.media_type == "video":
        description = await analyze_video(content, prompt, vision_model)
        model_used = vision_model
    elif request.media_type == "audio":
        description = await transcribe_audio(content, audio_model)
        model_used = audio_model
    elif request.media_type == "file":
        description = await extract_file_text(content, request.filename)
        model_used = "text extractor"

    return AnalyzeResponse(
        description=description,
        seaweed_url=seaweed_url,
        media_type=request.media_type,
        size=len(content),
        model_used=model_used,
    )