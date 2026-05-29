from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.db.client import SupabaseClient
from app.gmail.client import create_web_oauth_flow
from app.models.schemas import OAuthSession

logger = logging.getLogger(__name__)

OAUTH_SESSION_TTL_MINUTES = 10


class OAuthSessionService:
    """Google OAuth PKCE セッションを Supabase に永続化する。"""

    def __init__(self, db_client: SupabaseClient | None = None):
        self.db = db_client or SupabaseClient()

    def begin_authorization(self, user_id: str, redirect_uri: str) -> str:
        """OAuth 開始 URL を生成し、code_verifier を DB に保存する。"""
        flow = create_web_oauth_flow(redirect_uri)
        authorization_url, _state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            state=user_id,
        )
        if not flow.code_verifier:
            raise RuntimeError("PKCE code_verifier の生成に失敗しました。")

        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=OAUTH_SESSION_TTL_MINUTES
        )
        self.db.save_oauth_session(
            OAuthSession(
                state=user_id,
                user_id=user_id,
                code_verifier=flow.code_verifier,
                redirect_uri=redirect_uri,
                expires_at=expires_at,
            )
        )
        logger.info("OAuth セッション保存: user_id=%s", user_id)
        return authorization_url

    def complete_authorization(
        self,
        state: str,
        authorization_response: str,
    ):
        """保存済み code_verifier でトークン交換し、セッションを削除する。"""
        session = self.db.get_oauth_session(state)
        if session is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "OAuth セッションが見つかりません。"
                    "/start からやり直してください。"
                ),
            )

        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            self.db.delete_oauth_session(state)
            raise HTTPException(
                status_code=400,
                detail="OAuth セッションの有効期限が切れました。/start からやり直してください。",
            )

        flow = create_web_oauth_flow(
            session.redirect_uri,
            code_verifier=session.code_verifier,
        )
        try:
            flow.fetch_token(authorization_response=authorization_response)
        finally:
            self.db.delete_oauth_session(state)

        return flow.credentials
