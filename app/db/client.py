from datetime import datetime
from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings
from app.models.schemas import GmailToken, MessageRecord, OAuthSession, User


def _normalize_supabase_url(url: str) -> str:
    normalized = url.rstrip("/")
    if normalized.endswith("/rest/v1"):
        normalized = normalized[: -len("/rest/v1")]
    return normalized


@lru_cache
def get_supabase_client() -> Client:
    settings = get_settings()
    return create_client(
        _normalize_supabase_url(settings.supabase_url),
        settings.supabase_key,
    )


class SupabaseClient:
    USERS_TABLE = "users"
    GMAIL_TOKENS_TABLE = "gmail_tokens"
    PROCESSED_EMAILS_TABLE = "processed_emails"
    OAUTH_SESSIONS_TABLE = "oauth_sessions"
    SEND_HOUR_COLUMNS = ("send_hour", "notification_hour")

    def __init__(self):
        self._client = get_supabase_client()

    def get_users(self) -> list[User]:
        response = self._client.table(self.USERS_TABLE).select("*").execute()
        return [User.model_validate(row) for row in response.data]

    def get_user_by_line_user_id(self, line_user_id: str) -> User | None:
        response = (
            self._client.table(self.USERS_TABLE)
            .select("*")
            .eq("line_user_id", line_user_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return User.model_validate(response.data[0])

    def get_or_create_user_by_line_user_id(
        self,
        line_user_id: str,
        *,
        send_hour: int = 9,
    ) -> User:
        """LINE ユーザー ID で users を取得。未登録なら作成する。"""
        existing = self.get_user_by_line_user_id(line_user_id)
        if existing is not None:
            return existing

        if not 0 <= send_hour <= 23:
            raise ValueError("send_hour must be between 0 and 23")

        last_error: Exception | None = None
        for column in self.SEND_HOUR_COLUMNS:
            try:
                response = (
                    self._client.table(self.USERS_TABLE)
                    .insert(
                        {
                            "line_user_id": line_user_id,
                            column: send_hour,
                        }
                    )
                    .execute()
                )
                if response.data:
                    return User.model_validate(response.data[0])
            except Exception as exc:
                last_error = exc
                existing = self.get_user_by_line_user_id(line_user_id)
                if existing is not None:
                    return existing

        if last_error is not None:
            raise last_error
        raise RuntimeError("ユーザー作成に失敗しました。")

    def get_user_by_id(self, user_id: str) -> User | None:
        response = (
            self._client.table(self.USERS_TABLE)
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return User.model_validate(response.data[0])

    def update_user_gmail_email(self, user_id: str, gmail_email: str) -> None:
        self._client.table(self.USERS_TABLE).update(
            {"gmail_email": gmail_email}
        ).eq("id", user_id).execute()

    def get_gmail_token(self, user_id: str) -> GmailToken | None:
        response = (
            self._client.table(self.GMAIL_TOKENS_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return GmailToken.model_validate(response.data[0])

    def upsert_gmail_token(
        self,
        user_id: str,
        refresh_token: str,
        gmail_email: str,
    ) -> GmailToken:
        data = {
            "user_id": user_id,
            "refresh_token": refresh_token,
            "gmail_email": gmail_email,
            "updated_at": datetime.utcnow().isoformat(),
        }
        response = (
            self._client.table(self.GMAIL_TOKENS_TABLE)
            .upsert(data, on_conflict="user_id")
            .execute()
        )
        if response.data:
            return GmailToken.model_validate(response.data[0])
        return GmailToken(
            user_id=user_id,
            refresh_token=refresh_token,
            gmail_email=gmail_email,
        )

    def save_oauth_session(self, session: OAuthSession) -> OAuthSession:
        data = session.model_dump(exclude_none=True, mode="json")
        response = (
            self._client.table(self.OAUTH_SESSIONS_TABLE)
            .upsert(data, on_conflict="state")
            .execute()
        )
        if response.data:
            return OAuthSession.model_validate(response.data[0])
        return session

    def get_oauth_session(self, state: str) -> OAuthSession | None:
        response = (
            self._client.table(self.OAUTH_SESSIONS_TABLE)
            .select("*")
            .eq("state", state)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        return OAuthSession.model_validate(response.data[0])

    def delete_oauth_session(self, state: str) -> None:
        self._client.table(self.OAUTH_SESSIONS_TABLE).delete().eq(
            "state", state
        ).execute()

    def update_last_relink_notice(self, user_id: str, noticed_at: datetime) -> None:
        self._client.table(self.GMAIL_TOKENS_TABLE).update(
            {"last_relink_notice_at": noticed_at.isoformat()}
        ).eq("user_id", user_id).execute()

    def get_users_by_send_hour(self, hour: int) -> list[User]:
        if not 0 <= hour <= 23:
            raise ValueError("hour must be between 0 and 23")

        last_error: Exception | None = None
        for column in self.SEND_HOUR_COLUMNS:
            try:
                response = (
                    self._client.table(self.USERS_TABLE)
                    .select("*")
                    .eq(column, hour)
                    .execute()
                )
                return [User.model_validate(row) for row in response.data]
            except Exception as exc:
                last_error = exc

        if last_error is not None:
            raise last_error
        return []

    def get_users_for_current_send_hour(self) -> list[User]:
        """現在時刻の hour と send_hour が一致するユーザーのみ返す。"""
        return self.get_users_by_send_hour(datetime.now().hour)

    def save_processed_email(self, record: MessageRecord) -> MessageRecord:
        data = record.model_dump(exclude={"id"}, exclude_none=True, mode="json")
        on_conflict = "user_id,gmail_message_id"
        response = (
            self._client.table(self.PROCESSED_EMAILS_TABLE)
            .upsert(data, on_conflict=on_conflict)
            .execute()
        )
        if response.data:
            return MessageRecord.model_validate(response.data[0])
        return record

    def is_email_processed(self, gmail_message_id: str, user_id: str) -> bool:
        response = (
            self._client.table(self.PROCESSED_EMAILS_TABLE)
            .select("id")
            .eq("gmail_message_id", gmail_message_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return bool(response.data)

    def get_processed_message_ids(
        self,
        gmail_message_ids: list[str],
        user_id: str,
    ) -> set[str]:
        """指定 ID のうち processed_emails に登録済みの gmail_message_id を返す。"""
        if not gmail_message_ids:
            return set()

        response = (
            self._client.table(self.PROCESSED_EMAILS_TABLE)
            .select("gmail_message_id")
            .eq("user_id", user_id)
            .in_("gmail_message_id", gmail_message_ids)
            .execute()
        )
        return {row["gmail_message_id"] for row in response.data}
