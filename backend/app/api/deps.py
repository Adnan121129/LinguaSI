"""Shared FastAPI dependencies: authentication, authorisation, pagination and AI rate limits."""

from __future__ import annotations

from datetime import timedelta

import jwt
from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.clock import ensure_aware, utcnow
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AuthError, ForbiddenError
from app.core.rate_limit import enforce
from app.core.security import decode_access_token
from app.models import AuthSession, User

_bearer = HTTPBearer(auto_error=False, description="Access token from /auth/login or /auth/register")


def current_session_id(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> int | None:
    """The refresh session behind the caller's access token (tokens issued before sessions were named have none)."""
    if credentials is None:
        return None
    try:
        sid = decode_access_token(credentials.credentials).get("sid")
    except jwt.PyJWTError:
        return None
    return sid if isinstance(sid, int) else None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise AuthError()
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Your session has expired. Please sign in again.", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid authentication token.", code="invalid_token") from exc
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise AuthError("Invalid authentication token.", code="invalid_token") from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("Your account is not available.", code="account_unavailable")
    sid = payload.get("sid")
    if isinstance(sid, int):
        session = db.get(AuthSession, sid)
        # An access token ends with its session: signed out, password changed on another device, or ended
        # after token theft. A rotated session has not ended; the token's holder simply refreshed.
        if session is None or (session.revoked_at is not None and session.replaced_by_id is None):
            raise AuthError("Your session has ended. Please sign in again.", code="session_revoked")
    now = utcnow()
    last = ensure_aware(user.last_active_at)
    if last is None or now - last > timedelta(minutes=5):
        user.last_active_at = now
        db.commit()
    return user


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise ForbiddenError("Admin access required.")
    return user


class Pagination:
    def __init__(
        self,
        page: int = Query(1, ge=1, le=10_000),
        page_size: int = Query(20, ge=1, le=100),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def ai_rate_limit(user: User = Depends(get_current_user)) -> User:
    """Per-learner cap on AI-heavy requests (cost control and abuse protection)."""
    enforce(
        f"ai:{user.id}",
        settings.ai_user_hourly_limit,
        3600,
        "You've reached the hourly limit for AI-powered activities. Please try again later.",
    )
    return user
