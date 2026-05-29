import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from googleapiclient.errors import HttpError

from app.config import get_settings
from app.db.client import SupabaseClient
from app.gmail.client import fetch_gmail_profile_email
from app.services.oauth_session_service import OAuthSessionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth/google", tags=["oauth"])


def _format_token_error(exc: Exception, redirect_uri: str) -> str:
    message = str(exc)
    hint = (
        f"Google Cloud Console の「承認済みのリダイレクト URI」に "
        f"次を追加してください: {redirect_uri}"
    )
    if "redirect_uri_mismatch" in message.lower() or "redirect_uri" in message.lower():
        return f"{message} — {hint}"
    if "invalid_grant" in message.lower():
        return (
            f"{message} — OAuth セッションが無効です。"
            f"/start からやり直すか、{hint}"
        )
    if "insecure_transport" in message.lower():
        return (
            f"{message} — ローカル開発用の設定が不足しています。"
            "API を再起動して /start からやり直してください。"
        )
    if "scope has changed" in message.lower():
        return (
            f"{message} — Gmail のみ再連携してください。"
            "https://myaccount.google.com/permissions でこのアプリの"
            "アクセス権を削除してから /start を開き直してください。"
        )
    return message


@router.get("/start")
async def google_oauth_start(user_id: str = Query(..., description="users.id (UUID)")):
    """Google OAuth 認可画面へリダイレクトする。"""
    db = SupabaseClient()
    user = db.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

    settings = get_settings()
    redirect_uri = settings.google_oauth_redirect_uri
    oauth_sessions = OAuthSessionService(db)
    authorization_url = oauth_sessions.begin_authorization(user_id, redirect_uri)
    logger.info("OAuth 開始: user_id=%s redirect_uri=%s", user_id, redirect_uri)
    return RedirectResponse(url=authorization_url)


@router.get("/callback")
async def google_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """OAuth コールバック: refresh_token を gmail_tokens に保存する。"""
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth エラー: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="code または state が不足しています")

    db = SupabaseClient()
    user = db.get_user_by_id(state)
    if user is None:
        raise HTTPException(status_code=404, detail="state のユーザーが見つかりません")

    settings = get_settings()
    redirect_uri = settings.google_oauth_redirect_uri
    oauth_sessions = OAuthSessionService(db)
    authorization_response = str(request.url)

    try:
        creds = oauth_sessions.complete_authorization(state, authorization_response)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "OAuth トークン取得失敗: user_id=%s redirect_uri=%s response=%s",
            state,
            redirect_uri,
            authorization_response,
        )
        raise HTTPException(
            status_code=400,
            detail=f"トークン取得失敗: {_format_token_error(exc, redirect_uri)}",
        ) from exc

    if not creds.refresh_token:
        raise HTTPException(
            status_code=400,
            detail="refresh_token が取得できませんでした。prompt=consent で再認証してください。",
        )

    try:
        gmail_email = fetch_gmail_profile_email(creds.refresh_token)
    except HttpError as exc:
        logger.exception("Gmail プロフィール取得失敗: user_id=%s", state)
        raise HTTPException(
            status_code=502,
            detail=f"Gmail プロフィール取得失敗: {exc}",
        ) from exc

    db.upsert_gmail_token(
        user_id=user.id,
        refresh_token=creds.refresh_token,
        gmail_email=gmail_email,
    )
    db.update_user_gmail_email(user.id, gmail_email)

    logger.info("OAuth 完了: user_id=%s gmail=%s", user.id, gmail_email)
    return {
        "status": "connected",
        "user_id": user.id,
        "line_user_id": user.line_user_id,
        "gmail_email": gmail_email,
    }


@router.get("/config-check")
async def oauth_config_check() -> dict[str, Any]:
    """設定確認用（本番では無効化推奨）。"""
    settings = get_settings()
    return {
        "redirect_uri": settings.google_oauth_redirect_uri,
        "hint": (
            "Google Cloud Console → 認証情報 → OAuth 2.0 クライアント → "
            "承認済みのリダイレクト URI に redirect_uri と完全一致する URL を追加"
        ),
    }
