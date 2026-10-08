"""Listening practice: script generation/selection, TTS audio (or device-voice fallback), attempts and scoring."""

from __future__ import annotations

import logging
import random

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.agents import practice_generator, si_core
from app.agents.context import build_context
from app.agents.progress_analyst import SkillResult, get_skill_profile
from app.ai.client import ai_client
from app.ai.providers.base import AIError
from app.ai.speech import SpeechUnavailableError, get_tts, voice_for
from app.analytics.scoring import accuracy as accuracy_pct
from app.analytics.text import word_count
from app.core.clock import utcnow
from app.core.errors import NotFoundError, ValidationAppError
from app.core.levels import accuracy_to_band
from app.models import ListeningAttempt, ListeningQuestion, ListeningScript, User
from app.schemas.comprehension import ListeningAttemptOut, QuestionOut, QuestionResult, ScriptOut, SegmentOut
from app.services import comprehension
from app.services.storage import storage

logger = logging.getLogger("linguasi.listening")

RATE_BY_DIFFICULTY = {1: 0.85, 2: 0.92, 3: 1.0, 4: 1.05, 5: 1.12}
SCENARIO_BY_DIFFICULTY = {1: "conversation", 2: "conversation", 3: "discussion", 4: "lecture", 5: "lecture"}
TOPICS = ["travel", "education", "health", "environment", "work", "culture", "daily_life", "society"]


def ensure_audio(db: Session, script: ListeningScript) -> None:
    """Synthesize one audio file per segment with the configured TTS provider (once per script)."""
    if script.audio_status == "ready":
        return
    tts = get_tts()
    if tts.name == "mock":
        script.audio_status = "none"
        return
    try:
        audio = []
        speakers = {s["id"]: (i, s) for i, s in enumerate(script.speakers)}
        for index, seg in enumerate(script.segments):
            idx, speaker = speakers.get(seg["speaker"], (0, {"gender": "female", "accent": script.accent, "role": "speaker"}))
            data, mime = tts.synthesize(
                seg["text"],
                voice=voice_for(speaker, idx),
                speed=script.speech_rate,
                instructions=f"Speak naturally as a {speaker.get('role', 'speaker')} with a {speaker.get('accent', script.accent)} English accent.",
            )
            key = f"listening/{script.id}/{index}.mp3"
            storage.save(key, data, mime)
            audio.append({"segment": index, "key": key, "mime": mime})
        script.audio = audio
        script.audio_status = "ready"
    except SpeechUnavailableError as exc:
        logger.warning("TTS failed for script %s: %s", script.id, exc)
        script.audio_status = "failed"


def _attempted(db: Session, user: User) -> dict[int, object]:
    rows = db.execute(
        select(ListeningAttempt.script_id, func.max(ListeningAttempt.started_at))
        .where(ListeningAttempt.user_id == user.id)
        .group_by(ListeningAttempt.script_id)
    ).all()
    return {sid: ts for sid, ts in rows}


