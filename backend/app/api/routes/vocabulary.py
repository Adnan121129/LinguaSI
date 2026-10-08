from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics import srs
from app.api.deps import Pagination, ai_rate_limit, get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.common import Message, Page
from app.schemas.vocabulary import (
    AddWordRequest,
    CompleteSessionRequest,
    CompleteSessionResponse,
    ExplainResponse,
    ReviewRequest,
    ReviewResponse,
    TodayResponse,
    UserWordOut,
    VocabularyItemOut,
)
from app.services import vocabulary_service

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


@router.get("/today", response_model=TodayResponse, summary="Today's adaptive review session")
def today(focus: str | None = Query(None, pattern="^(collocation)$"), user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> TodayResponse:
    return TodayResponse(**vocabulary_service.today(db, user, focus))


@router.post("/review", response_model=ReviewResponse, summary="Answer one exercise (spaced repetition update)")
def review(payload: ReviewRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReviewResponse:
    result = vocabulary_service.review(db, user, payload.exercise_id, payload.answer, payload.response_ms, payload.hinted)
    return ReviewResponse(
        correct=result["correct"],
        correct_answer=result["correct_answer"],
        feedback=result["feedback"],
        state_before=result["state_before"],
        state_after=result["state_after"],
        next_review_at=result["next_review_at"],
        item=VocabularyItemOut.model_validate(result["item"]),
        xp_gained=result["xp_gained"],
        mission_progress=result["mission_progress"],
    )


@router.post("/session/complete", response_model=CompleteSessionResponse, summary="Finish a review session (updates SI Core)")
def complete(payload: CompleteSessionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CompleteSessionResponse:
    return CompleteSessionResponse(**vocabulary_service.complete_session(db, user, payload.started_at, payload.duration_seconds))


@router.post("/words/{user_vocab_id}/known", response_model=Message, summary="Mark a word as already known (too easy)")
def known(user_vocab_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Message:
    vocabulary_service.mark_known(db, user, user_vocab_id)
    return Message(message="Marked as known - SI will show it rarely.")


@router.get("/words", response_model=Page[UserWordOut])
def words(
    state: str | None = Query(None, pattern="^(new|learning|familiar|strong|mastered)$"),
    pagination: Pagination = Depends(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[UserWordOut]:
    rows, total = vocabulary_service.words(db, user, state, pagination.page, pagination.page_size)
    items = [
        UserWordOut(
            user_vocab_id=uv.id,
            item=VocabularyItemOut.model_validate(uv.item),
            state=uv.state,
            correct_count=uv.correct_count,
            incorrect_count=uv.incorrect_count,
            due_at=uv.due_at,
            last_reviewed_at=uv.last_reviewed_at,
            used_in_writing=uv.used_in_writing,
            used_in_speaking=uv.used_in_speaking,
            reason=uv.reason,
            reason_detail=uv.reason_detail,
            classification=srs.classify(uv),
        )
        for uv in rows
    ]
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.post("/words", response_model=Message, summary="Add a word from the word bank")
def add_word(payload: AddWordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Message:
    vocabulary_service.add_word(db, user, payload.item_id)
    return Message(message="Word added to your reviews.")


@router.get("/bank", summary="Browse the word bank")
def bank(
    topic: str | None = Query(None, max_length=40),
    q: str | None = Query(None, max_length=60),
    pagination: Pagination = Depends(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rows, total, owned = vocabulary_service.bank(db, user, topic, q, pagination.page, pagination.page_size)
    return {
        "items": [VocabularyItemOut.model_validate(r).model_dump() | {"owned": r.id in owned} for r in rows],
        "total": total,
        "page": pagination.page,
        "page_size": pagination.page_size,
    }


@router.get("/insights", summary="Vocabulary strength, retention and adaptive classifications")
def insights(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return vocabulary_service.insights(db, user)


@router.post("/items/{item_id}/explain", response_model=ExplainResponse, summary="SI explanation of a word in context")
def explain(item_id: int, user: User = Depends(ai_rate_limit), db: Session = Depends(get_db)) -> ExplainResponse:
    return ExplainResponse(**vocabulary_service.explain(db, user, item_id))
