from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import Pagination, ai_rate_limit, get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.common import Message, Page
from app.schemas.writing import (
    AutosaveRequest,
    AutosaveResponse,
    EvaluateRequest,
    EvaluateResponse,
    GenerateTaskRequest,
    GenerateTaskResponse,
    HintRequest,
    HintResponse,
    StartSubmissionRequest,
    SubmissionOut,
    SubmissionSummary,
    WritingTaskOut,
)
from app.services import writing_service

router = APIRouter(prefix="/writing", tags=["writing"])


@router.get("/tasks", response_model=Page[WritingTaskOut], summary="Browse writing tasks (curated + your generated tasks)")
def list_tasks(
    task_type: str | None = Query(None, pattern="^(task1|task2|general)$"),
    module: str | None = Query(None, pattern="^(academic|general_training|general_english)$"),
    category: str | None = Query(None, max_length=40),
    pagination: Pagination = Depends(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[WritingTaskOut]:
    items, total = writing_service.list_tasks(
        db, user, task_type=task_type, module=module, category=category, page=pagination.page, page_size=pagination.page_size
    )
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/tasks/{task_id}", response_model=WritingTaskOut)
def get_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WritingTaskOut:
    return WritingTaskOut.model_validate(writing_service.get_task(db, user, task_id))


@router.post("/generate", response_model=GenerateTaskResponse, summary="Generate an original IELTS-style writing task")
def generate(payload: GenerateTaskRequest, user: User = Depends(ai_rate_limit), db: Session = Depends(get_db)) -> GenerateTaskResponse:
    task, notice = writing_service.generate_task(
        db, user, module=payload.module, task_type=payload.task_type, category=payload.category, topic=payload.topic, difficulty=payload.difficulty
    )
    return GenerateTaskResponse(task=WritingTaskOut.model_validate(task), notice=notice)


@router.post("/submissions", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED, summary="Start (or resume) a draft")
def start(payload: StartSubmissionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SubmissionOut:
    sub = writing_service.start_submission(db, user, payload.task_id, payload.mode)
    return writing_service.get_submission(db, user, sub.id)


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SubmissionOut:
    return writing_service.get_submission(db, user, submission_id)


@router.put("/submissions/{submission_id}", response_model=AutosaveResponse, summary="Autosave a draft")
def autosave(submission_id: int, payload: AutosaveRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AutosaveResponse:
    sub = writing_service.autosave(db, user, submission_id, payload.content, payload.time_spent_seconds)
    return AutosaveResponse(saved_at=sub.autosaved_at, word_count=sub.word_count)


@router.delete("/submissions/{submission_id}", response_model=Message)
def delete(submission_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Message:
    writing_service.delete_draft(db, user, submission_id)
    return Message(message="Draft deleted.")


@router.post("/submissions/{submission_id}/hint", response_model=HintResponse, summary="SI Tutor hints (tutor mode only, no model answers)")
def hint(submission_id: int, payload: HintRequest, user: User = Depends(ai_rate_limit), db: Session = Depends(get_db)) -> HintResponse:
    data, used = writing_service.hint(db, user, submission_id, payload.question, payload.content)
    return HintResponse(**data, hints_used=used)


@router.post("/evaluate", response_model=EvaluateResponse, summary="Submit for AI evaluation (AI Estimated Band)")
def evaluate(payload: EvaluateRequest, user: User = Depends(ai_rate_limit), db: Session = Depends(get_db)) -> EvaluateResponse:
    sub, outcome = writing_service.evaluate(db, user, payload.submission_id, payload.content, payload.time_spent_seconds)
    return EvaluateResponse(submission=writing_service.submission_out(db, sub), outcome=outcome)


@router.get("/history", response_model=Page[SubmissionSummary])
def history(pagination: Pagination = Depends(), user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Page[SubmissionSummary]:
    items, total = writing_service.history(db, user, pagination.page, pagination.page_size)
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)
