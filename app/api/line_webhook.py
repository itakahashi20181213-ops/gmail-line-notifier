import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import get_settings
from app.line.client import LineClient
from app.services.line_bot_service import LineBotService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/line", tags=["line"])


@router.post("/webhook")
async def line_webhook(
    request: Request,
    x_line_signature: str | None = Header(default=None, alias="X-Line-Signature"),
):
    """LINE Messaging API Webhook。"""
    body = await request.body()
    settings = get_settings()
    line_client = LineClient()

    secret = (settings.line_channel_secret or "").strip()
    if not secret or secret == "your-line-channel-secret":
        raise HTTPException(
            status_code=503,
            detail="LINE_CHANNEL_SECRET が設定されていません。",
        )

    if not x_line_signature or not line_client.verify_signature(
        body, x_line_signature, secret
    ):
        logger.warning("LINE Webhook 署名検証失敗")
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    events = payload.get("events") or []
    if events:
        LineBotService().handle_events(events)

    return {"status": "ok"}
