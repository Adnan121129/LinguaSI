from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import Pagination, ai_rate_limit, get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.common import Page
from app.schemas.comprehension import (
    AttemptSummary,
    ListeningAttemptOut,
    ListeningGenerateRequest,
    ListeningSubmitResponse,
    ReadingAttemptOut,
    ReadingGenerateRequest,
    ReadingSubmitResponse,
    SubmitAnswersRequest,
)
from app.services import listening_service, reading_service

reading_router = APIRouter(prefix="/reading", tags=["reading"])
listening_router = APIRouter(prefix="/listening", tags=["listening"])


@reading_router.post(
    "/generate", response_model=ReadingAttemptOut, status_code=status.HTTP_201_CREATED, summary="Generate (or select) a reading exercise and start an attempt"
)
def reading_generate(payload: ReadingGenerateRequest, user: User = Depends(ai_rate_limit), db: Session = Depends(get_db)) -> ReadingAttemptOut:
    attempt, notice = reading_service.generate(
        db,
        user,
        difficulty=payload.difficulty,
        topic=payload.topic,
        question_count=payload.question_count,
        time_limit=payload.time_limit_minutes,
        module=payload.module,
        question_types=payload.question_types,
    )
    return reading_service.attempt_out(db, user, attempt, notice)


@reading_router.get("/attempts/{attempt_id}", response_model=ReadingAttemptOut)
def reading_attempt(attempt_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReadingAttemptOut:
    return reading_service.attempt_out(db, user, reading_service.get(db, user, attempt_id))


@reading_router.post("/submit", response_model=ReadingSubmitResponse, summary="Submit answers for scoring")
def reading_submit(payload: SubmitAnswersRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReadingSubmitResponse:
    attempt, outcome = reading_service.submit(db, user, payload.attempt_id, payload.answers, payload.time_spent_seconds)
    return ReadingSubmitResponse(attempt=reading_service.attempt_out(db, user, attempt), outcome=outcome)


@reading_router.get("/history", response_model=Page[AttemptSummary])
def reading_history(pagination: Pagination = Depends(), user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Page[AttemptSummary]:
    rows, total = reading_service.history(db, user, pagination.page, pagination.page_size)
    items = [
        AttemptSummary(
            id=a.id,
            title=a.passage.title,
            topic=a.passage.topic,
            difficulty=a.difficulty,
            status=a.status,
            correct=a.correct,
            total=a.total,
            accuracy=a.accuracy,
            band=a.band,
            started_at=a.started_at,
            submitted_at=a.submitted_at,
        )
        for a in rows
    ]
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@listening_router.post(
    "/generate",
    response_model=ListeningAttemptOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate (or select) a listening exercise and start an attempt",
)
def listening_generate(payload: ListeningGenerateRequest, user: User = Depends(ai_rate_limit), db: Session = Depends(get_db)) -> ListeningAttemptOut:
    attempt, notice = listening_service.generate(
        db,
        user,
        difficulty=payload.difficulty,
        topic=payload.topic,
        scenario=payload.scenario,
        question_count=payload.question_count,
        time_limit=payload.time_limit_minutes,
        accent=payload.accent,
        question_types=payload.question_types,
    )
    return listening_service.attempt_out(db, attempt, notice)


@listening_router.get("/attempts/{attempt_id}", response_model=ListeningAttemptOut)
def listening_attempt(attempt_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ListeningAttemptOut:
    return listening_service.attempt_out(db, listening_service.get(db, user, attempt_id))


@listening_router.post("/attempts/{attempt_id}/replay", summary="Record that the audio was replayed")
def listening_replay(attempt_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return {"replays": listening_service.record_replay(db, user, attempt_id)}


@listening_router.get("/audio/{script_id}/{segment}", summary="Stream a synthesized audio segment")
def listening_audio(script_id: int, segment: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    data, mime = listening_service.audio(db, user, script_id, segment)
    return Response(content=data, media_type=mime, headers={"Cache-Control": "private, max-age=86400"})


@listening_router.post("/submit", response_model=ListeningSubmitResponse, summary="Submit answers for scoring")
def listening_submit(payload: SubmitAnswersRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ListeningSubmitResponse:
    attempt, outcome = listening_service.submit(db, user, payload.attempt_id, payload.answers, payload.time_spent_seconds, payload.replays)
    return ListeningSubmitResponse(attempt=listening_service.attempt_out(db, attempt), outcome=outcome)


@listening_router.get("/history", response_model=Page[AttemptSummary])
def listening_history(pagination: Pagination = Depends(), user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Page[AttemptSummary]:
    rows, total = listening_service.history(db, user, pagination.page, pagination.page_size)
    items = [
        AttemptSummary(
            id=a.id,
            title=a.script.title,
            topic=a.script.topic,
            difficulty=a.difficulty,
            status=a.status,
            correct=a.correct,
            total=a.total,
            accuracy=a.accuracy,
            band=a.band,
            started_at=a.started_at,
            submitted_at=a.submitted_at,
        )
        for a in rows
    ]
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)
