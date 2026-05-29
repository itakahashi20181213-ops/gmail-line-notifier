import logging

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import get_settings
from mail_pipeline import run_mail_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cron", tags=["cron"])


def _verify_cron_secret(authorization: str | None) -> None:
    settings = get_settings()
    secret = (settings.cron_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="CRON_SECRET が設定されていません。",
        )
    expected = f"Bearer {secret}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/mail-pipeline")
async def cron_mail_pipeline(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    """Vercel Cron から呼ばれるメール通知パイプライン。"""
    _verify_cron_secret(authorization)

    logger.info("Vercel Cron: mail_pipeline 開始")
    result = run_mail_pipeline(max_results=5, ignore_send_hour=True)
    logger.info(
        "Vercel Cron: mail_pipeline 完了 sent=%d failed=%d",
        result.total_sent,
        result.total_failed,
    )
    return {
        "status": "ok",
        "total_sent": result.total_sent,
        "total_failed": result.total_failed,
        "user_count": len(result.user_results),
    }
