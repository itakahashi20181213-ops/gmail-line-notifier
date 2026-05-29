"""Gmail → 未処理判定 → AI 要約 → LINE 通知 → Supabase 保存の統合パイプライン。

使い方:
    .\\.venv\\Scripts\\python mail_pipeline.py
    .\\.venv\\Scripts\\python mail_pipeline.py --send
    .\\.venv\\Scripts\\python mail_pipeline.py --ignore-send-hour --line-user-id Uxxxx
    .\\.venv\\Scripts\\python mail_pipeline.py --scheduler
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.db.client import SupabaseClient
from app.gmail.exceptions import is_gmail_auth_error
from app.gmail.service import GmailService
from app.services.email_notification_service import (
    EmailNotificationService,
    NotificationResult,
)
from app.services.relink_service import RelinkService

logger = logging.getLogger(__name__)


@dataclass
class UserPipelineResult:
    line_user_id: str
    send_hour: int | None = None
    notifications: list[NotificationResult] = field(default_factory=list)

    @property
    def sent_count(self) -> int:
        return sum(1 for item in self.notifications if item.sent)

    @property
    def skipped_count(self) -> int:
        return sum(1 for item in self.notifications if item.skipped)

    @property
    def failed_count(self) -> int:
        return sum(
            1
            for item in self.notifications
            if not item.sent and not item.skipped
        )


@dataclass
class MailPipelineResult:
    ran_at: datetime
    current_hour: int
    user_results: list[UserPipelineResult] = field(default_factory=list)
    used_fallback_line_user: bool = False

    @property
    def total_sent(self) -> int:
        return sum(result.sent_count for result in self.user_results)

    @property
    def total_failed(self) -> int:
        return sum(result.failed_count for result in self.user_results)


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )


def resolve_target_users(
    db: SupabaseClient,
    *,
    ignore_send_hour: bool,
    line_user_id: str | None,
) -> tuple[list[tuple[str, int | None]], bool]:
    """通知対象の (line_user_id, send_hour) 一覧を返す。"""
    if line_user_id:
        return [(line_user_id.strip(), None)], False

    if ignore_send_hour:
        users = db.get_users()
        if users:
            return [(user.line_user_id, user.send_hour) for user in users], False

        settings = get_settings()
        if settings.line_user_id:
            return [(settings.line_user_id, None)], True
        return [], False

    users = db.get_users_for_current_send_hour()
    if users:
        return [(user.line_user_id, user.send_hour) for user in users], False

    settings = get_settings()
    if settings.line_user_id:
        logger.info(
            "send_hour 一致ユーザーなし。LINE_USER_ID フォールバックを使用します。"
        )
        return [(settings.line_user_id, None)], True

    return [], False


def run_mail_pipeline(
    *,
    max_results: int = 5,
    line_user_id: str | None = None,
    ignore_send_hour: bool = False,
    dry_run: bool = False,
    db_client: SupabaseClient | None = None,
    notification_service: EmailNotificationService | None = None,
) -> MailPipelineResult:
    """パイプライン本体: 対象ユーザーごとに未処理メールを要約して LINE へ送信する。"""
    now = datetime.now()
    db = db_client or SupabaseClient()
    if notification_service is not None:
        logger.warning(
            "notification_service 引数は Phase 1 では未使用です（ユーザーごとに GmailService を生成します）"
        )

    targets, used_fallback = resolve_target_users(
        db,
        ignore_send_hour=ignore_send_hour,
        line_user_id=line_user_id,
    )

    pipeline_result = MailPipelineResult(
        ran_at=now,
        current_hour=now.hour,
        used_fallback_line_user=used_fallback,
    )

    if not targets:
        logger.warning(
            "通知対象がありません (hour=%d)。users の send_hour または LINE_USER_ID を確認してください。",
            now.hour,
        )
        return pipeline_result

    for target_line_user_id, send_hour in targets:
        user_result = UserPipelineResult(
            line_user_id=target_line_user_id,
            send_hour=send_hour,
        )

        user = db.get_user_by_line_user_id(target_line_user_id)
        if user is None:
            logger.warning(
                "users に未登録のためスキップ: line_user_id=%s",
                target_line_user_id,
            )
            pipeline_result.user_results.append(user_result)
            continue

        gmail_token = db.get_gmail_token(user.id)
        if gmail_token is None:
            logger.warning(
                "Gmail 未連携のためスキップ: line_user_id=%s user_id=%s",
                target_line_user_id,
                user.id,
            )
            pipeline_result.user_results.append(user_result)
            continue

        user_service = EmailNotificationService(
            gmail_service=GmailService(refresh_token=gmail_token.refresh_token),
            db_client=db,
        )

        try:
            if dry_run:
                emails = user_service.gmail.get_recent_inbox_emails(
                    max_results=max_results
                )
                unprocessed = user_service.filter_unprocessed_emails(emails, user.id)
                logger.info(
                    "dry-run: line_user_id=%s gmail=%s total=%d unprocessed=%d",
                    target_line_user_id,
                    gmail_token.gmail_email,
                    len(emails),
                    len(unprocessed),
                )
                for email in unprocessed:
                    user_result.notifications.append(
                        NotificationResult(
                            gmail_message_id=email.gmail_message_id,
                            subject=email.subject,
                            sent=False,
                            skipped=True,
                        )
                    )
            else:
                notifications = user_service.send_unprocessed_emails(
                    target_line_user_id,
                    user.id,
                    max_results=max_results,
                )
                user_result.notifications.extend(notifications)
                logger.info(
                    "完了: line_user_id=%s gmail=%s sent=%d skipped=%d failed=%d",
                    target_line_user_id,
                    gmail_token.gmail_email,
                    user_result.sent_count,
                    user_result.skipped_count,
                    user_result.failed_count,
                )
        except Exception as exc:
            if is_gmail_auth_error(exc):
                logger.warning(
                    "Gmail 認証失敗: line_user_id=%s user_id=%s error=%s",
                    target_line_user_id,
                    user.id,
                    exc,
                )
                RelinkService(db_client=db).notify_token_expired(
                    user,
                    reason=str(exc),
                )
            else:
                logger.exception(
                    "ユーザー処理中にエラー: line_user_id=%s user_id=%s",
                    target_line_user_id,
                    user.id,
                )
                user_result.notifications.append(
                    NotificationResult(
                        gmail_message_id="",
                        subject="(Gmail 取得失敗)",
                        sent=False,
                        error=str(exc),
                    )
                )

        pipeline_result.user_results.append(user_result)

    return pipeline_result


def run_scheduler_loop() -> None:
    """設定間隔でパイプラインを定期実行する（FastAPI ライフサイクルと同等）。"""
    from app.scheduler.tasks import setup_scheduler, shutdown_scheduler

    settings = get_settings()
    scheduler = setup_scheduler()
    interval = settings.gmail_poll_interval_minutes

    print(f"スケジューラ起動: {interval} 分ごとに mail_pipeline を実行")
    print("停止するには Ctrl+C を押してください。")

    try:
        import time

        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nスケジューラを停止しています...")
    finally:
        shutdown_scheduler()
        if scheduler is not None:
            del scheduler


def print_summary(result: MailPipelineResult, *, dry_run: bool) -> None:
    mode = "dry-run" if dry_run else "実行"
    print(f"\n=== パイプライン結果 ({mode}) ===")
    print(f"実行時刻: {result.ran_at:%Y-%m-%d %H:%M:%S}")
    print(f"現在 hour: {result.current_hour}")
    if result.used_fallback_line_user:
        print("フォールバック: .env の LINE_USER_ID を使用")

    if not result.user_results:
        print("対象ユーザー: なし")
        return

    for user_result in result.user_results:
        hour_label = (
            str(user_result.send_hour)
            if user_result.send_hour is not None
            else "-"
        )
        print(
            f"\n--- {user_result.line_user_id} (send_hour={hour_label}) ---"
        )
        print(
            f"送信: {user_result.sent_count} / "
            f"スキップ: {user_result.skipped_count} / "
            f"失敗: {user_result.failed_count}"
        )
        for item in user_result.notifications:
            if item.sent:
                status = "送信"
            elif dry_run and item.skipped:
                status = "未処理"
            elif item.skipped:
                status = "スキップ"
            else:
                status = "失敗"
            subject = item.subject or "(件名なし)"
            print(f"  [{status}] {subject}")
            if item.error:
                print(f"         エラー: {item.error}")

    print(
        f"\n合計: 送信 {result.total_sent} / 失敗 {result.total_failed}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gmail メール要約 LINE 通知パイプライン"
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Gmail 取得件数（デフォルト: 5）",
    )
    parser.add_argument(
        "--line-user-id",
        help="特定の LINE ユーザー ID のみ通知（send_hour フィルタを無視）",
    )
    parser.add_argument(
        "--ignore-send-hour",
        action="store_true",
        help="全ユーザーを対象にする（send_hour フィルタなし）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Gmail 取得と未処理判定のみ（要約・LINE・DB 保存なし）",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="要約と LINE 送信を実行（未指定時は dry-run と同様に送信しない）",
    )
    parser.add_argument(
        "--scheduler",
        action="store_true",
        help="APScheduler で定期実行（uvicorn 起動時と同じ設定）",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="詳細ログを出力",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(verbose=args.verbose)

    settings = get_settings()
    dry_run = args.dry_run or not args.send

    if args.scheduler:
        if dry_run:
            print("[NG] --scheduler は --dry-run と併用できません")
            return 1
        run_scheduler_loop()
        return 0

    print("=== Mail Pipeline ===")
    print(f"Gmail: {settings.gmail_user_email or '(ユーザーごとの gmail_tokens)'}")
    print(f"モデル: {settings.openai_model}")
    if args.line_user_id:
        print(f"対象: {args.line_user_id}（明示指定）")
    elif args.ignore_send_hour:
        print("対象: 全ユーザー（--ignore-send-hour）")
    else:
        print(f"対象: send_hour={datetime.now().hour} に一致するユーザー")

    if args.send and not args.dry_run:
        print("モード: 送信（要約 + LINE + DB 保存）")
    else:
        print("モード: dry-run（Gmail 取得と未処理判定のみ）")

    try:
        result = run_mail_pipeline(
            max_results=args.max_results,
            line_user_id=args.line_user_id,
            ignore_send_hour=args.ignore_send_hour,
            dry_run=dry_run,
        )
    except Exception as exc:
        logger.exception("パイプライン実行中にエラーが発生しました")
        print(f"[NG] {exc}")
        return 1

    print_summary(result, dry_run=dry_run)

    if result.total_failed > 0:
        print(f"\n[NG] {result.total_failed} 件の通知に失敗しました")
        return 1

    print("\n[OK] パイプラインが正常に完了しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
