"""Writing module workflows: tasks, drafts with autosave, tutor hints, evaluation and history."""

from __future__ import annotations

import logging

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.agents import practice_generator, si_core, tutor, writing_examiner
from app.agents.progress_analyst import SkillResult
from app.ai.providers.base import AIError
from app.analytics.text import word_count
from app.core.clock import utcnow
from app.core.errors import AIUnavailableError, ForbiddenError, NotFoundError, ValidationAppError
from app.core.levels import band_to_score
from app.models import User, WritingEvaluation, WritingSubmission, WritingTask
from app.schemas.writing import (
    CriterionOut,
    PreviousAttempt,
    SubmissionOut,
    SubmissionSummary,
    WritingErrorOut,
    WritingEvaluationOut,
    WritingTaskOut,
)

logger = logging.getLogger("linguasi.writing")
MAX_HINTS = 12


def list_tasks(db: Session, user: User, *, task_type: str | None, module: str | None, category: str | None, page: int, page_size: int):
    q = select(WritingTask).where(or_(WritingTask.created_for_user_id.is_(None), WritingTask.created_for_user_id == user.id))
    if task_type:
        q = q.where(WritingTask.task_type == task_type)
    if module:
        q = q.where(WritingTask.module == module)
    if category:
        q = q.where(WritingTask.category == category)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(WritingTask.created_for_user_id.is_(None), WritingTask.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return [WritingTaskOut.model_validate(t) for t in rows], total


def get_task(db: Session, user: User, task_id: int) -> WritingTask:
    task = db.get(WritingTask, task_id)
    if task is None or (task.created_for_user_id is not None and task.created_for_user_id != user.id):
        raise NotFoundError("Writing task not found.")
    return task


def generate_task(db: Session, user: User, **params) -> tuple[WritingTask, str | None]:
    task, notice = practice_generator.generate_writing_task(db, user, **params)
    db.commit()
    return task, notice


def _get_submission(db: Session, user: User, submission_id: int) -> WritingSubmission:
    sub = db.scalar(
        select(WritingSubmission)
        .options(selectinload(WritingSubmission.evaluation).selectinload(WritingEvaluation.errors))
        .where(WritingSubmission.id == submission_id)
        .execution_options(populate_existing=True)
    )
    if sub is None or sub.user_id != user.id:
        raise NotFoundError("Writing submission not found.")
    return sub


def start_submission(db: Session, user: User, task_id: int, mode: str) -> WritingSubmission:
    task = get_task(db, user, task_id)
    existing = db.scalar(
        select(WritingSubmission)
        .where(WritingSubmission.user_id == user.id, WritingSubmission.task_id == task.id, WritingSubmission.status == "draft")
        .order_by(WritingSubmission.created_at.desc())
        .limit(1)
    )
    if existing:
        existing.mode = mode
        db.commit()
        return existing
    sub = WritingSubmission(user_id=user.id, task_id=task.id, mode=mode, content="", word_count=0, status="draft")
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def autosave(db: Session, user: User, submission_id: int, content: str, time_spent: int) -> WritingSubmission:
    sub = _get_submission(db, user, submission_id)
    if sub.status not in ("draft", "evaluation_failed"):
        raise ValidationAppError("This response has already been submitted and can no longer be edited.", code="already_submitted")
    sub.content = content
    sub.word_count = word_count(content)
    sub.time_spent_seconds = max(sub.time_spent_seconds or 0, time_spent)
    sub.autosaved_at = utcnow()
    db.commit()
    return sub


def hint(db: Session, user: User, submission_id: int, question: str | None, content: str | None) -> tuple[dict, int]:
    sub = _get_submission(db, user, submission_id)
    if sub.mode != "tutor":
        raise ForbiddenError("Hints are turned off in exam mode. Switch to tutor mode to get help.", code="hints_disabled")
    if sub.status != "draft":
        raise ValidationAppError("Hints are available while you are writing.")
    if (sub.hints_used or 0) >= MAX_HINTS:
        raise ValidationAppError("You've used all the hints for this task - try finishing it on your own!", code="hint_limit")
    if content is not None:
        sub.content = content
        sub.word_count = word_count(content)
    try:
        parsed = tutor.writing_hint(db, user, sub, question)
    except AIError as exc:
        db.commit()
        raise AIUnavailableError("The SI Tutor is temporarily unavailable. Your draft is saved - keep writing and try again shortly.") from exc
    sub.hints_used = (sub.hints_used or 0) + 1
    notes = list(sub.tutor_notes or [])
    notes.append({"at": utcnow().isoformat(), "question": question, "hints": parsed.hints, "observations": parsed.observations})
    sub.tutor_notes = notes[-20:]
    db.commit()
    return parsed.model_dump(), sub.hints_used


def evaluate(db: Session, user: User, submission_id: int, content: str | None, time_spent: int | None):
    sub = _get_submission(db, user, submission_id)
    if sub.status == "evaluated":
        raise ValidationAppError("This response has already been evaluated.", code="already_evaluated")
    if content is not None:
        sub.content = content
    if time_spent is not None:
        sub.time_spent_seconds = max(sub.time_spent_seconds or 0, time_spent)
    sub.word_count = word_count(sub.content)
    if sub.word_count < 20:
        raise ValidationAppError("Write at least 20 words before submitting for evaluation.", code="too_short")
    # Persist the learner's work BEFORE calling the AI so nothing is lost if analysis fails.
    sub.status = "submitted"
    sub.submitted_at = utcnow()
    sub.failure_reason = None
    db.commit()

    try:
        evaluation, records, extra = writing_examiner.evaluate_submission(db, user, sub)
    except AIError as exc:
        db.rollback()
        sub = _get_submission(db, user, submission_id)
        sub.status = "evaluation_failed"
        sub.failure_reason = getattr(exc, "category", "provider_error")
        db.commit()
        logger.warning("Writing evaluation failed for submission %s: %s", submission_id, exc)
        raise AIUnavailableError(details={"submission_id": submission_id, "status": "evaluation_failed"}) from exc

    sub.status = "evaluated"
    sub.evaluated_at = utcnow()
    task = sub.task
    best_before = db.scalar(select(func.max(WritingEvaluation.overall_band)).where(WritingEvaluation.user_id == user.id, WritingEvaluation.id != evaluation.id))
    writing_band = writing_examiner.writing_band_estimate(db, user, evaluation, task.task_type)
    xp = [(50, "writing_submission", f"Writing evaluated: {task.title}")]
    if best_before is not None and evaluation.overall_band > best_before:
        xp.append((25, "personal_best", f"New personal best writing band: {evaluation.overall_band:g}"))
    outcome = si_core.process_activity(
        db,
        user,
        si_core.ActivityEvent(
            activity="writing",
            title=f"Writing {task.task_type.replace('task', 'Task ')}: {task.title}",
            duration_seconds=sub.time_spent_seconds or 0,
            ref_type="writing_submission",
            ref_id=sub.id,
            score=band_to_score(evaluation.overall_band),
            skill_results=[
                SkillResult("writing", band_to_score(writing_band), writing_band, task.difficulty),
                SkillResult("grammar", band_to_score(evaluation.grammatical_range_accuracy), None, None),
                SkillResult("vocabulary", band_to_score(evaluation.lexical_resource), None, None),
            ],
            errors=records,
            usage_text=sub.content,
            usage_source="writing",
            topic=task.topic,
            xp=xp,
            mission_metrics={"writing_tasks": 1},
            misspelled_words=extra["misspelled"],
            completes_kinds={"writing"},
            meta={"band": evaluation.overall_band, "task_type": task.task_type},
        ),
    )
    writing_examiner.link_mistakes(db, evaluation)
    db.commit()
    return _get_submission(db, user, submission_id), outcome


def evaluation_out(evaluation: WritingEvaluation) -> WritingEvaluationOut:
    order = ("task_response", "coherence_cohesion", "lexical_resource", "grammatical_range_accuracy")
    criteria = [
        CriterionOut(
            key=k,
            label=evaluation.criteria_feedback.get(k, {}).get("label", k),
            band=getattr(evaluation, k),
            comment=evaluation.criteria_feedback.get(k, {}).get("comment", ""),
        )
        for k in order
    ]
    metrics = evaluation.metrics or {}
    public_metrics = {
        k: metrics.get(k)
        for k in (
            "word_count",
            "min_words",
            "paragraph_count",
            "sentence_count",
            "avg_sentence_length",
            "lexical_diversity",
            "academic_words",
            "linker_variety",
            "linkers",
            "complex_ratio",
            "repeated_words",
            "overview",
            "position_statement",
            "conclusion",
        )
        if k in metrics
    }
    return WritingEvaluationOut(
        id=evaluation.id,
        overall_band=evaluation.overall_band,
        criteria=criteria,
        strengths=evaluation.strengths,
        weaknesses=evaluation.weaknesses,
        task_response_issues=evaluation.task_response_issues,
        cohesion_issues=evaluation.cohesion_issues,
        vocabulary_issues=evaluation.vocabulary_issues,
        advice=evaluation.advice,
        summary=evaluation.summary,
        recommended_exercise=evaluation.recommended_exercise,
        metrics=public_metrics,
        errors=[WritingErrorOut.model_validate(e) for e in evaluation.errors],
        provider=evaluation.provider,
        model=evaluation.model,
        is_mock=evaluation.is_mock,
        created_at=evaluation.created_at,
    )


def _previous_attempt(db: Session, sub: WritingSubmission) -> PreviousAttempt | None:
    base = (
        select(WritingSubmission, WritingEvaluation)
        .join(WritingEvaluation, WritingEvaluation.submission_id == WritingSubmission.id)
        .where(WritingSubmission.user_id == sub.user_id, WritingSubmission.id != sub.id, WritingSubmission.created_at < sub.created_at)
        .order_by(WritingSubmission.created_at.desc())
    )
    row = db.execute(base.where(WritingSubmission.task_id == sub.task_id).limit(1)).first()
    same = True
    if row is None:
        row = db.execute(
            base.join(WritingTask, WritingTask.id == WritingSubmission.task_id).where(WritingTask.task_type == sub.task.task_type).limit(1)
        ).first()
        same = False
    if row is None:
        return None
    prev_sub, prev_eval = row
    return PreviousAttempt(
        submission_id=prev_sub.id,
        overall_band=prev_eval.overall_band,
        same_task=same,
        evaluated_at=prev_sub.evaluated_at,
        criteria={k: getattr(prev_eval, k) for k in ("task_response", "coherence_cohesion", "lexical_resource", "grammatical_range_accuracy")},
    )


def submission_out(db: Session, sub: WritingSubmission) -> SubmissionOut:
    evaluated = sub.evaluation is not None
    return SubmissionOut(
        id=sub.id,
        task=WritingTaskOut.model_validate(sub.task),
        mode=sub.mode,
        content=sub.content,
        word_count=sub.word_count,
        time_spent_seconds=sub.time_spent_seconds,
        status=sub.status,
        hints_used=sub.hints_used,
        tutor_notes=sub.tutor_notes or [],
        failure_reason=sub.failure_reason,
        autosaved_at=sub.autosaved_at,
        submitted_at=sub.submitted_at,
        evaluated_at=sub.evaluated_at,
        created_at=sub.created_at,
        key_points=sub.task.key_points if evaluated else None,
        evaluation=evaluation_out(sub.evaluation) if evaluated else None,
        previous=_previous_attempt(db, sub) if evaluated else None,
    )


def get_submission(db: Session, user: User, submission_id: int) -> SubmissionOut:
    return submission_out(db, _get_submission(db, user, submission_id))


def history(db: Session, user: User, page: int, page_size: int) -> tuple[list[SubmissionSummary], int]:
    q = select(WritingSubmission).where(WritingSubmission.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.options(selectinload(WritingSubmission.evaluation)).order_by(WritingSubmission.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [
        SubmissionSummary(
            id=s.id,
            task_id=s.task_id,
            task_title=s.task.title,
            task_type=s.task.task_type,
            module=s.task.module,
            category=s.task.category,
            mode=s.mode,
            status=s.status,
            word_count=s.word_count,
            overall_band=s.evaluation.overall_band if s.evaluation else None,
            created_at=s.created_at,
            evaluated_at=s.evaluated_at,
        )
        for s in rows
    ], total


def delete_draft(db: Session, user: User, submission_id: int) -> None:
    sub = _get_submission(db, user, submission_id)
    if sub.status not in ("draft", "evaluation_failed"):
        raise ValidationAppError("Only drafts can be deleted.")
    db.delete(sub)
    db.commit()
