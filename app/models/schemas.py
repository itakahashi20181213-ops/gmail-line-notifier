from datetime import datetime

from pydantic import AliasChoices, BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class GmailMessage(BaseModel):
    gmail_message_id: str
    subject: str = ""
    body: str = ""
    from_address: str = ""
    received_at: str | None = None


class User(BaseModel):
    id: str
    line_user_id: str
    gmail_email: str | None = None
    send_hour: int = Field(validation_alias=AliasChoices("send_hour", "notification_hour"))
    created_at: datetime | None = None


class GmailToken(BaseModel):
    user_id: str
    refresh_token: str
    gmail_email: str
    updated_at: datetime | None = None
    last_relink_notice_at: datetime | None = None


class OAuthSession(BaseModel):
    state: str
    user_id: str
    code_verifier: str
    redirect_uri: str
    created_at: datetime | None = None
    expires_at: datetime


class MessageRecord(BaseModel):
    id: str | None = None
    user_id: str | None = None
    gmail_message_id: str
    summary: str | None = None
    line_user_id: str | None = None
    notified: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
