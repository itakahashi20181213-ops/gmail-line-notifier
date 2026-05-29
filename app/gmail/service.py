import base64
from email.utils import parsedate_to_datetime

from app.config import get_settings
from app.gmail.client import get_gmail_service, refresh_access_token
from app.models.schemas import GmailMessage


class GmailService:
    def __init__(self, refresh_token: str | None = None):
        self.settings = get_settings()
        self.refresh_token = refresh_token
        self._service = None

    @property
    def service(self):
        if self._service is None:
            self._service = get_gmail_service(refresh_token=self.refresh_token)
        return self._service

    def get_access_token(self) -> str:
        """refresh_token からアクセストークンを取得する。"""
        return refresh_access_token(refresh_token=self.refresh_token)

    def list_recent_inbox_messages(self, max_results: int = 10) -> list[dict]:
        """受信トレイから直近のメール ID 一覧を取得する。"""
        response = (
            self.service.users()
            .messages()
            .list(
                userId="me",
                labelIds=["INBOX"],
                maxResults=max_results,
            )
            .execute()
        )
        return response.get("messages", [])

    def list_unread_messages(self, max_results: int = 10) -> list[dict]:
        response = (
            self.service.users()
            .messages()
            .list(
                userId="me",
                q="is:unread",
                maxResults=max_results,
            )
            .execute()
        )
        return response.get("messages", [])

    def get_message(self, message_id: str) -> dict:
        return (
            self.service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

    def get_recent_inbox_emails(self, max_results: int = 10) -> list[GmailMessage]:
        """受信トレイから直近メールを取得し、件名・本文・message id を返す。"""
        messages = self.list_recent_inbox_messages(max_results=max_results)
        return [self.parse_message(self.get_message(message["id"])) for message in messages]

    @staticmethod
    def parse_message(raw_message: dict) -> GmailMessage:
        """Gmail API レスポンスから件名・本文・message id を抽出する。"""
        payload = raw_message.get("payload", {})
        headers = payload.get("headers", [])

        return GmailMessage(
            gmail_message_id=raw_message["id"],
            subject=_get_header(headers, "Subject"),
            body=_extract_body(payload),
            from_address=_get_header(headers, "From"),
            received_at=_parse_received_at(headers),
        )


def _get_header(headers: list[dict], name: str) -> str:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def _decode_body_data(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _extract_body(payload: dict) -> str:
    body = payload.get("body", {})
    if body.get("data"):
        return _decode_body_data(body["data"]).strip()

    parts = payload.get("parts", [])
    plain_text = _find_body_in_parts(parts, "text/plain")
    if plain_text:
        return plain_text

    html_text = _find_body_in_parts(parts, "text/html")
    if html_text:
        return html_text

    return ""


def _find_body_in_parts(parts: list[dict], mime_type: str) -> str:
    for part in parts:
        if part.get("mimeType") == mime_type:
            data = part.get("body", {}).get("data")
            if data:
                return _decode_body_data(data).strip()

        nested_parts = part.get("parts", [])
        if nested_parts:
            body = _find_body_in_parts(nested_parts, mime_type)
            if body:
                return body

    return ""


def _parse_received_at(headers: list[dict]) -> str | None:
    date_value = _get_header(headers, "Date")
    if not date_value:
        return None
    try:
        return parsedate_to_datetime(date_value).isoformat()
    except (TypeError, ValueError, OverflowError):
        return date_value
