"""SupabaseClient の動作確認スクリプト。

使い方:
    .\\.venv\\Scripts\\python scripts\\verify_supabase.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.db.client import SupabaseClient, _normalize_supabase_url
from app.models.schemas import MessageRecord


TEST_GMAIL_MESSAGE_ID = "__verify_supabase_test__"


def ok(message: str) -> None:
    print(f"[OK] {message}")


def ng(message: str) -> None:
    print(f"[NG] {message}")


def main() -> int:
    settings = get_settings()
    print("=== Supabase 接続設定 ===")
    ok(f"URL: {_normalize_supabase_url(settings.supabase_url)}")
    ok("API キー: 設定済み" if settings.supabase_key else "API キー: 未設定")

    client = SupabaseClient()
    failed = 0

    print("\n=== 1. get_users ===")
    try:
        users = client.get_users()
        ok(f"取得件数: {len(users)}")
        for user in users[:3]:
            print(f"     - {user.line_user_id} (send_hour={user.send_hour})")
    except Exception as exc:
        ng(str(exc))
        failed += 1

    print("\n=== 2. get_users_by_send_hour(9) ===")
    try:
        users = client.get_users_by_send_hour(9)
        ok(f"取得件数: {len(users)}")
    except Exception as exc:
        ng(str(exc))
        failed += 1

    print("\n=== 3. get_users_for_current_send_hour ===")
    try:
        from datetime import datetime

        users = client.get_users_for_current_send_hour()
        ok(f"現在時刻 hour={datetime.now().hour} の取得件数: {len(users)}")
    except Exception as exc:
        ng(str(exc))
        failed += 1

    test_user_id: str | None = None
    print("\n=== 4. get_users (user_id 取得) ===")
    try:
        users = client.get_users()
        if users:
            test_user_id = users[0].id
            ok(f"テスト用 user_id: {test_user_id}")
        else:
            ng("users が空のため user_id 付きテストをスキップします")
            failed += 1
    except Exception as exc:
        ng(str(exc))
        failed += 1

    if not test_user_id:
        print("\n=== 結果 ===")
        ng("user_id が取得できないため以降のテストを中止します")
        return 1

    print("\n=== 5. is_email_processed (未登録ID) ===")
    try:
        exists = client.is_email_processed(TEST_GMAIL_MESSAGE_ID, test_user_id)
        ok(f"結果: {exists} (期待値: False)")
        if exists:
            failed += 1
    except Exception as exc:
        ng(str(exc))
        failed += 1

    print("\n=== 6. save_processed_email ===")
    try:
        saved = client.save_processed_email(
            MessageRecord(
                user_id=test_user_id,
                gmail_message_id=TEST_GMAIL_MESSAGE_ID,
                summary="verify script test",
                line_user_id="U_verify_test",
                notified=False,
            )
        )
        ok(f"保存完了: gmail_message_id={saved.gmail_message_id}")
    except Exception as exc:
        ng(str(exc))
        failed += 1

    print("\n=== 7. is_email_processed (保存後) ===")
    try:
        exists = client.is_email_processed(TEST_GMAIL_MESSAGE_ID, test_user_id)
        ok(f"結果: {exists} (期待値: True)")
        if not exists:
            failed += 1
    except Exception as exc:
        ng(str(exc))
        failed += 1

    print("\n=== 結果 ===")
    if failed:
        ng(f"{failed} 件のテストが失敗しました")
        print("Supabase に users / processed_emails テーブルが存在するか確認してください。")
        return 1

    ok("すべてのテストが成功しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
