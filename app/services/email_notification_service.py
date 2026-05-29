from __future__ import annotations

import logging
from dataclasses import dataclass

from app.ai.summarizer import summarize_email
from app.db.client import SupabaseClient
from app.gmail.service import GmailService
from app.line.client import LineClient, LineClientError
from app.models.schemas import GmailMessage, MessageRecord

logger = logging.getLogger(__name__)


@dataclass
class NotificationResult:
    gmail_message_id: str
    subject: str
    sent: bool
    skipped: bool = False
    error: str | None = None


class EmailNotificationService:
    """Gmail メールを取得し、processed_emails に未登録のものだけ LINE へ送信する。"""

    def __init__(
        self,
        gmail_service: GmailService | None = None,
        db_client: SupabaseClient | None = None,
        line_client: LineClient | None = None,
    ):
        self.gmail = gmail_service or GmailService()
        self.db = db_client or SupabaseClient()
        self.line = line_client or LineClient()

    def filter_unprocessed_emails(
        self,
        emails: list[GmailMessage],
        user_id: str,
    ) -> list[GmailMessage]:
        """processed_emails に gmail_message_id が存在しないメールのみ返す。"""
        if not emails:
            return []

        message_ids = [email.gmail_message_id for email in emails]
        processed_ids = self.db.get_processed_message_ids(message_ids, user_id)
        return [
            email for email in emails if email.gmail_message_id not in processed_ids
        ]

    def send_unprocessed_emails(
        self,
        line_user_id: str,
        user_id: str,
        *,
        max_results: int = 10,
    ) -> list[NotificationResult]:
        """受信トレイからメールを取得し、未処理分のみ要約して LINE に送信する。"""
        emails = self.gmail.get_recent_inbox_emails(max_results=max_results)
        unprocessed = self.filter_unprocessed_emails(emails, user_id)

        logger.info(
            "未処理メールを確認: user_id=%s total=%d unprocessed=%d",
            user_id,
            len(emails),
            len(unprocessed),
        )

        results: list[NotificationResult] = []
        for email in unprocessed:
            results.append(self.notify_email(email, line_user_id, user_id))

        return results

    def notify_email(
        self,
        email: GmailMessage,
        line_user_id: str,
        user_id: str,
    ) -> NotificationResult:
        """1通のメールを要約・送信し、processed_emails に保存する。"""
        if self.db.is_email_processed(email.gmail_message_id, user_id):
            logger.info(
                "スキップ（処理済み）: user_id=%s gmail_message_id=%s",
                user_id,
                email.gmail_message_id,
            )
            return NotificationResult(
                gmail_message_id=email.gmail_message_id,
                subject=email.subject,
                sent=False,
                skipped=True,
            )

        try:
            summary_text = summarize_email(email.subject, email.body)
            self.line.push_message(line_user_id, summary_text)
        except LineClientError as exc:
            logger.exception(
                "LINE 送信失敗: user_id=%s gmail_message_id=%s line_user_id=%s",
                user_id,
                email.gmail_message_id,
                line_user_id,
            )
            return NotificationResult(
                gmail_message_id=email.gmail_message_id,
                subject=email.subject,
                sent=False,
                error=str(exc),
            )
        except Exception as exc:
            logger.exception(
                "メール通知失敗: user_id=%s gmail_message_id=%s",
                user_id,
                email.gmail_message_id,
            )
            return NotificationResult(
                gmail_message_id=email.gmail_message_id,
                subject=email.subject,
                sent=False,
                error=str(exc),
            )

        self.db.save_processed_email(
            MessageRecord(
                user_id=user_id,
                gmail_message_id=email.gmail_message_id,
                summary=summary_text,
                line_user_id=line_user_id,
                notified=True,
            )
        )
        logger.info(
            "通知完了: user_id=%s gmail_message_id=%s line_user_id=%s",
            user_id,
            email.gmail_message_id,
            line_user_id,
        )
        return NotificationResult(
            gmail_message_id=email.gmail_message_id,
            subject=email.subject,
            sent=True,
        )