def generate(
    db: Session,
    user: User,
    *,
    difficulty: int | None,
    topic: str | None,
    scenario: str | None,
    question_count: int,
    time_limit: int,
    accent: str | None,
    question_types: list[str] | None,
) -> tuple[ListeningAttempt, str | None]:
    profile = get_skill_profile(db, user, "listening")
    difficulty = difficulty or profile.difficulty or 2
    types = [t for t in (question_types or []) if t in practice_generator.LISTENING_TYPES] or None
    notice = None
    script: ListeningScript | None = None

    if not ai_client.is_mock:
        ctx = build_context(db, user)
        chosen_topic = topic or (random.choice(ctx.preferred_topics) if ctx.preferred_topics else random.choice(TOPICS))
        chosen_scenario = scenario or SCENARIO_BY_DIFFICULTY[difficulty]
        try:
            parsed, report = practice_generator.generate_listening(
                db,
                user,
                topic=chosen_topic,
                scenario=chosen_scenario,
                difficulty=difficulty,
                question_count=question_count,
                accent=accent or "british",
                target_expressions=ctx.target_expressions[:3],
            )
            script = ListeningScript(
                title=parsed.title[:200],
                topic=(parsed.topic or chosen_topic)[:60],
                scenario=parsed.scenario,
                difficulty=difficulty,
                speakers=[s.model_dump() for s in parsed.speakers],
                segments=[s.model_dump() for s in parsed.segments],
                word_count=sum(word_count(s.text) for s in parsed.segments),
                speech_rate=RATE_BY_DIFFICULTY[difficulty],
                accent=accent or "british",
                context=parsed.context,
                source="ai",
                created_for_user_id=user.id,
                target_vocabulary=ctx.target_expressions[:3],
                quality=report.as_dict(),
            )
            for pos, q in enumerate(parsed.questions, start=1):
                script.questions.append(
                    ListeningQuestion(
                        position=pos,
                        qtype=q.qtype,
                        prompt=q.prompt,
                        options=q.options or None,
                        answer=q.answer,
                        accepted=q.accepted_answers,
                        explanation=q.explanation,
                        evidence=q.evidence,
                        word_limit=q.word_limit,
                    )
                )
            db.add(script)
            db.flush()
        except (AIError, ValueError) as exc:
            logger.info("Listening generation fell back to curated content: %s", exc)
            notice = "AI generation is temporarily unavailable, so SI selected a curated recording that matches your level."
            script = None

    if script is None:
        candidates = list(
            db.scalars(
                select(ListeningScript)
                .options(selectinload(ListeningScript.questions))
                .where(or_(ListeningScript.created_for_user_id.is_(None), ListeningScript.created_for_user_id == user.id))
            )
        )
        if scenario:
            candidates = [c for c in candidates if c.scenario == scenario] or candidates
        script = comprehension.choose_best(candidates, difficulty=difficulty, topic=topic, attempted=_attempted(db, user), types=types)
        if script is None:
            raise ValidationAppError("No listening content is available yet. Run the seed command to load the content bank.")
        if notice is None and ai_client.is_mock:
            notice = "Mock AI mode: SI selected the curated recording that best matches your level. Connect an AI provider for unlimited new scripts."
    if accent and accent != script.accent and script.source == "seed":
        notice = (notice or "") + f" This recording uses a {script.accent} accent."

    ensure_audio(db, script)
    questions = comprehension.pick_questions(script.questions, question_count, types)
    attempt = ListeningAttempt(
        user_id=user.id,
        script_id=script.id,
        status="in_progress",
        question_ids=[q.id for q in questions],
        time_limit_minutes=time_limit,
        difficulty=script.difficulty,
        total=len(questions),
        started_at=utcnow(),
    )
    db.add(attempt)
    db.commit()
    return attempt, (notice.strip() if notice else None)


