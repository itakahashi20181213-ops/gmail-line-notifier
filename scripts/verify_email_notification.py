"""EmailNotificationService の動作確認スクリプト。

使い方:
    .\\.venv\\Scripts\\python scripts\\verify_email_notification.py
    .\\.venv\\Scripts\\python scripts\\verify_email_notification.py --send
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.db.client import SupabaseClient
from app.gmail.service import GmailService
from app.models.schemas import GmailMessage, MessageRecord
from app.services.email_notification_service import EmailNotificationService

TEST_GMAIL_MESSAGE_ID = "__verify_email_notification_test__"


def ok(message: str) -> None:
    print(f"[OK] {message}")


def ng(message: str) -> None:
    print(f"[NG] {message}")


def verify_filter_logic() -> int:
    """モックを使った filter_unprocessed_emails の単体確認。"""
    print("\n=== 1. filter_unprocessed_emails（モック） ===")
    failed = 0

    mock_db = MagicMock()
    mock_db.get_processed_message_ids.return_value = {"msg_processed"}

    service = EmailNotificationService(db_client=mock_db)
    emails = [
        GmailMessage(gmail_message_id="msg_new", subject="新規"),
        GmailMessage(gmail_message_id="msg_processed", subject="処理済み"),
    ]
    unprocessed = service.filter_unprocessed_emails(emails, "user-test-id")

    if len(unprocessed) == 1 and unprocessed[0].gmail_message_id == "msg_new":
        ok("未処理メールのみ抽出: msg_new")
    else:
        ng(f"期待と異なる結果: {[e.gmail_message_id for e in unprocessed]}")
        failed += 1

    mock_db.get_processed_message_ids.assert_called_once_with(
        ["msg_new", "msg_processed"],
        "user-test-id",
    )
    return failed


def _first_user_id(db: SupabaseClient) -> str | None:
    users = db.get_users()
    return users[0].id if users else None


def verify_batch_lookup(db: SupabaseClient) -> int:
    """get_processed_message_ids の実 DB 確認。"""
    print("\n=== 2. get_processed_message_ids（Supabase） ===")
    failed = 0
    user_id = _first_user_id(db)
    if not user_id:
        ng("users テーブルにレコードがありません")
        return 1

    try:
        db.save_processed_email(
            MessageRecord(
                user_id=user_id,
                gmail_message_id=TEST_GMAIL_MESSAGE_ID,
                summary="verify batch lookup",
                line_user_id="U_verify_test",
                notified=False,
            )
        )
        processed = db.get_processed_message_ids(
            [TEST_GMAIL_MESSAGE_ID, "__not_registered__"],
            user_id,
        )
        if TEST_GMAIL_MESSAGE_ID in processed and "__not_registered__" not in processed:
            ok(f"登録済み ID を正しく検出: {processed}")
        else:
            ng(f"期待と異なる結果: {processed}")
            failed += 1
    except Exception as exc:
        ng(str(exc))
        failed += 1

    return failed


def verify_dry_run(
    service: EmailNotificationService,
    user_id: str,
    max_results: int,
) -> int:
    """Gmail 取得 + 未処理フィルタ（LINE 送信なし）。"""
    print("\n=== 3. Gmail 取得 + 未処理フィルタ（dry-run） ===")
    failed = 0

    try:
        emails = service.gmail.get_recent_inbox_emails(max_results=max_results)
        ok(f"Gmail 取得件数: {len(emails)}")

        unprocessed = service.filter_unprocessed_emails(emails, user_id)
        processed_count = len(emails) - len(unprocessed)
        ok(f"未処理: {len(unprocessed)} / 処理済み: {processed_count}")

        for index, email in enumerate(unprocessed[:3], start=1):
            print(f"\n--- 未処理メール {index} ---")
            print(f"gmail_message_id: {email.gmail_message_id}")
            print(f"件名: {email.subject or '(件名なし)'}")
    except Exception as exc:
        ng(str(exc))
        failed += 1

    return failed


def verify_send(
    service: EmailNotificationService,
    line_user_id: str,
    user_id: str,
) -> int:
    """未処理 1 件のみ LINE 送信（要約 + 保存）。"""
    print(f"\n=== 4. 未処理メール送信（line_user_id={line_user_id}） ===")
    failed = 0

    try:
        results = service.send_unprocessed_emails(
            line_user_id,
            user_id,
            max_results=1,
        )
        if not results:
            ok("未処理メールなし（送信スキップ）")
            return failed

        result = results[0]
        print(f"gmail_message_id: {result.gmail_message_id}")
        print(f"件名: {result.subject or '(件名なし)'}")
        if result.sent:
            ok("LINE 送信 + processed_emails 保存成功")
            if service.db.is_email_processed(result.gmail_message_id, user_id):
                ok("processed_emails に登録確認")
            else:
                ng("processed_emails に未登録")
                failed += 1
        elif result.skipped:
            ok("処理済みのためスキップ")
        else:
            ng(f"送信失敗: {result.error}")
            failed += 1
    except Exception as exc:
        ng(str(exc))
        failed += 1

    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description="EmailNotificationService 動作確認")
    parser.add_argument(
        "--send",
        action="store_true",
        help="未処理 1 件を実際に LINE 送信する（OpenAI 要約も実行）",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Gmail 取得件数（デフォルト: 5）",
    )
    args = parser.parse_args()

    settings = get_settings()
    print("=== EmailNotificationService 動作確認 ===")
    ok(f"Gmail: {settings.gmail_user_email}")
    ok(f"LINE_USER_ID: {settings.line_user_id or '(未設定)'}")

    failed = verify_filter_logic()

    db = SupabaseClient()
    failed += verify_batch_lookup(db)

    user_id = _first_user_id(db)
    if not user_id:
        ng("users テーブルにレコードがありません")
        failed += 1
        user_id = ""

    gmail_token = db.get_gmail_token(user_id) if user_id else None
    if gmail_token:
        service = EmailNotificationService(
            gmail_service=GmailService(refresh_token=gmail_token.refresh_token),
            db_client=db,
        )
    else:
        service = EmailNotificationService(db_client=db)
        print("[WARN] gmail_tokens 未登録。ローカルトークンファイルで Gmail に接続します。")

    if user_id:
        failed += verify_dry_run(service, user_id, max_results=args.max_results)
    else:
        failed += 1

    if args.send:
        line_user_id = settings.line_user_id
        if not line_user_id:
            ng("--send には .env の LINE_USER_ID が必要です")
            failed += 1
        elif not user_id:
            failed += 1
        else:
            failed += verify_send(service, line_user_id, user_id)
    else:
        print("\n=== 4. 実送信 ===")
        ok("スキップ（--send を指定すると未処理 1 件を送信）")

    print("\n=== 結果 ===")
    if failed:
        ng(f"{failed} 件のテストが失敗しました")
        return 1

    ok("すべてのテストが成功しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
