from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings

_scheduler: BackgroundScheduler | None = None


def poll_gmail_and_notify():
    """Gmail 取得 → 未処理のみ AI 要約 → LINE 通知。"""
    from mail_pipeline import run_mail_pipeline

    run_mail_pipeline(max_results=5)


def setup_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    settings = get_settings()
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        poll_gmail_and_notify,
        trigger="interval",
        minutes=settings.gmail_poll_interval_minutes,
        id="poll_gmail",
        replace_existing=True,
    )
    _scheduler.start()
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
