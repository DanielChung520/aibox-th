import hmac
import hashlib
import base64
import httpx


LINE_API_BASE = "https://api.line.me"


def verify_line_signature(body: str, signature: str, channel_secret: str) -> bool:
    """
    驗證 LINE webhook x-line-signature。

    Args:
        body: 原始 request body (字串)
        signature: x-line-signature header 值
        channel_secret: Channel Secret

    Returns:
        True if signature matches, False otherwise
    """
    gen = hmac.new(
        channel_secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    gen_b64 = base64.b64encode(gen).decode("utf-8")
    return hmac.compare_digest(signature, gen_b64)


async def test_channel_connection(channel_access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{LINE_API_BASE}/v2/bot/info",
                headers={"Authorization": f"Bearer {channel_access_token}"},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "success": True,
                    "bot_user_id": data.get("userId"),
                    "display_name": data.get("displayName"),
                }
            elif resp.status_code == 401:
                return {"success": False, "error": "無效的 Access Token"}
            elif resp.status_code == 403:
                return {"success": False, "error": "無法存取此資源"}
            else:
                return {"success": False, "error": f"LINE API 錯誤: {resp.status_code}"}
        except httpx.TimeoutException:
            return {"success": False, "error": "連線逾時"}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def reply_message(channel_access_token: str, reply_token: str, messages: list[dict]) -> dict:
    """
    使用 Reply API 發送訊息。

    Args:
        channel_access_token: LINE Channel Access Token
        reply_token: 從 webhook event取得的 replyToken (一次性)
        messages: 訊息物件列表，例如 [{"type": "text", "text": "你好"}]

    Returns:
        LINE API 回應
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{LINE_API_BASE}/v2/bot/message/reply",
                headers={
                    "Authorization": f"Bearer {channel_access_token}",
                    "Content-Type": "application/json",
                },
                json={"replyToken": reply_token, "messages": messages},
                timeout=10.0,
            )
            return {"status_code": resp.status_code, "body": resp.json() if resp.status_code != 200 else {}}
        except httpx.TimeoutException:
            return {"status_code": 408, "body": {"message": "連線逾時"}}
        except Exception as e:
            return {"status_code": 500, "body": {"message": str(e)}}


async def push_message(channel_access_token: str, to_user_id: str, messages: list[dict]) -> dict:
    """
    使用 Push API 主動發送訊息給用戶。

    Args:
        channel_access_token: LINE Channel Access Token
        to_user_id: LINE User ID
        messages: 訊息物件列表

    Returns:
        LINE API 回應
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{LINE_API_BASE}/v2/bot/message/push",
                headers={
                    "Authorization": f"Bearer {channel_access_token}",
                    "Content-Type": "application/json",
                },
                json={"to": to_user_id, "messages": messages},
                timeout=10.0,
            )
            return {"status_code": resp.status_code, "body": resp.json() if resp.status_code != 200 else {}}
        except httpx.TimeoutException:
            return {"status_code": 408, "body": {"message": "連線逾時"}}
        except Exception as e:
            return {"status_code": 500, "body": {"message": str(e)}}


async def get_message_content(content_id: str, channel_access_token: str) -> bytes:
    """
    下載 LINE 訊息內容（圖片、影片、音頻、檔案）。

    Args:
        content_id: 訊息的 contentId
        channel_access_token: LINE Channel Access Token

    Returns:
        原始二進位內容
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{LINE_API_BASE}/v2/bot/message/{content_id}/content",
            headers={"Authorization": f"Bearer {channel_access_token}"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.content