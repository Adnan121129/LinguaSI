"""Reading practice: AI generation (validated) or curated selection, attempts, scoring and SI Core updates."""

from __future__ import annotations

import logging
import random

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.agents import practice_generator, si_core
from app.agents.context import build_context
from app.agents.progress_analyst import SkillResult, get_skill_profile
from app.agents.vocabulary_engine import contains_item
from app.ai.client import ai_client
from app.ai.providers.base import AIError
from app.analytics.scoring import accuracy as accuracy_pct
from app.analytics.text import word_count
from app.core.clock import utcnow
from app.core.errors import NotFoundError, ValidationAppError
from app.core.levels import accuracy_to_band
from app.models import ReadingAttempt, ReadingPassage, ReadingQuestion, User, UserVocabulary, VocabularyItem
from app.schemas.comprehension import PassageOut, QuestionOut, QuestionResult, ReadingAttemptOut
from app.services import comprehension

logger = logging.getLogger("linguasi.reading")

TOPICS = ["environment", "technology", "health", "education", "work", "culture", "science", "urban", "society"]
DEFAULT_TYPES = {
    "academic": ["true_false_not_given", "multiple_choice", "matching_headings", "sentence_completion", "summary_completion", "matching_information"],
    "general_training": ["true_false_not_given", "short_answer", "sentence_completion", "multiple_choice"],
}


def _attempted(db: Session, user: User) -> dict[int, object]:
    rows = db.execute(
        select(ReadingAttempt.passage_id, func.max(ReadingAttempt.started_at)).where(ReadingAttempt.user_id == user.id).group_by(ReadingAttempt.passage_id)
    ).all()
    return {pid: ts for pid, ts in rows}


def generate(
    db: Session,
    user: User,
    *,
    difficulty: int | None,
    topic: str | None,
    question_count: int,
    time_limit: int,
    module: str | None,
    question_types: list[str] | None,
) -> tuple[ReadingAttempt, str | None]:
    profile = get_skill_profile(db, user, "reading")
    difficulty = difficulty or profile.difficulty or 3
    module = module or (user.profile.ielts_module if user.profile.goal == "ielts" else "academic")
    types = [t for t in (question_types or []) if t in practice_generator.READING_TYPES] or None
    notice = None
    passage: ReadingPassage | None = None

    if not ai_client.is_mock:
        ctx = build_context(db, user)
        chosen_topic = topic or (random.choice(ctx.preferred_topics) if ctx.preferred_topics else random.choice(TOPICS))
        try:
            parsed, report = practice_generator.generate_reading(
                db,
                user,
                module=module,
                topic=chosen_topic,
                difficulty=difficulty,
                question_count=question_count,
                question_types=types or DEFAULT_TYPES[module],
                target_expressions=ctx.target_expressions[:4],
            )
            passage = ReadingPassage(
                title=parsed.title[:200],
                topic=(parsed.topic or chosen_topic)[:60],
                module=module,
                difficulty=difficulty,
                paragraphs=[{"label": p.label.strip().upper()[:2], "text": p.text} for p in parsed.paragraphs],
                headings=parsed.headings,
                word_count=sum(word_count(p.text) for p in parsed.paragraphs),
                source="ai",
                created_for_user_id=user.id,
                target_vocabulary=ctx.target_expressions[:4],
                quality=report.as_dict(),
            )
            passage.estimated_minutes = max(8, round(passage.word_count / 40) + len(parsed.questions))
            for pos, q in enumerate(parsed.questions, start=1):
                passage.questions.append(
                    ReadingQuestion(
                        position=pos,
                        qtype=q.qtype,
                        prompt=q.prompt,
                        options=q.options or None,
                        answer=q.answer,
                        accepted=q.accepted_answers,
                        explanation=q.explanation,
                        evidence=q.evidence,
                        evidence_paragraph=(q.evidence_paragraph or "")[:2] or None,
                        word_limit=q.word_limit,
                    )
                )
            db.add(passage)
            db.flush()
        except (AIError, ValueError) as exc:
            logger.info("Reading generation fell back to curated content: %s", exc)
            notice = "AI generation is temporarily unavailable, so SI selected a curated passage that matches your level."
            passage = None

    if passage is None:
        candidates = list(
            db.scalars(
                select(ReadingPassage)
                .options(selectinload(ReadingPassage.questions))
                .where(or_(ReadingPassage.created_for_user_id.is_(None), ReadingPassage.created_for_user_id == user.id))
            )
        )
        same_module = [p for p in candidates if p.module == module] or candidates
        passage = comprehension.choose_best(same_module, difficulty=difficulty, topic=topic, attempted=_attempted(db, user), types=types)
        if passage is None:
            raise ValidationAppError("No reading content is available yet. Run the seed command to load the content bank.")
        if notice is None and ai_client.is_mock:
            notice = (
                "Mock AI mode: SI selected the curated passage that best matches your level and choices. Connect an AI provider for unlimited new passages."
            )

    questions = comprehension.pick_questions(passage.questions, question_count, types)
    attempt = ReadingAttempt(
        user_id=user.id,
        passage_id=passage.id,
        status="in_progress",
        question_ids=[q.id for q in questions],
        time_limit_minutes=time_limit,
        difficulty=passage.difficulty,
        total=len(questions),
        started_at=utcnow(),
    )
    db.add(attempt)
    db.commit()
    return attempt, notice


