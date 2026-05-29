from __future__ import annotations

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError


class GmailAuthError(Exception):
    """Gmail OAuth または API 認証が失敗した場合の例外。"""


def is_gmail_auth_error(exc: BaseException) -> bool:
    """トークン失効・権限不足など再連携が必要なエラーか判定する。"""
    if isinstance(exc, (GmailAuthError, RefreshError)):
        return True
    if isinstance(exc, HttpError) and exc.resp.status in (401, 403):
        return True
    return False
