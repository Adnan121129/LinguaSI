from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import Pagination, ai_rate_limit, get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.common import Message, Page
from app.schemas.speaking import (
    FinishRequest,
    FinishResponse,
    RespondResponse,
    SpeakingSessionOut,
    SpeakingSummary,
    StartSpeakingRequest,
    StartSpeakingResponse,
    TurnOut,
)
from app.services import speaking_service

router = APIRouter(prefix="/speaking", tags=["speaking"])


@router.post(
    "/session/start",
    response_model=StartSpeakingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start an IELTS-style speaking test (full or a single part)",
)
def start(payload: StartSpeakingRequest, user: User = Depends(ai_rate_limit), db: Session = Depends(get_db)) -> StartSpeakingResponse:
    session = speaking_service.start(db, user, payload.mode)
    out = speaking_service.session_out(session)
    return StartSpeakingResponse(session=out, turn=TurnOut(**session.current_question), speech=speaking_service.speech_capabilities())


@router.post("/session/respond", response_model=RespondResponse, summary="Send one answer (audio and/or transcript); the examiner replies with the next turn")
async def respond(
    session_id: int = Form(...),
    transcript: str | None = Form(None, max_length=6000),
    transcript_source: str | None = Form(None, pattern="^(browser|typed|device)$"),
    duration_seconds: float | None = Form(None, ge=0, le=600),
    pauses: str | None = Form(None, max_length=2000),
    audio: UploadFile | None = File(None),
    user: User = Depends(ai_rate_limit),
    db: Session = Depends(get_db),
) -> RespondResponse:
    audio_bytes = await audio.read() if audio is not None else None
    # The service does blocking database and AI work, so it runs in the threadpool, not on the event loop.
    t, nxt = await run_in_threadpool(
        speaking_service.respond,
        db,
        user,
        session_id,
        client_transcript=transcript,
        transcript_source=transcript_source,
        duration_seconds=duration_seconds,
        pauses_json=pauses,
        audio_bytes=audio_bytes or None,
        audio_mime=audio.content_type if audio is not None else None,
    )
    return RespondResponse(transcript=speaking_service.transcript_out(t), next=TurnOut(**nxt) if nxt else None, done=nxt is None)


@router.post("/session/finish", response_model=FinishResponse, summary="Finish the test and receive the AI estimated evaluation")
def finish(payload: FinishRequest, user: User = Depends(ai_rate_limit), db: Session = Depends(get_db)) -> FinishResponse:
    session, outcome = speaking_service.finish(db, user, payload.session_id)
    return FinishResponse(session=speaking_service.session_out(session), outcome=outcome)


@router.post("/session/{session_id}/abandon", response_model=Message)
def abandon(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Message:
    speaking_service.abandon(db, user, session_id)
    return Message(message="Session closed.")


@router.get("/sessions/{session_id}", response_model=SpeakingSessionOut)
def get_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SpeakingSessionOut:
    return speaking_service.get(db, user, session_id)


@router.get("/history", response_model=Page[SpeakingSummary])
def history(pagination: Pagination = Depends(), user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Page[SpeakingSummary]:
    items, total = speaking_service.history(db, user, pagination.page, pagination.page_size)
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/audio/{transcript_id}", summary="Replay a stored recording")
def audio(transcript_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    data, mime = speaking_service.audio(db, user, transcript_id)
    return Response(content=data, media_type=mime, headers={"Cache-Control": "private, max-age=3600"})
