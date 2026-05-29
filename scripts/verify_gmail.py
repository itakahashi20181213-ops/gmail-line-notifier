"""Gmail API の動作確認スクリプト。

使い方:
    .\\.venv\\Scripts\\python scripts\\verify_gmail.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.gmail.service import GmailService


def ok(message: str) -> None:
    print(f"[OK] {message}")


def ng(message: str) -> None:
    print(f"[NG] {message}")


def main() -> int:
    settings = get_settings()
    print("=== Gmail 接続設定 ===")
    ok(f"対象メール: {settings.gmail_user_email}")
    ok(f"トークンファイル: {settings.gmail_token_path}")

    gmail = GmailService()
    failed = 0

    print("\n=== 1. refresh_token からアクセストークン取得 ===")
    try:
        access_token = gmail.get_access_token()
        ok(f"取得成功: {access_token[:20]}...")
    except Exception as exc:
        ng(str(exc))
        failed += 1
        print("\n=== 結果 ===")
        ng("アクセストークン取得に失敗したため中断します。")
        print("credentials/gmail_token.json に refresh_token が含まれているか確認してください。")
        return 1

    print("\n=== 2. inbox から直近メール取得 ===")
    try:
        emails = gmail.get_recent_inbox_emails(max_results=3)
        ok(f"取得件数: {len(emails)}")
        for index, email in enumerate(emails, start=1):
            print(f"\n--- メール {index} ---")
            print(f"gmail_message_id: {email.gmail_message_id}")
            print(f"件名: {email.subject or '(件名なし)'}")
            print(f"差出人: {email.from_address or '(不明)'}")
            body_preview = email.body.replace("\n", " ")[:120]
            print(f"本文: {body_preview or '(本文なし)'}")
    except Exception as exc:
        ng(str(exc))
        failed += 1

    print("\n=== 結果 ===")
    if failed:
        ng(f"{failed} 件のテストが失敗しました")
        return 1

    ok("すべてのテストが成功しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
