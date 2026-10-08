from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import ServiceUnavailableError

router = APIRouter(tags=["system"])


@router.get("/health", summary="Liveness probe")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


@router.get("/health/ready", summary="Readiness probe (checks the database)")
def ready(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise ServiceUnavailableError("Database is not reachable.") from exc
    return {"status": "ready"}


@router.get("/meta", summary="Public runtime configuration used by the clients")
def meta() -> dict:
    return {
        "app": settings.app_name,
        "environment": settings.environment,
        "ai": {
            "provider": settings.effective_ai_provider,
            "mock_mode": settings.ai_is_mock,
            "configured_provider": settings.ai_provider,
        },
        "speech": {
            "stt_provider": settings.effective_stt_provider,
            "tts_provider": settings.effective_tts_provider,
        },
        "disclaimer": (
            "LinguaSI provides AI Estimated Bands for practice only. They are not official IELTS results "
            "and do not guarantee any test, admission or immigration outcome."
        ),
    }
