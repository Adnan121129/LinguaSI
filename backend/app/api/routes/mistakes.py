from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import Pagination, get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.common import Page
from app.schemas.practice import (
    CreatePracticeRequest,
    MistakeDetail,
    MistakeOut,
    MistakeStatusRequest,
    PracticeSetOut,
    SubmitPracticeRequest,
    SubmitPracticeResponse,
)
from app.services import practice_service

router = APIRouter(prefix="/mistakes", tags=["mistakes"])
practice_router = APIRouter(prefix="/practice", tags=["practice"])


@router.get("", response_model=Page[MistakeOut], summary="Your tracked mistakes across all skills")
def list_mistakes(
    status_filter: str | None = Query(None, alias="status", pattern="^(unresolved|corrected|mastered|due|recurring)$"),
    category: str | None = Query(None, max_length=30),
    source: str | None = Query(None, max_length=20),
    subcategory: str | None = Query(None, max_length=40),
    pagination: Pagination = Depends(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[MistakeOut]:
    items, total = practice_service.list_mistakes(
        db, user, status=status_filter, category=category, source=source, subcategory=subcategory, page=pagination.page, page_size=pagination.page_size
    )
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/summary", summary="Totals, most common mistakes, trends and heatmap")
def summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return practice_service.mistake_summary(db, user)


@router.post("/revision", response_model=PracticeSetOut, status_code=status.HTTP_201_CREATED, summary="Automatic revision session from your history")
def revision(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PracticeSetOut:
    return practice_service.practice_out(practice_service.revision_session(db, user))


@router.get("/{mistake_id}", response_model=MistakeDetail)
def detail(mistake_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MistakeDetail:
    return practice_service.mistake_detail(db, user, mistake_id)


@router.post("/{mistake_id}/practice", response_model=PracticeSetOut, status_code=status.HTTP_201_CREATED, summary="Mini practice for one mistake")
def practice(mistake_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PracticeSetOut:
    return practice_service.practice_out(practice_service.practice_for_mistake(db, user, mistake_id))


@router.post("/{mistake_id}/status", response_model=MistakeOut, summary="Mark as mastered, reopen, or revisit later")
def update_status(mistake_id: int, payload: MistakeStatusRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MistakeOut:
    m = practice_service.update_mistake_status(db, user, mistake_id, payload.status, payload.revisit_in_days)
    return practice_service.mistake_out(m)


@practice_router.get("/topics", summary="Practice focus areas available in the bank")
def topics(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return practice_service.practice_topics(db)


@practice_router.post("/sets", response_model=PracticeSetOut, status_code=status.HTTP_201_CREATED, summary="Create a focused practice set")
def create_set(payload: CreatePracticeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PracticeSetOut:
    ps = practice_service.create_practice(db, user, focus=payload.focus, kind=payload.kind, mistake_ids=payload.mistake_ids, item_count=payload.item_count)
    return practice_service.practice_out(ps)


@practice_router.get("/sets", response_model=Page[PracticeSetOut])
def list_sets(pagination: Pagination = Depends(), user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Page[PracticeSetOut]:
    rows, total = practice_service.list_practice(db, user, pagination.page, pagination.page_size)
    return Page(items=[practice_service.practice_out(r) for r in rows], total=total, page=pagination.page, page_size=pagination.page_size)


@practice_router.get("/sets/{practice_id}", response_model=PracticeSetOut)
def get_set(practice_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PracticeSetOut:
    return practice_service.practice_out(practice_service.get_practice(db, user, practice_id))


@practice_router.post("/sets/{practice_id}/submit", response_model=SubmitPracticeResponse)
def submit_set(
    practice_id: int, payload: SubmitPracticeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SubmitPracticeResponse:
    ps, mastered, outcome = practice_service.submit_practice(db, user, practice_id, payload.answers, payload.duration_seconds)
    return SubmitPracticeResponse(practice=practice_service.practice_out(ps), mastered_mistakes=mastered, outcome=outcome)
