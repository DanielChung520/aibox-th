import hmac
import logging
import os

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

INTERNAL_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")

if not INTERNAL_TOKEN:
    logger.warning("INTERNAL_SERVICE_TOKEN not set — internal token verification disabled")


def verify_internal_token(
    x_internal_token: str = Header(None, alias="X-Internal-Token"),
) -> None:
    if not INTERNAL_TOKEN:
        return
    if not x_internal_token or not hmac.compare_digest(x_internal_token, INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid internal token")
