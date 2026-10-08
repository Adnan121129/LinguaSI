"""Admin panel: platform overview, user management, content moderation, evaluations and AI observability.

The admin views expose metadata only. Learner essays, transcripts and prompts are never listed here;
AI logs contain request metadata unless AI_LOG_CONTENT is explicitly enabled for debugging.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.config import settings
from app.core.errors import NotFoundError, ValidationAppError
from app.core.levels import level_for_xp, level_title
from app.models import (
    AIInteractionLog,
    AuthSession,
    GrammarExercise,
    ListeningAttempt,
    ListeningScript,
    Mistake,
    PracticeSet,
    ReadingAttempt,
    ReadingPassage,
    SpeakingEvaluation,
    SpeakingSession,
    SpeakingTopic,
    StudySession,
    SystemLog,
    User,
    VocabularyItem,
    VocabularyReview,
    WritingEvaluation,
    WritingSubmission,
    WritingTask,
    XPTransaction,
)
from app.repositories import stats
from app.seed.loader import load_all
from app.services.system_log import record_system_log

CONTENT_MODELS: dict[str, Any] = {
    "vocabulary": VocabularyItem,
    "grammar": GrammarExercise,
    "reading": ReadingPassage,
    "listening": ListeningScript,
    "writing": WritingTask,
    "speaking": SpeakingTopic,
}

# Fields an admin may edit per content type (everything else is managed by the seed files or SI).
EDITABLE_FIELDS: dict[str, set[str]] = {
    "vocabulary": {"definition", "example", "synonyms", "collocations", "topics", "cefr", "difficulty", "is_active"},
    "grammar": {"prompt", "options", "answer", "accepted", "explanation", "difficulty", "is_active"},
    "reading": {"title", "difficulty", "is_active"},
    "listening": {"title", "context", "difficulty", "is_active"},
    "writing": {"title", "prompt", "instructions", "key_points", "difficulty", "is_active"},
    "speaking": {"difficulty", "is_active"},
}


# --- Overview ------------------------------------------------------------------------------------


def overview(db: Session) -> dict:
    now = utcnow()
    week_ago, day_ago = now - timedelta(days=7), now - timedelta(days=1)

    def count(model, *where) -> int:
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    ai_row = db.execute(
        select(
            func.count(AIInteractionLog.id),
            func.sum(case((AIInteractionLog.success.is_(False), 1), else_=0)),
            func.sum(case((AIInteractionLog.is_mock.is_(True), 1), else_=0)),
            func.avg(AIInteractionLog.latency_ms),
            func.sum(AIInteractionLog.input_tokens),
            func.sum(AIInteractionLog.output_tokens),
        ).where(AIInteractionLog.created_at >= day_ago)
    ).one()
    calls, failures, mock_calls, avg_latency, tokens_in, tokens_out = ai_row
    content = {}
    for kind, model in CONTENT_MODELS.items():
        content[kind] = {"total": count(model), "hidden": count(model, model.is_active.is_(False))}
        if hasattr(model, "source"):
            content[kind]["ai_generated"] = count(model, model.source == "ai")
    return {
        "users": {
            "total": count(User),
            "admins": count(User, User.role == "admin"),
            "active_7d": count(User, User.last_active_at >= week_ago),
            "new_7d": count(User, User.created_at >= week_ago),
            "deactivated": count(User, User.is_active.is_(False)),
            "demo": count(User, User.is_demo.is_(True)),
        },
        "activity_7d": {
            "study_sessions": count(StudySession, StudySession.started_at >= week_ago),
            "writing_submissions": count(WritingSubmission, WritingSubmission.created_at >= week_ago),
            "writing_evaluations": count(WritingEvaluation, WritingEvaluation.created_at >= week_ago),
            "speaking_sessions": count(SpeakingSession, SpeakingSession.created_at >= week_ago),
            "reading_attempts": count(ReadingAttempt, ReadingAttempt.started_at >= week_ago),
            "listening_attempts": count(ListeningAttempt, ListeningAttempt.started_at >= week_ago),
            "practice_sets": count(PracticeSet, PracticeSet.created_at >= week_ago),
            "vocabulary_reviews": count(VocabularyReview, VocabularyReview.created_at >= week_ago),
            "mistakes_logged": count(Mistake, Mistake.first_seen_at >= week_ago),
        },
        "ai_24h": {
            "calls": calls or 0,
            "failures": int(failures or 0),
            "mock_calls": int(mock_calls or 0),
            "avg_latency_ms": round(float(avg_latency)) if avg_latency is not None else None,
            "input_tokens": int(tokens_in or 0),
            "output_tokens": int(tokens_out or 0),
        },
        "ai_config": ai_config(),
        "content": content,
        "errors_24h": count(SystemLog, SystemLog.created_at >= day_ago, SystemLog.level.in_(("error", "critical"))),
    }


def ai_config() -> dict:
    provider = settings.effective_ai_provider
    return {
        "configured_provider": settings.ai_provider,
        "effective_provider": provider,
        "mock_mode": settings.ai_is_mock,
        "model_fast": settings.model_for_tier("fast"),
        "model_strong": settings.model_for_tier("strong"),
        "stt_provider": settings.effective_stt_provider,
        "tts_provider": settings.effective_tts_provider,
        "content_logging": settings.ai_log_content,
        "user_hourly_limit": settings.ai_user_hourly_limit,
    }


# --- Users ----------------------------------------------------------------------------------------


def _user_row(user: User, xp: int) -> dict:
    p = user.profile
    level = level_for_xp(xp)
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "is_active": user.is_active,
        "is_demo": user.is_demo,
        "created_at": user.created_at,
        "last_active_at": user.last_active_at,
        "goal": p.goal if p else None,
        "estimated_cefr": p.estimated_cefr if p else None,
        "estimated_band": p.estimated_band if p else None,
        "onboarding_completed": bool(p and p.onboarding_completed),
        "diagnostic_completed": bool(p and p.diagnostic_completed),
        "total_xp": xp,
        "level": level,
        "level_title": level_title(level),
    }


def list_users(db: Session, *, q: str | None, role: str | None, active: bool | None, page: int, page_size: int) -> tuple[list[dict], int]:
    query = select(User)
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(User.email).like(like), func.lower(User.name).like(like)))
    if role:
        query = query.where(User.role == role)
    if active is not None:
        query = query.where(User.is_active.is_(active))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    users = db.scalars(query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).unique().all()
    ids = [u.id for u in users]
    xp = (
        dict(
            db.execute(
                select(XPTransaction.user_id, func.sum(XPTransaction.amount)).where(XPTransaction.user_id.in_(ids)).group_by(XPTransaction.user_id)
            ).all()
        )
        if ids
        else {}
    )
    return [_user_row(u, int(xp.get(u.id) or 0)) for u in users], total


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    return user


def user_detail(db: Session, user_id: int) -> dict:
    user = _get_user(db, user_id)
    row = _user_row(user, stats.total_xp(db, user.id))
    sessions = db.scalars(select(StudySession).where(StudySession.user_id == user.id).order_by(StudySession.started_at.desc()).limit(15)).all()
    ai_rows = db.execute(
        select(AIInteractionLog.task, func.count(AIInteractionLog.id), func.sum(case((AIInteractionLog.success.is_(False), 1), else_=0)))
        .where(AIInteractionLog.user_id == user.id)
        .group_by(AIInteractionLog.task)
    ).all()
    minutes = db.scalar(select(func.coalesce(func.sum(StudySession.duration_seconds), 0)).where(StudySession.user_id == user.id)) or 0
    row |= {
        "profile": {
            "ielts_module": user.profile.ielts_module,
            "target_band": user.profile.target_band,
            "test_date": user.profile.test_date,
            "daily_minutes": user.profile.daily_minutes,
            "timezone": user.profile.timezone,
            "weak_areas": user.profile.weak_areas,
            "strong_areas": user.profile.strong_areas,
        },
        "totals": {
            "study_minutes": round(minutes / 60),
            "writing_submissions": db.scalar(select(func.count()).select_from(WritingSubmission).where(WritingSubmission.user_id == user.id)) or 0,
            "speaking_sessions": db.scalar(select(func.count()).select_from(SpeakingSession).where(SpeakingSession.user_id == user.id)) or 0,
            "mistakes": stats.mistake_counts(db, user.id),
            "vocabulary": stats.vocab_counts(db, user.id),
        },
        "recent_sessions": [
            {"activity": s.activity, "title": s.title, "started_at": s.started_at, "duration_seconds": s.duration_seconds, "score": s.score, "xp": s.xp_earned}
            for s in sessions
        ],
        "ai_usage": [{"task": task, "calls": n, "failures": int(f or 0)} for task, n, f in ai_rows],
    }
    return row


def update_user(db: Session, admin: User, user_id: int, *, is_active: bool | None, role: str | None) -> dict:
    user = _get_user(db, user_id)
    if user.id == admin.id and (is_active is False or (role and role != "admin")):
        raise ValidationAppError("You can't deactivate or demote your own admin account.", code="self_lockout")
    changes = {}
    if is_active is not None and is_active != user.is_active:
        user.is_active = is_active
        changes["is_active"] = is_active
        if not is_active:
            # Sign the user out everywhere: revoke all refresh sessions.
            db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=utcnow()))
    if role and role != user.role:
        user.role = role
        changes["role"] = role
    db.commit()
    if changes:
        record_system_log("info", "admin", f"User {user.id} updated by admin {admin.id}", {"changes": changes})
    return _user_row(user, stats.total_xp(db, user.id))


# --- Content --------------------------------------------------------------------------------------


def _model_for(kind: str):
    model = CONTENT_MODELS.get(kind)
    if model is None:
        raise NotFoundError(f"Unknown content type '{kind}'.")
    return model


def _content_summary(kind: str, obj) -> dict:
    base = {"id": obj.id, "kind": kind, "is_active": obj.is_active, "created_at": obj.created_at, "source": getattr(obj, "source", "seed")}
    if kind == "vocabulary":
        return base | {"title": obj.word, "subtitle": f"{obj.part_of_speech} · {obj.cefr}", "detail": obj.definition, "difficulty": obj.difficulty}
    if kind == "grammar":
        return base | {"title": obj.prompt[:120], "subtitle": f"{obj.topic} · {obj.qtype}", "detail": obj.explanation, "difficulty": obj.difficulty}
    if kind == "reading":
        return base | {
            "title": obj.title,
            "subtitle": f"{obj.topic} · {obj.module} · {obj.word_count} words",
            "detail": obj.quality,
            "difficulty": obj.difficulty,
        }
    if kind == "listening":
        return base | {
            "title": obj.title,
            "subtitle": f"{obj.topic} · {obj.scenario} · {obj.word_count} words",
            "detail": obj.context,
            "difficulty": obj.difficulty,
        }
    if kind == "writing":
        return base | {
            "title": obj.title,
            "subtitle": f"{obj.task_type} · {obj.module} · {obj.category}",
            "detail": obj.prompt[:240],
            "difficulty": obj.difficulty,
        }
    title = (obj.cue_card or {}).get("title") if obj.kind == "cue_card" else f"Part 1: {obj.topic}"
    return base | {"title": title or obj.topic, "subtitle": f"{obj.kind} · {obj.topic}", "detail": ", ".join(obj.tags or []), "difficulty": obj.difficulty}


def list_content(db: Session, kind: str, *, q: str | None, active: bool | None, source: str | None, page: int, page_size: int) -> tuple[list[dict], int]:
    model = _model_for(kind)
    query = select(model)
    if q:
        like = f"%{q.strip().lower()}%"
        text_col = {
            "vocabulary": VocabularyItem.word,
            "grammar": GrammarExercise.prompt,
            "reading": ReadingPassage.title,
            "listening": ListeningScript.title,
            "writing": WritingTask.title,
            "speaking": SpeakingTopic.topic,
        }[kind]
        query = query.where(func.lower(text_col).like(like))
    if active is not None:
        query = query.where(model.is_active.is_(active))
    if source and hasattr(model, "source"):
        query = query.where(model.source == source)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(model.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return [_content_summary(kind, r) for r in rows], total


def content_detail(db: Session, kind: str, item_id: int) -> dict:
    model = _model_for(kind)
    obj = db.get(model, item_id)
    if obj is None:
        raise NotFoundError("Content item not found.")
    data = {c.name: getattr(obj, c.name) for c in model.__table__.columns}
    if kind in ("reading", "listening"):
        data["questions"] = [
            {"position": qn.position, "qtype": qn.qtype, "prompt": qn.prompt, "options": qn.options, "answer": qn.answer, "explanation": qn.explanation}
            for qn in obj.questions
        ]
    return {"summary": _content_summary(kind, obj), "data": data, "editable_fields": sorted(EDITABLE_FIELDS[kind])}


def update_content(db: Session, admin: User, kind: str, item_id: int, changes: dict) -> dict:
    model = _model_for(kind)
    obj = db.get(model, item_id)
    if obj is None:
        raise NotFoundError("Content item not found.")
    allowed = EDITABLE_FIELDS[kind]
    unknown = set(changes) - allowed
    if unknown:
        raise ValidationAppError(f"These fields can't be edited here: {', '.join(sorted(unknown))}.")
    _validate_content_changes(kind, obj, changes)
    for field, value in changes.items():
        setattr(obj, field, value)
    text_edit = set(changes) - {"is_active"}
    if text_edit and getattr(obj, "source", None) == "seed":
        obj.source = "edited"  # keeps the edit when the seed command runs again
    db.commit()
    record_system_log("info", "admin", f"{kind} #{item_id} updated by admin {admin.id}", {"fields": sorted(changes)})
    return content_detail(db, kind, item_id)


def _validate_content_changes(kind: str, obj, changes: dict) -> None:
    for field in ("definition", "example", "prompt", "answer", "title"):
        if field in changes and not str(changes[field] or "").strip():
            raise ValidationAppError(f"'{field}' cannot be empty.")
    if "difficulty" in changes and not (isinstance(changes["difficulty"], int) and 1 <= changes["difficulty"] <= 5):
        raise ValidationAppError("Difficulty must be a whole number from 1 to 5.")
    if "cefr" in changes and changes["cefr"] not in ("A1", "A2", "B1", "B2", "C1", "C2"):
        raise ValidationAppError("CEFR level must be one of A1-C2.")
    if "is_active" in changes and not isinstance(changes["is_active"], bool):
        raise ValidationAppError("is_active must be true or false.")
    for field in ("synonyms", "collocations", "topics", "accepted", "key_points"):
        if field in changes and not (isinstance(changes[field], list) and all(isinstance(v, str) for v in changes[field])):
            raise ValidationAppError(f"'{field}' must be a list of text values.")
    if kind == "grammar":
        qtype = obj.qtype
        options = changes.get("options", obj.options)
        answer = changes.get("answer", obj.answer)
        if qtype == "multiple_choice" and (not isinstance(options, list) or len(options) < 2 or answer not in options):
            raise ValidationAppError("A multiple-choice exercise needs at least two options, including the answer.")


def create_vocabulary(db: Session, admin: User, data: dict) -> dict:
    exists = db.scalar(
        select(VocabularyItem).where(func.lower(VocabularyItem.word) == data["word"].strip().lower(), VocabularyItem.part_of_speech == data["part_of_speech"])
    )
    if exists:
        raise ValidationAppError("This word already exists with that part of speech.", code="duplicate")
    cefr = data.get("cefr", "B2")
    item = VocabularyItem(
        word=data["word"].strip(),
        part_of_speech=data["part_of_speech"],
        definition=data["definition"].strip(),
        example=data["example"].strip(),
        synonyms=data.get("synonyms", []),
        antonyms=[],
        collocations=data.get("collocations", []),
        word_family={},
        topics=data.get("topics", []),
        cefr=cefr,
        difficulty={"A1": 1, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}[cefr],
        is_academic=bool(data.get("is_academic")),
        is_phrase=" " in data["word"].strip(),
        source="admin",
    )
    db.add(item)
    db.commit()
    record_system_log("info", "admin", f"Vocabulary '{item.word}' added by admin {admin.id}", {"item_id": item.id})
    return content_detail(db, "vocabulary", item.id)


# --- Evaluations, AI usage and logs ------------------------------------------------------------------


def list_evaluations(db: Session, kind: str, page: int, page_size: int) -> tuple[list[dict], int]:
    if kind == "speaking":
        query = (
            select(SpeakingEvaluation, User.email, SpeakingSession.mode, SpeakingSession.topic)
            .join(User, User.id == SpeakingEvaluation.user_id)
            .join(SpeakingSession, SpeakingSession.id == SpeakingEvaluation.session_id)
        )
        total = db.scalar(select(func.count()).select_from(SpeakingEvaluation)) or 0
        rows = db.execute(query.order_by(SpeakingEvaluation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        return [
            {
                "id": ev.id,
                "kind": "speaking",
                "user_email": email,
                "title": f"{mode} · {topic}",
                "overall_band": ev.overall_band,
                "criteria": {
                    "fluency_coherence": ev.fluency_coherence,
                    "lexical_resource": ev.lexical_resource,
                    "grammatical_range_accuracy": ev.grammatical_range_accuracy,
                    "pronunciation": ev.pronunciation,
                },
                "provider": ev.provider,
                "model": ev.model,
                "is_mock": ev.is_mock,
                "error_count": len(ev.errors or []),
                "created_at": ev.created_at,
            }
            for ev, email, mode, topic in rows
        ], total
    query = (
        select(WritingEvaluation, User.email, WritingTask.title, WritingTask.task_type)
        .join(User, User.id == WritingEvaluation.user_id)
        .join(WritingSubmission, WritingSubmission.id == WritingEvaluation.submission_id)
        .join(WritingTask, WritingTask.id == WritingSubmission.task_id)
    )
    total = db.scalar(select(func.count()).select_from(WritingEvaluation)) or 0
    rows = db.execute(query.order_by(WritingEvaluation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return [
        {
            "id": ev.id,
            "kind": "writing",
            "user_email": email,
            "title": f"{task_type} · {title}",
            "overall_band": ev.overall_band,
            "criteria": {
                "task_response": ev.task_response,
                "coherence_cohesion": ev.coherence_cohesion,
                "lexical_resource": ev.lexical_resource,
                "grammatical_range_accuracy": ev.grammatical_range_accuracy,
            },
            "provider": ev.provider,
            "model": ev.model,
            "is_mock": ev.is_mock,
            "error_count": len(ev.errors),
            "created_at": ev.created_at,
        }
        for ev, email, title, task_type in rows
    ], total


def ai_usage(db: Session, days: int) -> dict:
    since = utcnow() - timedelta(days=days)
    base = select(AIInteractionLog).where(AIInteractionLog.created_at >= since).subquery()
    by_task = db.execute(
        select(
            base.c.task,
            base.c.tier,
            func.count(),
            func.sum(case((base.c.success.is_(False), 1), else_=0)),
            func.avg(base.c.latency_ms),
            func.sum(base.c.input_tokens),
            func.sum(base.c.output_tokens),
        )
        .group_by(base.c.task, base.c.tier)
        .order_by(func.count().desc())
    ).all()
    by_model = db.execute(
        select(base.c.provider, base.c.model, base.c.is_mock, func.count(), func.sum(base.c.input_tokens), func.sum(base.c.output_tokens)).group_by(
            base.c.provider, base.c.model, base.c.is_mock
        )
    ).all()
    errors = db.execute(select(base.c.error_category, func.count()).where(base.c.success.is_(False)).group_by(base.c.error_category)).all()
    daily: dict[str, dict] = defaultdict(lambda: {"calls": 0, "failures": 0, "input_tokens": 0, "output_tokens": 0})
    for created, success, tin, tout in db.execute(select(base.c.created_at, base.c.success, base.c.input_tokens, base.c.output_tokens)).all():
        day = daily[created.date().isoformat()]
        day["calls"] += 1
        day["failures"] += 0 if success else 1
        day["input_tokens"] += tin or 0
        day["output_tokens"] += tout or 0
    latencies = sorted(db.scalars(select(base.c.latency_ms).where(base.c.success.is_(True))).all())
    p95 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] if latencies else None
    recent_failures = db.scalars(
        select(AIInteractionLog)
        .where(AIInteractionLog.created_at >= since, AIInteractionLog.success.is_(False))
        .order_by(AIInteractionLog.created_at.desc())
        .limit(20)
    ).all()
    return {
        "days": days,
        "config": ai_config(),
        "p95_latency_ms": p95,
        "by_task": [
            {
                "task": task,
                "tier": tier,
                "calls": n,
                "failures": int(f or 0),
                "avg_latency_ms": round(float(lat)) if lat is not None else None,
                "input_tokens": int(tin or 0),
                "output_tokens": int(tout or 0),
            }
            for task, tier, n, f, lat, tin, tout in by_task
        ],
        "by_model": [
            {"provider": provider, "model": model, "is_mock": mock, "calls": n, "input_tokens": int(tin or 0), "output_tokens": int(tout or 0)}
            for provider, model, mock, n, tin, tout in by_model
        ],
        "errors": [{"category": cat or "unknown", "count": n} for cat, n in errors],
        "daily": [{"day": day} | values for day, values in sorted(daily.items())],
        "recent_failures": [
            {
                "id": r.id,
                "task": r.task,
                "provider": r.provider,
                "model": r.model,
                "error_category": r.error_category,
                "error_message": r.error_message,
                "attempts": r.attempts,
                "created_at": r.created_at,
            }
            for r in recent_failures
        ],
    }


def list_logs(db: Session, *, level: str | None, source: str | None, page: int, page_size: int) -> tuple[list[dict], int]:
    query = select(SystemLog)
    if level:
        query = query.where(SystemLog.level == level)
    if source:
        query = query.where(SystemLog.source == source)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(SystemLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return [{"id": r.id, "level": r.level, "source": r.source, "message": r.message, "context": r.context, "created_at": r.created_at} for r in rows], total


def run_seed(db: Session, admin: User) -> dict:
    counts = load_all(db)
    record_system_log("info", "admin", f"Seed content reloaded by admin {admin.id}", {"counts": counts})
    return counts
