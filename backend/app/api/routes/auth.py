from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import client_ip, enforce, rate_limit
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenResponse, UserOut
from app.schemas.common import Message
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(user, tokens) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("register", 10, 3600))],
    summary="Create an account (email + password)",
)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user, tokens = auth_service.register(
        db,
        email=payload.email,
        password=payload.password,
        name=payload.name,
        user_agent=request.headers.get("user-agent"),
    )
    return _token_response(user, tokens)


@router.post("/login", response_model=TokenResponse, summary="Sign in and receive access + refresh tokens")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    enforce(f"login-ip:{client_ip(request)}", 30, 300, "Too many sign-in attempts. Please wait a few minutes.")
    enforce(f"login-email:{payload.email.lower()}", 10, 300, "Too many sign-in attempts. Please wait a few minutes.")
    user, tokens = auth_service.login(db, email=payload.email, password=payload.password, user_agent=request.headers.get("user-agent"))
    return _token_response(user, tokens)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("refresh", 60, 60))],
    summary="Rotate a refresh token and get a new access token",
)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user, tokens = auth_service.refresh(db, refresh_token=payload.refresh_token, user_agent=request.headers.get("user-agent"))
    return _token_response(user, tokens)


@router.post("/logout", response_model=Message, summary="Revoke a refresh token")
def logout(payload: LogoutRequest, db: Session = Depends(get_db)) -> Message:
    auth_service.logout(db, refresh_token=payload.refresh_token)
    return Message(message="Signed out.")
