"""Speaking mock tests: sessions, turn-by-turn responses (audio/STT or client transcript), evaluation."""

from __future__ import annotations

import json
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.agents import si_core, speaking_examiner
from app.agents.progress_analyst import SkillResult
from app.ai.providers.base import AIError
from app.ai.speech import SpeechUnavailableError, get_stt
from app.analytics.speaking_metrics import analyze_response
from app.core.clock import utcnow
from app.core.config import settings
from app.core.errors import AIUnavailableError, NotFoundError, ValidationAppError
from app.core.levels import band_to_score
from app.models import SpeakingSession, SpeakingTranscript, User
from app.schemas.speaking import SpeakingEvaluationOut, SpeakingSessionOut, SpeakingSummary, TranscriptOut, TurnOut
from app.services.storage import storage

logger = logging.getLogger("linguasi.speaking")

AUDIO_EXTENSIONS = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/aac": "aac",
    "video/webm": "webm",
}


def speech_capabilities() -> dict:
    return {"server_stt": settings.effective_stt_provider != "mock", "stt_provider": settings.effective_stt_provider}


def start(db: Session, user: User, mode: str) -> SpeakingSession:
    active = db.scalars(select(SpeakingSession).where(SpeakingSession.user_id == user.id, SpeakingSession.status == "in_progress")).all()
    for old in active:
        old.status = "abandoned"
    plan, targets = speaking_examiner.create_plan(db, user, mode)
    session = SpeakingSession(
        user_id=user.id,
        mode=mode,
        status="in_progress",
        topic=plan["topic"],
        plan=plan,
        current_part=plan["queue"][0]["part"],
        current_index=0,
        target_expressions=targets,
        started_at=utcnow(),
    )
    db.add(session)
    db.flush()
    session.current_question = speaking_examiner.first_turn(session)
    db.commit()
    return session


def _get(db: Session, user: User, session_id: int) -> SpeakingSession:
    session = db.scalar(
        select(SpeakingSession)
        .options(selectinload(SpeakingSession.transcripts), selectinload(SpeakingSession.evaluation))
        .where(SpeakingSession.id == session_id)
        .execution_options(populate_existing=True)
    )
    if session is None or session.user_id != user.id:
        raise NotFoundError("Speaking session not found.")
    return session


def respond(
    db: Session,
    user: User,
    session_id: int,
    *,
    client_transcript: str | None,
    transcript_source: str | None,
    duration_seconds: float | None,
    pauses_json: str | None,
    audio_bytes: bytes | None,
    audio_mime: str | None,
):
    session = _get(db, user, session_id)
    if session.status != "in_progress":
        raise ValidationAppError("This speaking session is not in progress.", code="session_closed")
    current = session.current_question or speaking_examiner.first_turn(session)
    if audio_bytes and len(audio_bytes) > settings.max_audio_upload_mb * 1024 * 1024:
        raise ValidationAppError(f"Recordings must be smaller than {settings.max_audio_upload_mb} MB.")

    text, source, confidence = (client_transcript or "").strip(), (transcript_source or "typed"), None
    stt = get_stt()
    if audio_bytes and stt.name != "mock":
        try:
            result = stt.transcribe(audio_bytes, audio_mime or "audio/webm", filename=f"answer.{AUDIO_EXTENSIONS.get(audio_mime or '', 'webm')}")
            if result.text:
                text, source, confidence = result.text, "stt", result.confidence
                if result.duration_seconds and not duration_seconds:
                    duration_seconds = result.duration_seconds
        except SpeechUnavailableError as exc:
            if not text:
                raise ValidationAppError(f"{exc} Please type your answer instead.", code="transcription_unavailable") from exc
    if not text:
        if audio_bytes:
            raise ValidationAppError(
                "Server transcription isn't configured, and no transcript was captured. Use live transcription in a supported browser or type your answer.",
                code="transcription_unavailable",
            )
        raise ValidationAppError("We didn't receive an answer. Please speak or type your response.", code="empty_answer")
    if source not in ("stt", "browser", "typed", "device"):
        source = "typed"

    pauses = None
    if pauses_json:
        try:
            pauses = json.loads(pauses_json)
            if not isinstance(pauses, dict):
                pauses = None
        except ValueError:
            pauses = None
    metrics = analyze_response(text, question=current["question"], part=current["part"], duration_seconds=duration_seconds, pauses=pauses)
    transcript = SpeakingTranscript(
        session_id=session.id,
        part=current["part"],
        turn_index=len(session.transcripts),
        question=current["question"],
        is_followup=bool(current.get("is_followup")),
        transcript=text[:6000],
        transcript_source=source,
        duration_seconds=metrics.duration_seconds,
        word_count=metrics.word_count,
        stt_confidence=confidence,
        metrics=metrics.to_dict(),
    )
    db.add(transcript)
    db.flush()
    if audio_bytes and user.profile.keep_recordings:
        mime = (audio_mime or "").split(";")[0].strip().lower()
        mime = mime if mime.startswith("audio/") else "audio/webm"  # stored and served only as audio
        ext = AUDIO_EXTENSIONS.get(mime, "webm")
        key = f"users/{user.id}/speaking/{session.id}/{transcript.id}.{ext}"
        try:
            storage.save(key, audio_bytes, mime)
            transcript.audio_key = key
            transcript.audio_mime = mime
        except Exception:  # storage problems must not lose the learner's answer
            logger.exception("Could not store recording for transcript %s", transcript.id)
    session.total_speaking_seconds = (session.total_speaking_seconds or 0) + metrics.duration_seconds
    next_turn = speaking_examiner.next_turn(db, user, session, text, metrics.word_count, current)
    session.current_question = next_turn or {}
    db.commit()
    return transcript, next_turn


