"""Onboarding, diagnostic, dashboard, progress, recommendations, missions and achievements."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import ai_rate_limit, get_current_user
from app.core.clock import utcnow
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models import Recommendation, User
from app.schemas.auth import UserOut
from app.schemas.common import Message
from app.schemas.onboarding import DiagnosticResult, DiagnosticStartResponse, DiagnosticSubmitRequest, OnboardingRequest
from app.services import dashboard_service, diagnostic_service

onboarding_router = APIRouter(tags=["onboarding"])
dashboard_router = APIRouter(tags=["dashboard"])
progress_router = APIRouter(tags=["progress"])
recommendations_router = APIRouter(tags=["recommendations"])
gamification_router = APIRouter(tags=["gamification"])


@onboarding_router.post("/onboarding", response_model=UserOut, summary="Save goals and preferences from onboarding")
def onboarding(payload: OnboardingRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    return UserOut.model_validate(diagnostic_service.complete_onboarding(db, user, payload))


@onboarding_router.post(
    "/diagnostic/start", response_model=DiagnosticStartResponse, status_code=status.HTTP_201_CREATED, summary="Start (or resume) the diagnostic assessment"
)
def diagnostic_start(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DiagnosticStartResponse:
    attempt, public = diagnostic_service.start(db, user)
    return DiagnosticStartResponse(attempt_id=attempt.id, started_at=attempt.started_at, **public)


@onboarding_router.post("/diagnostic/{attempt_id}/submit", response_model=DiagnosticResult, summary="Submit the diagnostic and receive your AI Estimated Level")
def diagnostic_submit(
    attempt_id: int, payload: DiagnosticSubmitRequest, user: User = Depends(ai_rate_limit), db: Session = Depends(get_db)
) -> DiagnosticResult:
    return diagnostic_service.submit(db, user, attempt_id, payload.answers, payload.writing, payload.speaking)


@onboarding_router.get("/diagnostic/latest", response_model=DiagnosticResult)
def diagnostic_latest(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DiagnosticResult:
    result = diagnostic_service.latest(db, user)
    if result is None:
        raise NotFoundError("You haven't completed the diagnostic yet.", code="no_diagnostic")
    return result


@dashboard_router.get("/dashboard", summary="Personalised dashboard driven by SI Core")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return dashboard_service.dashboard(db, user)


@progress_router.get("/progress", summary="Progress analytics; every chart answers a learner question")
def progress(days: int = Query(30, ge=7, le=180), user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return dashboard_service.progress(db, user, days)


@recommendations_router.get("/recommendations", summary="Personalised recommendations with 'Why this?' explanations")
def recommendations(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return [dashboard_service.rec_out(r) for r in dashboard_service.active_recommendations(db, user, limit=8)]


@recommendations_router.post("/recommendations/{rec_id}/dismiss", response_model=Message)
def dismiss(rec_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Message:
    rec = db.get(Recommendation, rec_id)
    if rec is None or rec.user_id != user.id:
        raise NotFoundError("Recommendation not found.")
    rec.status = "dismissed"
    rec.completed_at = utcnow()
    db.commit()
    return Message(message="Recommendation dismissed.")


@gamification_router.get("/missions", summary="Today's AI daily mission and weekly challenges")
def missions(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return dashboard_service.missions(db, user)


@gamification_router.get("/achievements", summary="Achievements, level and XP history")
def achievements(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return dashboard_service.achievements(db, user)
