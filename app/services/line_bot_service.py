from __future__ import annotations

import logging
from typing import Any

from app.db.client import SupabaseClient
from app.line.client import LineClient, LineClientError
from app.services.oauth_link import build_link_command_message

logger = logging.getLogger(__name__)

LINK_COMMANDS = frozenset(
    {
        "連携",
        "/link",
        "link",
        "gmail連携",
        "再連携",
        "/連携",
        "gmail",
    }
)

WELCOME_MESSAGE = (
    "友だち追加ありがとうございます。\n"
    "Gmail の要約通知 Bot です。\n\n"
    "「連携」と送ると Gmail 連携用リンクをお送りします。"
)

HELP_MESSAGE = (
    "使えるコマンド:\n"
    "・連携 … Gmail 連携リンクを送信\n"
    "・再連携 … トークン失効時などに再連携リンクを送信"
)


def is_link_command(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    if normalized in {command.lower() for command in LINK_COMMANDS}:
        return True
    return normalized.startswith("/link")


class LineBotService:
    """LINE Webhook イベントを処理する。"""

    def __init__(
        self,
        db_client: SupabaseClient | None = None,
        line_client: LineClient | None = None,
        *,
        default_send_hour: int = 9,
    ):
        self.db = db_client or SupabaseClient()
        self.line = line_client or LineClient()
        self.default_send_hour = default_send_hour

    def handle_events(self, events: list[dict[str, Any]]) -> None:
        for event in events:
            try:
                self.handle_event(event)
            except LineClientError:
                logger.exception("LINE イベント処理中に API エラー: %s", event.get("type"))
            except Exception:
                logger.exception("LINE イベント処理中にエラー: %s", event.get("type"))

    def handle_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "follow":
            self._handle_follow(event)
            return
        if event_type != "message":
            return

        message = event.get("message") or {}
        if message.get("type") != "text":
            return

        text = message.get("text", "")
        if is_link_command(text):
            self._handle_link_command(event, text)
            return

        normalized = text.strip().lower()
        if normalized in {"help", "/help", "ヘルプ", "使い方"}:
            self._reply(event, HELP_MESSAGE)

    def _handle_follow(self, event: dict[str, Any]) -> None:
        reply_token = event.get("replyToken")
        if not reply_token:
            return
        self.line.reply_message(reply_token, WELCOME_MESSAGE)

    def _handle_link_command(self, event: dict[str, Any], text: str) -> None:
        source = event.get("source") or {}
        line_user_id = source.get("userId")
        if not line_user_id:
            logger.warning("LINE userId が取得できません: event=%s", event.get("type"))
            return

        user = self.db.get_or_create_user_by_line_user_id(
            line_user_id,
            send_hour=self.default_send_hour,
        )
        already_linked = self.db.get_gmail_token(user.id) is not None
        message = build_link_command_message(user.id, already_linked=already_linked)

        reply_token = event.get("replyToken")
        if reply_token:
            self.line.reply_message(reply_token, message)
            logger.info(
                "連携リンクを Reply 送信: line_user_id=%s user_id=%s command=%s",
                line_user_id,
                user.id,
                text.strip(),
            )
            return

        self.line.push_message(line_user_id, message)
        logger.info(
            "連携リンクを Push 送信: line_user_id=%s user_id=%s command=%s",
            line_user_id,
            user.id,
            text.strip(),
        )

    def _reply(self, event: dict[str, Any], message: str) -> None:
        reply_token = event.get("replyToken")
        if not reply_token:
            return
        self.line.reply_message(reply_token, message)
