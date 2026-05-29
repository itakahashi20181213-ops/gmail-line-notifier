from functools import lru_cache
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "MyApp"
    debug: bool = False
    api_prefix: str = "/api/v1"

    supabase_url: str
    supabase_key: str

    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    gmail_credentials_path: str = "credentials/gmail_credentials.json"
    gmail_token_path: str = "credentials/gmail_token.json"
    gmail_user_email: str | None = None
    google_oauth_redirect_uri: str = (
        "http://127.0.0.1:8000/api/v1/oauth/google/callback"
    )
    public_base_url: str = "http://127.0.0.1:8000"

    line_channel_access_token: str
    line_channel_secret: str
    line_user_id: str | None = None

    cron_secret: str | None = None

    scheduler_enabled: bool = True
    gmail_poll_interval_minutes: int = 5

    @property
    def is_vercel(self) -> bool:
        return os.environ.get("VERCEL") == "1"

    @property
    def use_apscheduler(self) -> bool:
        """Vercel serverless では APScheduler を使わない。"""
        return self.scheduler_enabled and not self.is_vercel


@lru_cache
def get_settings() -> Settings:
    return Settings()