def finish(db: Session, user: User, session_id: int):
    session = _get(db, user, session_id)
    if session.status == "completed":
        raise ValidationAppError("This speaking session has already been evaluated.", code="already_evaluated")
    answered = [t for t in session.transcripts if t.word_count > 0]
    if not answered:
        raise ValidationAppError("Answer at least one question before finishing the test.", code="no_answers")
    session.finished_at = session.finished_at or utcnow()
    db.commit()
    try:
        evaluation, records, extra = speaking_examiner.evaluate_session(db, user, session)
    except AIError as exc:
        db.rollback()
        session = _get(db, user, session_id)
        session.status = "evaluation_failed"
        session.failure_reason = getattr(exc, "category", "provider_error")
        db.commit()
        raise AIUnavailableError(
            "AI speaking analysis is temporarily unavailable. Your answers are saved and can be analysed again.",
            details={"session_id": session_id, "status": "evaluation_failed"},
        ) from exc
    session.status = "completed"
    session.failure_reason = None
    session.evaluation = evaluation
    xp = [(60, "speaking_session", f"Speaking {session.mode} test completed")]
    if extra["used"]:
        xp.append((5 * len(extra["used"]), "target_expressions", f"Used {len(extra['used'])} target expression(s)"))
    outcome = si_core.process_activity(
        db,
        user,
        si_core.ActivityEvent(
            activity="speaking",
            title=f"Speaking {'mock test' if session.mode == 'full' else session.mode.replace('part', 'Part ')}: {session.topic}",
            duration_seconds=int(session.total_speaking_seconds or 0),
            ref_type="speaking_session",
            ref_id=session.id,
            score=band_to_score(evaluation.overall_band),
            skill_results=[
                SkillResult("speaking", band_to_score(evaluation.overall_band), evaluation.overall_band, None),
                SkillResult("grammar", band_to_score(evaluation.grammatical_range_accuracy), None, None),
            ],
            errors=records,
            usage_text=extra["text"],
            usage_source="speaking",
            topic=None,
            xp=xp,
            mission_metrics={"speaking_sessions": 1},
            completes_kinds={"speaking"},
            meta={"band": evaluation.overall_band, "mode": session.mode},
            started_at=session.started_at,
        ),
    )
    if extra["used"]:
        outcome.si_actions.append(f"You used {len(extra['used'])} target expression(s) naturally: {', '.join(extra['used'])}.")
    return _get(db, user, session_id), outcome


