"""Persist important server-side events for the admin panel (best effort, separate session)."""

from __future__ import annotations

import logging

from app.core.database import SessionLocal
from app.models import SystemLog

logger = logging.getLogger("linguasi.systemlog")


def record_system_log(level: str, source: str, message: str, context: dict | None = None) -> None:
    db = SessionLocal()
    try:
        db.add(SystemLog(level=level, source=source[:60], message=message[:2000], context=context or {}))
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Failed to write system log", exc_info=True)
    finally:
        db.close()
