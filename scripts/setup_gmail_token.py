"""Gmail OAuth 初回認証で refresh_token を取得するスクリプト。

使い方:
    .\\.venv\\Scripts\\python scripts\\setup_gmail_token.py

ブラウザで Google 認証を完了すると、credentials/gmail_token.json に
refresh_token を含むトークンが保存されます。
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.gmail.client import get_credentials


def main() -> int:
    settings = get_settings()
    print("Gmail OAuth 認証を開始します。ブラウザで Google ログインを完了してください。")
    print(f"トークン保存先: {settings.gmail_token_path}")

    creds = get_credentials()
    if not creds.refresh_token:
        print("[NG] refresh_token が取得できませんでした。")
        print("Google Cloud Console で OAuth 同意画面の公開状態と、")
        print("offline access (prompt=consent) が有効か確認してください。")
        return 1

    print("[OK] refresh_token を保存しました。")
    print(f"refresh_token: {creds.refresh_token[:20]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