def _get(db: Session, user: User, attempt_id: int) -> ListeningAttempt:
    attempt = db.get(ListeningAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise NotFoundError("Listening attempt not found.")
    return attempt


def _questions(db: Session, attempt: ListeningAttempt) -> list[ListeningQuestion]:
    by_id = {q.id: q for q in db.scalars(select(ListeningQuestion).where(ListeningQuestion.id.in_(attempt.question_ids)))}
    return [by_id[i] for i in attempt.question_ids if i in by_id]


def attempt_out(db: Session, attempt: ListeningAttempt, notice: str | None = None) -> ListeningAttemptOut:
    s = attempt.script
    submitted = attempt.status == "submitted"
    server_audio = s.audio_status == "ready"
    audio_by_segment = {a["segment"]: a for a in s.audio or []}
    segments = [
        SegmentOut(
            index=i,
            speaker=seg["speaker"],
            # With server audio the transcript is withheld until submission; device voices need the text to speak.
            text=seg["text"] if (submitted or not server_audio) else None,
            audio_url=f"/listening/audio/{s.id}/{i}" if i in audio_by_segment else None,
        )
        for i, seg in enumerate(s.segments)
    ]
    return ListeningAttemptOut(
        id=attempt.id,
        status=attempt.status,
        script=ScriptOut(
            id=s.id,
            title=s.title,
            topic=s.topic,
            scenario=s.scenario,
            difficulty=s.difficulty,
            context=s.context,
            speakers=s.speakers,
            segments=segments,
            speech_rate=s.speech_rate or RATE_BY_DIFFICULTY.get(s.difficulty, 1.0),
            accent=s.accent,
            audio_mode="server" if server_audio else "device",
            transcript_hidden=not submitted,
            source=s.source,
        ),
        questions=[
            QuestionOut(id=q.id, position=q.position, qtype=q.qtype, prompt=q.prompt, options=q.options, word_limit=q.word_limit)
            for q in _questions(db, attempt)
        ],
        time_limit_minutes=attempt.time_limit_minutes,
        difficulty=attempt.difficulty,
        started_at=attempt.started_at,
        submitted_at=attempt.submitted_at,
        correct=attempt.correct,
        total=attempt.total,
        accuracy=attempt.accuracy,
        band=attempt.band,
        replays=attempt.replays,
        results=[QuestionResult(**r) for r in attempt.results] if submitted else [],
        answers=attempt.answers if submitted else {},
        notice=notice,
    )


def record_replay(db: Session, user: User, attempt_id: int) -> int:
    attempt = _get(db, user, attempt_id)
    if attempt.status == "in_progress":
        attempt.replays += 1
        db.commit()
    return attempt.replays


def audio(db: Session, user: User, script_id: int, segment: int) -> tuple[bytes, str]:
    script = db.get(ListeningScript, script_id)
    if script is None or (script.created_for_user_id is not None and script.created_for_user_id != user.id):
        raise NotFoundError("Audio not found.")
    entry = next((a for a in script.audio or [] if a["segment"] == segment), None)
    if entry is None or not storage.exists(entry["key"]):
        raise NotFoundError("Audio not found.")
    return storage.read(entry["key"]), entry.get("mime", "audio/mpeg")


def submit(db: Session, user: User, attempt_id: int, answers: dict[str, str], time_spent: int, replays: int | None):
    attempt = _get(db, user, attempt_id)
    if attempt.status == "submitted":
        raise ValidationAppError("This listening attempt has already been submitted.", code="already_submitted")
    questions = _questions(db, attempt)
    results, correct = comprehension.score(questions, answers)
    acc = accuracy_pct(correct, len(questions))
    # Replays make practice easier than the real test (one listening only), so the band estimate is capped.
    band = accuracy_to_band(acc, attempt.difficulty)
    if replays is not None:
        attempt.replays = max(attempt.replays, replays)
    if attempt.replays >= 2:
        band = max(0.0, band - 0.5)
    attempt.answers = {str(k): v for k, v in answers.items()}
    attempt.results = results
    attempt.correct = correct
    attempt.total = len(questions)
    attempt.accuracy = acc
    attempt.band = band
    attempt.time_spent_seconds = time_spent
    attempt.status = "submitted"
    attempt.submitted_at = utcnow()
    db.flush()
    script = attempt.script
    outcome = si_core.process_activity(
        db,
        user,
        si_core.ActivityEvent(
            activity="listening",
            title=f"Listening: {script.title}",
            duration_seconds=time_spent,
            ref_type="listening_attempt",
            ref_id=attempt.id,
            score=acc,
            skill_results=[SkillResult("listening", acc, band, attempt.difficulty)],
            errors=comprehension.mistake_records("listening", questions, results, "listening_attempt", attempt.id),
            topic=script.topic,
            xp=[(20 + round(acc / 5), "listening_attempt", f"Listening completed: {correct}/{len(questions)}")],
            mission_metrics={"listening_exercises": 1},
            completes_kinds={"listening"},
            meta={"accuracy": acc, "difficulty": attempt.difficulty, "replays": attempt.replays},
        ),
    )
    return attempt, outcome


def history(db: Session, user: User, page: int, page_size: int):
    q = select(ListeningAttempt).where(ListeningAttempt.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(ListeningAttempt.started_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return rows, total


def get(db: Session, user: User, attempt_id: int) -> ListeningAttempt:
    return _get(db, user, attempt_id)
