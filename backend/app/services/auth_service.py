"""Registration, login, refresh-token rotation and logout."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.clock import ensure_aware, utcnow
from app.core.config import settings
from app.core.errors import AuthError, ConflictError
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    password_needs_rehash,
    verify_password,
)
from app.models import AuthSession, Profile, Streak, User

logger = logging.getLogger("linguasi.auth")

# Verifying against a dummy hash when the email is unknown keeps response timing uniform,
# which prevents account enumeration through login latency.
_DUMMY_HASH = hash_password("timing-equaliser-password-1")


@dataclass
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int


def _issue_tokens(db: Session, user: User, user_agent: str | None) -> IssuedTokens:
    access_token, expires_in = create_access_token(user.id, user.role)
    refresh_token = new_refresh_token()
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    return IssuedTokens(access_token, refresh_token, expires_in)


def register(db: Session, *, email: str, password: str, name: str, user_agent: str | None) -> tuple[User, IssuedTokens]:
    normalized = email.strip().lower()
    if db.scalar(select(User.id).where(User.email == normalized)):
        raise ConflictError("An account with this email already exists. Try signing in instead.", code="email_taken")
    admin_emails = {e.strip().lower() for e in settings.admin_emails}
    user = User(
        email=normalized,
        password_hash=hash_password(password),
        name=name,
        role="admin" if normalized in admin_emails else "learner",
    )
    user.profile = Profile()
    db.add(user)
    db.flush()
    db.add(Streak(user_id=user.id))
    tokens = _issue_tokens(db, user, user_agent)
    db.commit()
    db.refresh(user)
    logger.info("User registered id=%s", user.id)
    return user, tokens


def login(db: Session, *, email: str, password: str, user_agent: str | None) -> tuple[User, IssuedTokens]:
    normalized = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized))
    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise AuthError("Incorrect email or password.", code="invalid_credentials")
    if not verify_password(password, user.password_hash):
        raise AuthError("Incorrect email or password.", code="invalid_credentials")
    if not user.is_active:
        raise AuthError("This account has been deactivated.", code="account_inactive")
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_active_at = utcnow()
    tokens = _issue_tokens(db, user, user_agent)
    db.commit()
    return user, tokens


def refresh(db: Session, *, refresh_token: str, user_agent: str | None) -> tuple[User, IssuedTokens]:
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(refresh_token)))
    if session is None:
        raise AuthError("Your session has expired. Please sign in again.", code="invalid_refresh_token")
    now = utcnow()
    if session.revoked_at is not None:
        # A rotated token was presented again: treat as theft and end every session for this user.
        db.execute(update(AuthSession).where(AuthSession.user_id == session.user_id, AuthSession.revoked_at.is_(None)).values(revoked_at=now))
        db.commit()
        logger.warning("Refresh token reuse detected for user id=%s; all sessions revoked", session.user_id)
        raise AuthError("Your session is no longer valid. Please sign in again.", code="refresh_token_reused")
    if ensure_aware(session.expires_at) <= now:
        raise AuthError("Your session has expired. Please sign in again.", code="refresh_token_expired")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise AuthError()
    tokens = _issue_tokens(db, user, user_agent)
    db.flush()
    new_session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(tokens.refresh_token)))
    session.revoked_at = now
    session.last_used_at = now
    session.replaced_by_id = new_session.id if new_session else None
    db.commit()
    return user, tokens


def logout(db: Session, *, refresh_token: str | None, user: User | None = None) -> None:
    now = utcnow()
    if refresh_token:
        session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(refresh_token)))
        if session and session.revoked_at is None:
            session.revoked_at = now
    elif user is not None:
        db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=now))
    db.commit()


def change_password(db: Session, user: User, *, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise AuthError("Your current password is incorrect.", code="invalid_credentials")
    user.password_hash = hash_password(new_password)
    db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=utcnow()))
    db.commit()