def abandon(db: Session, user: User, session_id: int) -> None:
    session = _get(db, user, session_id)
    if session.status == "in_progress":
        session.status = "abandoned"
        db.commit()


def audio(db: Session, user: User, transcript_id: int) -> tuple[bytes, str]:
    t = db.get(SpeakingTranscript, transcript_id)
    if t is None or t.audio_key is None:
        raise NotFoundError("Recording not found.")
    session = db.get(SpeakingSession, t.session_id)
    if session is None or session.user_id != user.id or not storage.exists(t.audio_key):
        raise NotFoundError("Recording not found.")
    return storage.read(t.audio_key), t.audio_mime or "audio/webm"


def transcript_out(t: SpeakingTranscript) -> TranscriptOut:
    return TranscriptOut(
        id=t.id,
        part=t.part,
        turn_index=t.turn_index,
        question=t.question,
        is_followup=t.is_followup,
        transcript=t.transcript,
        transcript_source=t.transcript_source,
        duration_seconds=t.duration_seconds,
        word_count=t.word_count,
        stt_confidence=t.stt_confidence,
        has_audio=t.audio_key is not None,
        audio_url=f"/speaking/audio/{t.id}" if t.audio_key else None,
        metrics=t.metrics,
        created_at=t.created_at,
    )


def session_out(session: SpeakingSession) -> SpeakingSessionOut:
    ev = session.evaluation
    current = session.current_question if session.status == "in_progress" and session.current_question else None
    return SpeakingSessionOut(
        id=session.id,
        mode=session.mode,
        status=session.status,
        topic=session.topic,
        current_part=session.current_part,
        current_index=session.current_index,
        total_turns=len(session.plan.get("queue", [])),
        target_expressions=session.target_expressions or [],
        started_at=session.started_at,
        finished_at=session.finished_at,
        total_speaking_seconds=session.total_speaking_seconds or 0.0,
        failure_reason=session.failure_reason,
        current_turn=TurnOut(**current) if current else None,
        transcripts=[transcript_out(t) for t in session.transcripts],
        evaluation=SpeakingEvaluationOut(
            id=ev.id,
            overall_band=ev.overall_band,
            fluency_coherence=ev.fluency_coherence,
            lexical_resource=ev.lexical_resource,
            grammatical_range_accuracy=ev.grammatical_range_accuracy,
            pronunciation=ev.pronunciation,
            pronunciation_note=ev.pronunciation_note,
            criteria_feedback=ev.criteria_feedback,
            metrics=ev.metrics,
            hesitation=ev.hesitation,
            repeated_words=ev.repeated_words,
            fillers=ev.fillers,
            grammar_patterns=ev.grammar_patterns,
            errors=ev.errors,
            strengths=ev.strengths,
            weaknesses=ev.weaknesses,
            recommendations=ev.recommendations,
            expressions_used=ev.expressions_used,
            summary=ev.summary,
            provider=ev.provider,
            model=ev.model,
            is_mock=ev.is_mock,
            created_at=ev.created_at,
        )
        if ev
        else None,
    )


def get(db: Session, user: User, session_id: int) -> SpeakingSessionOut:
    return session_out(_get(db, user, session_id))


def history(db: Session, user: User, page: int, page_size: int) -> tuple[list[SpeakingSummary], int]:
    q = select(SpeakingSession).where(SpeakingSession.user_id == user.id, SpeakingSession.status != "abandoned")
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.options(selectinload(SpeakingSession.evaluation), selectinload(SpeakingSession.transcripts))
        .order_by(SpeakingSession.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [
        SpeakingSummary(
            id=s.id,
            mode=s.mode,
            status=s.status,
            topic=s.topic,
            overall_band=s.evaluation.overall_band if s.evaluation else None,
            responses=len(s.transcripts),
            total_speaking_seconds=s.total_speaking_seconds or 0.0,
            created_at=s.created_at,
            finished_at=s.finished_at,
        )
        for s in rows
    ], total
