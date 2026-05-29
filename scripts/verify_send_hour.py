"""get_users_for_current_send_hour の動作確認スクリプト。

使い方:
    .\\.venv\\Scripts\\python scripts\\verify_send_hour.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.client import SupabaseClient


def main() -> int:
    client = SupabaseClient()
    current_hour = datetime.now().hour

    print("=== send_hour フィルタ確認 ===")
    print(f"現在時刻: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"現在の hour: {current_hour}")

    try:
        all_users = client.get_users()
    except Exception as exc:
        print(f"[NG] ユーザー取得失敗: {exc}")
        return 1

    print(f"\n全ユーザー数: {len(all_users)}")
    for user in all_users:
        print(
            f"  - {user.line_user_id} "
            f"(send_hour={user.send_hour}, gmail={user.gmail_email or '-'})"
        )

    try:
        matched = client.get_users_for_current_send_hour()
    except Exception as exc:
        print(f"\n[NG] get_users_for_current_send_hour 失敗: {exc}")
        return 1

    print(f"\n現在 hour={current_hour} に一致するユーザー: {len(matched)} 件")
    if not matched:
        print("  （該当ユーザーなし。send_hour を現在時刻に合わせたユーザーを追加すると確認できます）")
    for user in matched:
        print(f"  [一致] {user.line_user_id} (send_hour={user.send_hour})")

    manual = client.get_users_by_send_hour(current_hour)
    if len(manual) != len(matched):
        print(
            f"\n[NG] 件数不一致: manual={len(manual)} current={len(matched)}"
        )
        return 1

    print("\n[OK] get_users_for_current_send_hour は正常に動作しています")
    return 0


if __name__ == "__main__":
    sys.exit(main())
