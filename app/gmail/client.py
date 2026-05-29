import json
import os
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build

from app.config import get_settings
from app.gmail.exceptions import GmailAuthError

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def configure_local_oauth_transport(redirect_uri: str) -> None:
    """localhost の http 開発時に OAuth トークン交換を許可する。"""
    if redirect_uri.startswith(("http://127.0.0.1", "http://localhost")):
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        # 過去に付与した calendar 等のスコープが混ざってもトークン交換を許可
        os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"


def _load_client_config(credentials_path: str) -> dict:
    """ファイルパスまたは .env 内の JSON 文字列から OAuth クライアント設定を読み込む。"""
    if credentials_path.strip().startswith("{"):
        return json.loads(credentials_path)
    path = Path(credentials_path)
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_client_secrets(client_config: dict) -> tuple[str, str, str]:
    for key in ("installed", "web"):
        if key in client_config:
            section = client_config[key]
            return (
                section["client_id"],
                section["client_secret"],
                section.get("token_uri", "https://oauth2.googleapis.com/token"),
            )
    raise ValueError("OAuth クライアント設定に installed / web が見つかりません。")


def _client_config_for_web_redirect(client_config: dict, redirect_uri: str) -> dict:
    """installed（デスクトップ）設定を Web リダイレクト用に補完する。"""
    if "web" in client_config:
        web = dict(client_config["web"])
        web["redirect_uris"] = [redirect_uri]
        return {"web": web}

    if "installed" in client_config:
        installed = dict(client_config["installed"])
        installed["redirect_uris"] = [redirect_uri]
        return {"web": installed}

    raise ValueError("OAuth クライアント設定に installed / web が見つかりません。")


def create_web_oauth_flow(
    redirect_uri: str | None = None,
    *,
    code_verifier: str | None = None,
) -> Flow:
    """Web リダイレクト用 OAuth フローを作成する。"""
    settings = get_settings()
    raw_config = _load_client_config(settings.gmail_credentials_path)
    resolved_redirect = redirect_uri or settings.google_oauth_redirect_uri
    configure_local_oauth_transport(resolved_redirect)
    client_config = _client_config_for_web_redirect(raw_config, resolved_redirect)
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=resolved_redirect,
        code_verifier=code_verifier,
        autogenerate_code_verifier=code_verifier is None,
    )


def credentials_from_refresh_token(refresh_token: str) -> Credentials:
    """DB に保存した refresh_token から Credentials を構築する。"""
    settings = get_settings()
    client_config = _load_client_config(settings.gmail_credentials_path)
    client_id, client_secret, token_uri = _extract_client_secrets(client_config)
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    try:
        creds.refresh(Request())
    except RefreshError as exc:
        raise GmailAuthError(str(exc)) from exc
    return creds


def get_credentials(refresh_token: str | None = None) -> Credentials:
    """refresh_token 指定時は DB トークン、未指定時はローカルファイルを使用する。"""
    if refresh_token:
        return credentials_from_refresh_token(refresh_token)

    settings = get_settings()
    client_config = _load_client_config(settings.gmail_credentials_path)
    token_path = Path(settings.gmail_token_path)

    creds: Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(
                port=0,
                access_type="offline",
                prompt="consent",
            )

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


def refresh_access_token(refresh_token: str | None = None) -> str:
    """refresh_token を使ってアクセストークンを更新し、トークン文字列を返す。"""
    creds = get_credentials(refresh_token=refresh_token)
    if not creds.token:
        raise RuntimeError("アクセストークンの取得に失敗しました。")
    return creds.token


def get_gmail_service(refresh_token: str | None = None):
    """認証済み Gmail API クライアントを返す。"""
    return build("gmail", "v1", credentials=get_credentials(refresh_token=refresh_token))


def fetch_gmail_profile_email(refresh_token: str) -> str:
    """連携 Gmail アカウントのメールアドレスを取得する。"""
    service = get_gmail_service(refresh_token=refresh_token)
    profile = service.users().getProfile(userId="me").execute()
    email = profile.get("emailAddress")
    if not email:
        raise RuntimeError("Gmail プロフィールからメールアドレスを取得できませんでした。")
    return email
