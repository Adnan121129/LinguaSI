"""Vocabulary module workflows: daily sessions, reviews, word lists, insights and explanations."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents import si_core, vocabulary_engine
from app.agents.error_analyst import ErrorRecord
from app.agents.progress_analyst import SkillResult
from app.ai.client import ai_client
from app.ai.providers.base import AIError
from app.ai.schemas import VocabularyExplanationAI
from app.analytics import srs
from app.core.clock import ensure_aware, utcnow
from app.core.errors import AIUnavailableError, NotFoundError
from app.models import ProgressSnapshot, User, UserVocabulary, VocabularyItem, VocabularyReview
from app.repositories import stats
from app.services import gamification

_EXPLAIN_CACHE: dict[tuple[int, str], dict] = {}


def today(db: Session, user: User, focus: str | None = None) -> dict:
    if focus == "collocation":
        items = vocabulary_engine.choose_items(db, user, limit=8, topics={"collocation", "academic", "argument"}, phrase=True)
        vocabulary_engine.add_words(db, user, items, reason="weak_area", detail="Added for your collocation focus", priority=2.5)
    session = vocabulary_engine.build_session(db, user)
    if focus == "collocation":
        session["exercises"].sort(key=lambda e: e.get("reason") != "weak_area")
    db.commit()
    return session | {
        "counts": stats.vocab_counts(db, user.id),
        "retention": vocabulary_engine.retention_stats(db, user.id),
        "started_at": utcnow(),
    }


def review(db: Session, user: User, exercise_id: str, answer: str, response_ms: int | None, hinted: bool) -> dict:
    result = vocabulary_engine.check_review(db, user, exercise_id, answer, response_ms, hinted=hinted)
    state = gamification.RewardState()
    gamification.touch_streak(db, user, state)
    amount = 2 if result["correct"] else 1
    gain = gamification.award_xp(db, user, amount, "vocab_review", f"Vocabulary review: {result['item'].word}")
    gamification.record_mission_progress(db, user, {"vocab_reviews": 1}, state)
    gamification.ensure_week_challenges(db, user)
    gamification.record_challenge_progress(db, user, {"vocab_reviews": 1}, state, new_active_day=False)
    db.commit()
    return result | {
        "xp_gained": (gain.amount if gain else 0) + sum(g.amount for g in state.gains),
        "mission_progress": state.mission_progress,
    }


def complete_session(db: Session, user: User, started_at: datetime, duration_seconds: int) -> dict:
    now = utcnow()
    started = max(ensure_aware(started_at), now - timedelta(hours=3))
    reviews = db.execute(
        select(VocabularyReview, VocabularyItem)
        .join(VocabularyItem, VocabularyItem.id == VocabularyReview.item_id)
        .where(
            VocabularyReview.user_id == user.id, VocabularyReview.created_at >= started, VocabularyReview.exercise_type.in_(vocabulary_engine.EXERCISE_TYPES)
        )
    ).all()
    if not reviews:
        return {"reviews": 0, "correct": 0, "accuracy": None, "outcome": None}
    correct = sum(1 for r, _ in reviews if r.correct)
    accuracy = round(correct / len(reviews) * 100, 1)
    errors = [
        ErrorRecord(
            source="vocabulary",
            category="vocabulary",
            subcategory="vocabulary_recall",
            original=f"'{item.word}': answered '{r.answer or '(blank)'}'",
            corrected=f"{item.word} - {item.definition}",
            explanation=f"Example: {item.example}",
            context=item.example,
            severity="low",
            ref_type="vocabulary_item",
            ref_id=item.id,
            signature_hint=f"word:{item.id}",
        )
        for r, item in reviews
        if not r.correct
    ]
    outcome = si_core.process_activity(
        db,
        user,
        si_core.ActivityEvent(
            activity="vocabulary",
            title=f"Vocabulary review ({len(reviews)} words)",
            duration_seconds=min(duration_seconds or int((now - started).total_seconds()), 7200),
            score=accuracy,
            skill_results=[SkillResult("vocabulary", accuracy, None, None)],
            errors=errors,
            completes_kinds={"vocabulary"},
            meta={"reviews": len(reviews), "correct": correct},
            started_at=started,
        ),
    )
    return {"reviews": len(reviews), "correct": correct, "accuracy": accuracy, "outcome": outcome}


def mark_known(db: Session, user: User, user_vocab_id: int) -> UserVocabulary:
    uv = vocabulary_engine.mark_known(db, user, user_vocab_id)
    db.commit()
    return uv


def words(db: Session, user: User, state: str | None, page: int, page_size: int):
    q = select(UserVocabulary).where(UserVocabulary.user_id == user.id)
    if state:
        q = q.where(UserVocabulary.state == state)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(UserVocabulary.due_at.asc()).offset((page - 1) * page_size).limit(page_size)).all()
    return rows, total


def add_word(db: Session, user: User, item_id: int) -> None:
    item = db.get(VocabularyItem, item_id)
    if item is None:
        raise NotFoundError("Word not found in the word bank.")
    vocabulary_engine.add_words(db, user, [item], reason="manual", detail="You added this word", priority=1.5)
    db.commit()


def bank(db: Session, user: User, topic: str | None, query: str | None, page: int, page_size: int):
    q = select(VocabularyItem)
    if topic:
        q = q.where(VocabularyItem.topics.contains([topic]))
    if query:
        q = q.where(VocabularyItem.word.ilike(f"%{query.strip()}%"))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(VocabularyItem.word).offset((page - 1) * page_size).limit(page_size)).all()
    owned = set(db.scalars(select(UserVocabulary.item_id).where(UserVocabulary.user_id == user.id)))
    return rows, total, owned


def insights(db: Session, user: User) -> dict:
    rows = db.execute(
        select(UserVocabulary, VocabularyItem).join(VocabularyItem, VocabularyItem.id == UserVocabulary.item_id).where(UserVocabulary.user_id == user.id)
    ).all()
    groups: dict[str, list[str]] = {"too_easy": [], "challenging": [], "forgotten": [], "repeatedly_misunderstood": [], "in_progress": []}
    weak_topics = set()
    for area in user.profile.weak_areas or []:
        if area.get("skill") in ("vocabulary", "writing"):
            weak_topics.update({"academic", "collocation", "argument"})
    relevant = []
    used_writing, used_speaking = [], []
    for uv, item in rows:
        groups[srs.classify(uv)].append(item.word)
        if weak_topics & set(item.topics or []) and uv.state not in ("mastered",):
            relevant.append(item.word)
        if uv.used_in_writing:
            used_writing.append(item.word)
        if uv.used_in_speaking:
            used_speaking.append(item.word)
    growth = [
        {"day": s.day.isoformat(), "known": s.vocab_known, "mastered": s.vocab_mastered}
        for s in db.scalars(select(ProgressSnapshot).where(ProgressSnapshot.user_id == user.id).order_by(ProgressSnapshot.day.asc()).limit(90))
    ]
    return {
        "counts": stats.vocab_counts(db, user.id),
        "due": stats.vocab_due_count(db, user.id),
        "retention": vocabulary_engine.retention_stats(db, user.id),
        "groups": {k: v[:20] for k, v in groups.items()},
        "group_counts": {k: len(v) for k, v in groups.items()},
        "relevant_to_weak_areas": relevant[:20],
        "used_in_writing": used_writing[:20],
        "used_in_speaking": used_speaking[:20],
        "growth": growth,
    }


def explain(db: Session, user: User, item_id: int) -> dict:
    item = db.get(VocabularyItem, item_id)
    if item is None:
        raise NotFoundError("Word not found.")
    key = (item.id, ai_client.provider_name)
    if key in _EXPLAIN_CACHE:
        return _EXPLAIN_CACHE[key]
    level = user.profile.estimated_cefr or user.profile.self_reported_level
    item_dict = {
        "word": item.word,
        "part_of_speech": item.part_of_speech,
        "definition": item.definition,
        "example": item.example,
        "collocations": item.collocations,
        "is_academic": item.is_academic,
    }
    try:
        parsed, _ = ai_client.generate_model(
            "vocab_explain",
            {
                "word": item.word,
                "part_of_speech": item.part_of_speech,
                "definition": item.definition,
                "collocations": ", ".join(item.collocations) or "(none)",
                "level": level,
                "topics": ", ".join(user.profile.preferred_topics or item.topics or []),
            },
            VocabularyExplanationAI,
            user_id=user.id,
            mock_context={"item": item_dict},
        )
    except AIError as exc:
        raise AIUnavailableError("Explanations are temporarily unavailable. The definition and example above are always available.") from exc
    if not ai_client.is_mock:
        # Reusable generated content: keep new examples on the word for every learner (cost control).
        extra = list(item.extra_examples or [])
        for ex in parsed.examples:
            if ex not in extra and ex != item.example and len(extra) < 8:
                extra.append(ex)
        item.extra_examples = extra
        db.commit()
    data = parsed.model_dump() | {"is_mock": ai_client.is_mock}
    _EXPLAIN_CACHE[key] = data
    return data
