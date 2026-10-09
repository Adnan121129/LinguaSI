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

# How long after a rotation the previous refresh token is still accepted from parallel requests.
ROTATION_GRACE = timedelta(seconds=30)

# Verifying against a dummy hash when the email is unknown keeps response timing uniform,
# which prevents account enumeration through login latency.
_DUMMY_HASH = hash_password("timing-equaliser-password-1")


@dataclass
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    session_id: int


def _issue_tokens(db: Session, user: User, user_agent: str | None) -> IssuedTokens:
    refresh_token = new_refresh_token()
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(session)
    db.flush()
    # The access token names its refresh session ("sid") so account actions can tell this device apart.
    access_token, expires_in = create_access_token(user.id, user.role, {"sid": session.id})
    return IssuedTokens(access_token, refresh_token, expires_in, session.id)


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
        if session.replaced_by_id is None:
            # Ended deliberately (sign-out, password change, deactivation): just refuse it.
            raise AuthError("Your session has ended. Please sign in again.", code="session_revoked")
        if now - ensure_aware(session.revoked_at) > ROTATION_GRACE:
            # A rotated token was presented again later: treat as theft and end every session for this user.
            db.execute(update(AuthSession).where(AuthSession.user_id == session.user_id, AuthSession.revoked_at.is_(None)).values(revoked_at=now))
            db.commit()
            logger.warning("Refresh token reuse detected for user id=%s; all sessions revoked", session.user_id)
            raise AuthError("Your session is no longer valid. Please sign in again.", code="refresh_token_reused")
        # Rotated moments ago: a client that fires several requests just after its access token expired
        # sends the same refresh token with each, and only the first can rotate it. That is not theft, so
        # the others get tokens too, unless the session was ended deliberately in the meantime.
        successor = db.get(AuthSession, session.replaced_by_id)
        if successor is None or (successor.revoked_at is not None and successor.replaced_by_id is None):
            raise AuthError("Your session has ended. Please sign in again.", code="session_revoked")
    if ensure_aware(session.expires_at) <= now:
        raise AuthError("Your session has expired. Please sign in again.", code="refresh_token_expired")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise AuthError()
    tokens = _issue_tokens(db, user, user_agent)
    session.last_used_at = now
    if session.revoked_at is None:
        session.revoked_at = now
        session.replaced_by_id = tokens.session_id
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


def change_password(db: Session, user: User, *, current_password: str, new_password: str, keep_session_id: int | None = None) -> None:
    """Set a new password and sign out every other device. The session making the change stays signed in."""
    if not verify_password(current_password, user.password_hash):
        raise AuthError("Your current password is incorrect.", code="invalid_credentials")
    user.password_hash = hash_password(new_password)
    others = update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
    if keep_session_id is not None:
        others = others.where(AuthSession.id != keep_session_id)
    db.execute(others.values(revoked_at=utcnow()))
    db.commit()
