"""Lightweight admin panel API. Every endpoint requires an admin account."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import Pagination, get_admin_user
from app.core.database import get_db
from app.models import User
from app.schemas.admin import UserUpdateRequest, VocabularyCreateRequest
from app.schemas.common import Page
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])

CONTENT_KIND = "^(vocabulary|grammar|reading|listening|writing|speaking)$"


@router.get("/overview", summary="Platform health: users, activity, AI usage, content and errors")
def overview(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict:
    return admin_service.overview(db)


@router.get("/users", response_model=Page[dict])
def users(
    q: str | None = Query(None, max_length=100),
    role: str | None = Query(None, pattern="^(learner|admin)$"),
    active: bool | None = None,
    pagination: Pagination = Depends(),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Page[dict]:
    items, total = admin_service.list_users(db, q=q, role=role, active=active, page=pagination.page, page_size=pagination.page_size)
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/users/{user_id}")
def user_detail(user_id: int, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict:
    return admin_service.user_detail(db, user_id)


@router.patch("/users/{user_id}", summary="Activate/deactivate a user or change their role")
def update_user(user_id: int, payload: UserUpdateRequest, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict:
    return admin_service.update_user(db, admin, user_id, is_active=payload.is_active, role=payload.role)


@router.get("/content/{kind}", response_model=Page[dict], summary="Browse content by type")
def content(
    kind: str,
    q: str | None = Query(None, max_length=100),
    active: bool | None = None,
    source: str | None = Query(None, pattern="^(seed|ai|template|edited|admin)$"),
    pagination: Pagination = Depends(),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Page[dict]:
    items, total = admin_service.list_content(db, kind, q=q, active=active, source=source, page=pagination.page, page_size=pagination.page_size)
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.post("/content/vocabulary", status_code=status.HTTP_201_CREATED, summary="Add a word to the vocabulary bank")
def create_vocabulary(payload: VocabularyCreateRequest, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict:
    return admin_service.create_vocabulary(db, admin, payload.model_dump())


@router.get("/content/{kind}/{item_id}")
def content_detail(kind: str, item_id: int, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict:
    return admin_service.content_detail(db, kind, item_id)


@router.patch("/content/{kind}/{item_id}", summary="Edit allowed fields or hide/show an item for learners")
def update_content(
    kind: str,
    item_id: int,
    changes: dict[str, Any] = Body(..., examples=[{"is_active": False}]),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    return admin_service.update_content(db, admin, kind, item_id, changes)


@router.get("/evaluations", response_model=Page[dict], summary="Recent AI writing or speaking evaluations (metadata only)")
def evaluations(
    kind: str = Query("writing", pattern="^(writing|speaking)$"),
    pagination: Pagination = Depends(),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Page[dict]:
    items, total = admin_service.list_evaluations(db, kind, pagination.page, pagination.page_size)
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/ai-usage", summary="AI calls, failures, latency and tokens by task and model")
def ai_usage(days: int = Query(7, ge=1, le=90), admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict:
    return admin_service.ai_usage(db, days)


@router.get("/logs", response_model=Page[dict], summary="System logs")
def logs(
    level: str | None = Query(None, pattern="^(debug|info|warning|error|critical)$"),
    source: str | None = Query(None, max_length=60),
    pagination: Pagination = Depends(),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Page[dict]:
    items, total = admin_service.list_logs(db, level=level, source=source, page=pagination.page, page_size=pagination.page_size)
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.post("/seed", summary="Reload curated seed content (idempotent; keeps admin edits)")
def seed(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict:
    return {"loaded": admin_service.run_seed(db, admin)}