def _get(db: Session, user: User, attempt_id: int) -> ReadingAttempt:
    attempt = db.get(ReadingAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise NotFoundError("Reading attempt not found.")
    return attempt


def _questions(db: Session, attempt: ReadingAttempt) -> list[ReadingQuestion]:
    by_id = {q.id: q for q in db.scalars(select(ReadingQuestion).where(ReadingQuestion.id.in_(attempt.question_ids)))}
    return [by_id[i] for i in attempt.question_ids if i in by_id]


def spotlight(db: Session, user: User, passage: ReadingPassage) -> list[str]:
    """Words from the learner's vocabulary queue that appear in this passage (cross-skill reinforcement)."""
    text = " ".join(p["text"] for p in passage.paragraphs)
    rows = db.scalars(
        select(VocabularyItem)
        .join(UserVocabulary, UserVocabulary.item_id == VocabularyItem.id)
        .where(UserVocabulary.user_id == user.id, UserVocabulary.state != "mastered")
    ).all()
    return [item.word for item in rows if contains_item(text, item)][:8]


def attempt_out(db: Session, user: User, attempt: ReadingAttempt, notice: str | None = None) -> ReadingAttemptOut:
    p = attempt.passage
    submitted = attempt.status == "submitted"
    out = ReadingAttemptOut(
        id=attempt.id,
        status=attempt.status,
        passage=PassageOut(
            id=p.id,
            title=p.title,
            topic=p.topic,
            module=p.module,
            difficulty=p.difficulty,
            paragraphs=p.paragraphs,
            headings=p.headings,
            word_count=p.word_count,
            source=p.source,
        ),
        questions=[
            QuestionOut(
                id=q.id,
                position=q.position,
                qtype=q.qtype,
                prompt=q.prompt,
                options=q.options if q.qtype != "matching_headings" else (p.headings or q.options),
                word_limit=q.word_limit,
            )
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
        results=[QuestionResult(**r) for r in attempt.results] if submitted else [],
        answers=attempt.answers if submitted else {},
        notice=notice,
        spotlight=spotlight(db, user, p),
    )
    return out


def submit(db: Session, user: User, attempt_id: int, answers: dict[str, str], time_spent: int):
    attempt = _get(db, user, attempt_id)
    if attempt.status == "submitted":
        raise ValidationAppError("This reading attempt has already been submitted.", code="already_submitted")
    questions = _questions(db, attempt)
    results, correct = comprehension.score(questions, answers)
    acc = accuracy_pct(correct, len(questions))
    band = accuracy_to_band(acc, attempt.difficulty)
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
    passage = attempt.passage
    outcome = si_core.process_activity(
        db,
        user,
        si_core.ActivityEvent(
            activity="reading",
            title=f"Reading: {passage.title}",
            duration_seconds=time_spent,
            ref_type="reading_attempt",
            ref_id=attempt.id,
            score=acc,
            skill_results=[SkillResult("reading", acc, band, attempt.difficulty)],
            errors=comprehension.mistake_records("reading", questions, results, "reading_attempt", attempt.id),
            topic=passage.topic,
            xp=[(20 + round(acc / 5), "reading_attempt", f"Reading completed: {correct}/{len(questions)}")],
            mission_metrics={"reading_exercises": 1},
            completes_kinds={"reading"},
            meta={"accuracy": acc, "difficulty": attempt.difficulty},
        ),
    )
    return attempt, outcome


def history(db: Session, user: User, page: int, page_size: int):
    q = select(ReadingAttempt).where(ReadingAttempt.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(ReadingAttempt.started_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return rows, total


def get(db: Session, user: User, attempt_id: int) -> ReadingAttempt:
    return _get(db, user, attempt_id)
