from __future__ import annotations

from app.config import get_settings


def build_google_oauth_start_url(user_id: str) -> str:
    """LINE 等で送る Gmail 連携 URL を生成する。"""
    settings = get_settings()
    base = settings.public_base_url.rstrip("/")
    prefix = settings.api_prefix.rstrip("/")
    return f"{base}{prefix}/oauth/google/start?user_id={user_id}"


def build_link_command_message(user_id: str, *, already_linked: bool = False) -> str:
    """Bot コマンド応答用の連携案内メッセージ。"""
    url = build_google_oauth_start_url(user_id)
    browser_hint = (
        "【重要】LINE 内ブラウザでは開けない場合があります。\n"
        "リンクを長押し →「ブラウザで開く」（Chrome / Safari）を選んでください。\n\n"
    )
    if already_linked:
        return (
            "Gmail は連携済みです。\n"
            "別アカウントへ切り替える場合は、以下から再連携してください。\n\n"
            f"{browser_hint}"
            f"{url}\n\n"
            "※Google アカウントの許可画面が表示されたら「許可」を押してください。"
        )
    return (
        "Gmail 連携はこちらから行えます。\n\n"
        f"{browser_hint}"
        f"{url}\n\n"
        "※Google アカウントの許可画面が表示されたら「許可」を押してください。"
    )


def build_relink_message(user_id: str) -> str:
    """トークン失効時の再連携案内メッセージ。"""
    url = build_google_oauth_start_url(user_id)
    return (
        "Gmail 連携の有効期限が切れました。\n"
        "メール通知を再開するには、以下から再連携してください。\n\n"
        f"{url}"
    )
