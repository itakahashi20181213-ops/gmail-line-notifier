from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.db.client import SupabaseClient
from app.line.client import LineClient, LineClientError
from app.models.schemas import User
from app.services.oauth_link import build_relink_message

logger = logging.getLogger(__name__)

RELINK_COOLDOWN_HOURS = 24


class RelinkService:
    """Gmail トークン失効時に LINE へ再連携リンクを送る。"""

    def __init__(
        self,
        db_client: SupabaseClient | None = None,
        line_client: LineClient | None = None,
        *,
        cooldown_hours: int = RELINK_COOLDOWN_HOURS,
    ):
        self.db = db_client or SupabaseClient()
        self.line = line_client or LineClient()
        self.cooldown_hours = cooldown_hours

    def _is_in_cooldown(self, user: User) -> bool:
        token = self.db.get_gmail_token(user.id)
        if token is None or token.last_relink_notice_at is None:
            return False

        last_notice = token.last_relink_notice_at
        if last_notice.tzinfo is None:
            last_notice = last_notice.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - last_notice < timedelta(
            hours=self.cooldown_hours
        )

    def notify_token_expired(self, user: User, *, reason: str | None = None) -> bool:
        """再連携メッセージを Push 送信する。クールダウン中は False を返す。"""
        if self._is_in_cooldown(user):
            logger.info(
                "再連携通知をスキップ（クールダウン中）: user_id=%s line_user_id=%s",
                user.id,
                user.line_user_id,
            )
            return False

        message = build_relink_message(user.id)
        try:
            self.line.push_message(user.line_user_id, message)
        except LineClientError:
            logger.exception(
                "再連携通知の送信に失敗: user_id=%s line_user_id=%s reason=%s",
                user.id,
                user.line_user_id,
                reason,
            )
            return False

        self.db.update_last_relink_notice(user.id, datetime.now(timezone.utc))
        logger.warning(
            "再連携通知を送信: user_id=%s line_user_id=%s reason=%s",
            user.id,
            user.line_user_id,
            reason,
        )
        return True
