"""OAuth 設定の確認。

使い方:
    .\\.venv\\Scripts\\python scripts\\check_oauth_config.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.gmail.client import _load_client_config


def main() -> int:
    settings = get_settings()
    redirect_uri = settings.google_oauth_redirect_uri

    print("=== OAuth 設定確認 ===")
    print(f"GOOGLE_OAUTH_REDIRECT_URI: {redirect_uri}")
    print()

    try:
        raw = _load_client_config(settings.gmail_credentials_path)
        if "installed" in raw:
            registered = raw["installed"].get("redirect_uris", [])
            print("credentials 内の redirect_uris (参考):")
            for uri in registered:
                print(f"  - {uri}")
            print()
    except Exception as exc:
        print(f"[WARN] credentials 読み込み: {exc}")

    print("Google Cloud Console で次を設定してください:")
    print("  認証情報 → OAuth 2.0 クライアント ID → 承認済みのリダイレクト URI")
    print(f"  → {redirect_uri}")
    print()
    print("注意:")
    print("  - http://127.0.0.1 と http://localhost は別扱いです")
    print("  - パス /api/v1/oauth/google/callback まで完全一致が必要です")
    print("  - 設定後、/start からやり直してください（API 再起動後は必須）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
