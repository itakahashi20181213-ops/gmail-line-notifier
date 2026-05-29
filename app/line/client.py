from __future__ import annotations

import base64
import hashlib
import hmac
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
MAX_TEXT_MESSAGE_LENGTH = 5000


class LineClientError(Exception):
    """LINE クライアントの基底例外。"""


class LineConfigurationError(LineClientError):
    """設定が不正な場合の例外。"""


class LineValidationError(LineClientError):
    """入力値が不正な場合の例外。"""


class LineApiError(LineClientError):
    """LINE Messaging API がエラーを返した場合の例外。"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: dict | str | None = None,
    ):
        self.status_code = status_code
        self.response_body = response_body
        detail = message
        if status_code is not None:
            detail = f"[{status_code}] {message}"
        super().__init__(detail)


class LineClient:
    def __init__(self, *, timeout: float = 30.0):
        settings = get_settings()
        self.channel_access_token = settings.line_channel_access_token
        self.channel_secret = settings.line_channel_secret
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.channel_access_token}",
            "Content-Type": "application/json",
        }

    def _ensure_configured(self) -> None:
        token = (self.channel_access_token or "").strip()
        if not token or token == "your-line-channel-access-token":
            raise LineConfigurationError(
                "LINE_CHANNEL_ACCESS_TOKEN が設定されていません。"
            )

    @staticmethod
    def _validate_push_input(line_user_id: str, message: str) -> tuple[str, str]:
        user_id = (line_user_id or "").strip()
        text = (message or "").strip()

        if not user_id:
            raise LineValidationError("line_user_id が空です。")
        if not text:
            raise LineValidationError("message が空です。")
        if len(text) > MAX_TEXT_MESSAGE_LENGTH:
            raise LineValidationError(
                f"message は {MAX_TEXT_MESSAGE_LENGTH} 文字以内にしてください。"
            )

        return user_id, text

    @staticmethod
    def _parse_error_body(response: httpx.Response) -> dict | str:
        try:
            body = response.json()
            if isinstance(body, dict):
                return body
        except ValueError:
            pass

        text = response.text.strip()
        return text or "(empty response)"

    @classmethod
    def _extract_error_message(cls, response: httpx.Response) -> str:
        body = cls._parse_error_body(response)
        if isinstance(body, dict):
            message = body.get("message")
            if message:
                return str(message)
            return str(body)
        return str(body)

    def push_message(self, line_user_id: str, message: str) -> dict:
        """指定ユーザーへテキストメッセージを Push 送信する。"""
        user_id, text = self._validate_push_input(line_user_id, message)
        payload = {
            "to": user_id,
            "messages": [{"type": "text", "text": text}],
        }
        return self._send_messages(LINE_PUSH_URL, payload, context="Push")

    def push_text(self, user_id: str, text: str) -> dict:
        """後方互換用エイリアス。"""
        return self.push_message(user_id, text)

    @staticmethod
    def verify_signature(body: bytes, signature: str, channel_secret: str) -> bool:
        """LINE Webhook の X-Line-Signature を検証する。"""
        secret = (channel_secret or "").strip()
        sig = (signature or "").strip()
        if not secret or not sig or not body:
            return False

        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, sig)

    def _send_messages(self, url: str, payload: dict, *, context: str) -> dict:
        self._ensure_configured()

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=self._headers, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.exception("LINE %s がタイムアウトしました", context)
            raise LineApiError(
                f"LINE {context} API がタイムアウトしました。",
                status_code=None,
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            error_message = self._extract_error_message(exc.response)
            logger.error(
                "LINE %s API エラー: status=%s message=%s",
                context,
                status_code,
                error_message,
            )
            raise LineApiError(
                error_message,
                status_code=status_code,
                response_body=self._parse_error_body(exc.response),
            ) from exc
        except httpx.RequestError as exc:
            logger.exception("LINE %s API への接続に失敗しました", context)
            raise LineApiError(
                f"LINE {context} API への接続に失敗しました: {exc}",
                status_code=None,
            ) from exc

        if not response.content:
            return {}

        try:
            return response.json()
        except ValueError:
            return {"raw_response": response.text}

    def reply_message(self, reply_token: str, message: str) -> dict:
        """Webhook イベントへの Reply 送信。"""
        token = (reply_token or "").strip()
        text = (message or "").strip()
        if not token:
            raise LineValidationError("reply_token が空です。")
        if not text:
            raise LineValidationError("message が空です。")
        if len(text) > MAX_TEXT_MESSAGE_LENGTH:
            raise LineValidationError(
                f"message は {MAX_TEXT_MESSAGE_LENGTH} 文字以内にしてください。"
            )

        payload = {
            "replyToken": token,
            "messages": [{"type": "text", "text": text}],
        }
        return self._send_messages(LINE_REPLY_URL, payload, context="Reply")
