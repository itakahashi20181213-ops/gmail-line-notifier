"""users テーブルに LINE ユーザーを登録する。

使い方:
    .\\.venv\\Scripts\\python scripts\\register_user.py
    .\\.venv\\Scripts\\python scripts\\register_user.py --line-user-id Uxxxx --send-hour 9
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.db.client import SupabaseClient
from app.services.oauth_link import build_google_oauth_start_url


def main() -> int:
    parser = argparse.ArgumentParser(description="users テーブルにユーザーを登録")
    parser.add_argument(
        "--line-user-id",
        help="LINE ユーザー ID（未指定時は .env の LINE_USER_ID）",
    )
    parser.add_argument(
        "--send-hour",
        type=int,
        default=9,
        help="通知時刻 0-23（デフォルト: 9）",
    )
    args = parser.parse_args()

    settings = get_settings()
    line_user_id = (args.line_user_id or settings.line_user_id or "").strip()
    if not line_user_id:
        print("[NG] --line-user-id または .env の LINE_USER_ID を指定してください")
        return 1

    if not 0 <= args.send_hour <= 23:
        print("[NG] send_hour は 0〜23 で指定してください")
        return 1

    client = SupabaseClient()
    try:
        user = client.get_or_create_user_by_line_user_id(
            line_user_id,
            send_hour=args.send_hour,
        )
    except Exception as exc:
        print(f"[NG] 登録に失敗しました: {exc}")
        return 1

    print("[OK] ユーザーを登録しました")
    print(f"  id:           {user.id}")
    print(f"  line_user_id: {user.line_user_id}")
    print(f"  通知時刻:     {user.send_hour}")
    print()
    print("Gmail 連携 URL:")
    print(f"  {build_google_oauth_start_url(user.id)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
