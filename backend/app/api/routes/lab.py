"""English Lab: daily English, pronunciation, sentence building and conversation scenarios."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.lab import (
    DailyPhrase,
    LabOverview,
    PronunciationCheckRequest,
    PronunciationCheckResult,
    PronunciationSet,
    Scenario,
)
from app.schemas.practice import PracticeSetOut
from app.services import lab_service, practice_service
from app.services.content import conversation_scenarios, pronunciation_sets

router = APIRouter(prefix="/lab", tags=["lab"])


@router.get("", response_model=LabOverview, summary="English Lab sections and today's phrase")
def overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> LabOverview:
    return LabOverview(**lab_service.overview(db, user))


@router.get("/daily", response_model=DailyPhrase, summary="Today's everyday English expression")
def daily(user: User = Depends(get_current_user)) -> DailyPhrase:
    return DailyPhrase(**lab_service.daily_phrase(user))


@router.post(
    "/daily/quiz", response_model=PracticeSetOut, status_code=status.HTTP_201_CREATED, summary="A 3-question quiz on today's phrase and two review phrases"
)
def daily_quiz(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PracticeSetOut:
    return practice_service.practice_out(lab_service.daily_quiz(db, user))


@router.get("/pronunciation", response_model=list[PronunciationSet], summary="Listen-and-repeat sentence sets by sound focus")
def pronunciation(user: User = Depends(get_current_user)) -> list[PronunciationSet]:
    return [PronunciationSet(**s) for s in pronunciation_sets()]


@router.post("/pronunciation/check", response_model=PronunciationCheckResult, summary="Compare what speech recognition heard with the target sentence")
def pronunciation_check(payload: PronunciationCheckRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PronunciationCheckResult:
    return PronunciationCheckResult(**lab_service.check_pronunciation(db, user, payload.sentence, payload.transcript, payload.duration_seconds))


@router.get("/scenarios", response_model=list[Scenario], summary="Role-play scenarios for conversation practice")
def scenarios(user: User = Depends(get_current_user)) -> list[Scenario]:
    return [Scenario(**{k: s[k] for k in ("id", "title", "level", "ai_role", "goal", "phrases")}) for s in conversation_scenarios()]


@router.post(
    "/sentence-building",
    response_model=PracticeSetOut,
    status_code=status.HTTP_201_CREATED,
    summary="Unscramble natural sentences built from the vocabulary bank",
)
def sentence_building(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PracticeSetOut:
    return practice_service.practice_out(lab_service.sentence_building(db, user))
