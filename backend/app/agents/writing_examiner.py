"""SI Writing Examiner - IELTS-style writing evaluation.

Pipeline:
  1. deterministic metrics (word count, paragraphs, linking, lexical diversity...)      [analytics]
  2. high-precision rule-based error detection                                          [analytics]
  3. AI evaluation with the official-criteria rubric, metrics and learner memory         [AI / mock]
  4. validation: bands snapped to the 0.5 grid, under-length penalties enforced, every
     quoted error must exist verbatim in the learner's text (fabricated quotes are dropped),
     rule detections the AI missed are merged in
  5. storage of the evaluation and error annotations; the submission was saved BEFORE the
     AI call so nothing is lost if the AI fails
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.context import build_context
from app.agents.error_analyst import ErrorRecord, signature_for
from app.ai.client import ai_client
from app.ai.schemas import WritingEvaluationAI
from app.analytics.grammar_rules import DetectedError, detect_errors
from app.analytics.writing_metrics import analyze_essay
from app.core.levels import clamp_band, round_band, round_band_down, snap_half
from app.core.taxonomy import category_for, label_for, normalize_subcategory
from app.models import Mistake, User, WritingError, WritingEvaluation, WritingSubmission, WritingTask

logger = logging.getLogger("linguasi.agents.writing")

CRITERIA = ("task_response", "coherence_cohesion", "lexical_resource", "grammatical_range_accuracy")


@dataclass
class LocatedError:
    category: str
    subcategory: str
    original: str
    corrected: str
    explanation: str
    severity: str
    start: int | None
    end: int | None
    source: str
    context: str


def task_labels(task: WritingTask) -> tuple[str, str]:
    module_label = {"academic": "IELTS Academic", "general_training": "IELTS General Training", "general_english": "General English"}[task.module]
    if task.task_type == "task1":
        label = "Task 1 report" if task.module == "academic" else "Task 1 letter"
    elif task.task_type == "task2":
        label = "Task 2 essay"
    else:
        label = "General writing"
    return label, module_label


def visual_summary(task: WritingTask) -> str:
    visual = task.visual
    if not visual:
        return ""
    if visual.get("chart_type") == "process":
        steps = "; ".join(f"{i + 1}. {s}" for i, s in enumerate(visual.get("steps", [])))
        return f"Visual (process diagram '{visual.get('title', '')}'): {steps}"
    lines = [f"Visual ({visual.get('chart_type')} '{visual.get('title', '')}', unit: {visual.get('unit', '')}):"]
    cats = visual.get("categories", [])
    for series in visual.get("series", []):
        values = ", ".join(f"{c}={v}" for c, v in zip(cats, series.get("values", []), strict=False))
        lines.append(f"- {series.get('name')}: {values}")
    return "\n".join(lines)


def _locate(text: str, original: str, used: list[tuple[int, int]]) -> tuple[int, int] | None:
    if not original or not original.strip():
        return None
    start = 0
    while True:
        idx = text.find(original, start)
        if idx == -1:
            break
        span = (idx, idx + len(original))
        if not any(s < span[1] and span[0] < e for s, e in used):
            return span
        start = idx + 1
    # tolerate case and whitespace differences only
    pattern = r"\s+".join(re.escape(part) for part in original.split())
    for m in re.finditer(pattern, text, re.IGNORECASE):
        span = (m.start(), m.end())
        if not any(s < span[1] and span[0] < e for s, e in used):
            return span
    return None


def _sentence_around(text: str, start: int, end: int) -> str:
    left = max(text.rfind(c, 0, start) for c in ".!?\n")
    rights = [i for i in (text.find(c, end) for c in ".!?\n") if i != -1]
    right = min(rights) + 1 if rights else len(text)
    return text[left + 1 : right].strip()[:400]


def merge_errors(text: str, ai_errors: list, rule_errors: list[DetectedError]) -> tuple[list[LocatedError], int]:
    """Validate AI errors against the text and merge in rule-based detections. Returns (errors, dropped)."""
    located: list[LocatedError] = []
    used: list[tuple[int, int]] = []
    dropped = 0
    for err in ai_errors:
        original = (err.original or "").strip()
        corrected = (err.corrected or "").strip()
        if not original or not corrected or original.lower() == corrected.lower():
            dropped += 1
            continue
        span = _locate(text, original, used)
        if span is None:
            dropped += 1  # the quote is not in the learner's text: never store fabricated evidence
            continue
        used.append(span)
        sub = normalize_subcategory(err.subcategory, err.category)
        located.append(
            LocatedError(
                category_for(sub),
                sub,
                text[span[0] : span[1]],
                corrected,
                err.explanation,
                err.severity if err.severity in ("low", "medium", "high") else "medium",
                span[0],
                span[1],
                "ai",
                _sentence_around(text, *span),
            )
        )
    for det in rule_errors:
        overlaps = [e for e in located if e.start is not None and e.start < det.end and det.start < e.end]
        if any(e.subcategory == det.subcategory for e in overlaps):
            continue
        highlight = not overlaps and det.highlight
        located.append(
            LocatedError(
                det.category,
                det.subcategory,
                det.original,
                det.corrected,
                det.explanation,
                det.severity,
                det.start if highlight else None,
                det.end if highlight else None,
                "rules",
                det.context,
            )
        )
        if highlight:
            used.append((det.start, det.end))
    located.sort(key=lambda e: (e.start is None, e.start or 0))
    return located, dropped


def evaluate_submission(db: Session, user: User, submission: WritingSubmission) -> tuple[WritingEvaluation, list[ErrorRecord], dict]:
    """Run the full evaluation. Raises AIError if the AI step fails (caller handles persistence)."""
    task = submission.task
    text = submission.content
    academic = not (task.module == "general_english" or task.category == "informal_letter")
    rule_errors = detect_errors(text, academic=academic)
    analysis = analyze_essay(
        text, task_type=task.task_type, module=task.module, prompt=task.prompt, key_points=task.key_points, min_words=task.min_words, errors=rule_errors
    )
    ctx = build_context(db, user)
    task_label, module_label = task_labels(task)
    metrics = analysis.to_dict()
    metrics_text = (
        f"words={analysis.word_count} (minimum {task.min_words}); paragraphs={analysis.paragraph_count}; "
        f"sentences={analysis.sentence_count}; avg sentence length={analysis.avg_sentence_length}; "
        f"lexical diversity (MATTR)={analysis.lexical_diversity}; academic words={len(analysis.academic_words)}; "
        f"linking devices={analysis.linker_variety} distinct; complex sentence ratio={analysis.complex_ratio}; "
        f"overview present={analysis.overview}; position statement={analysis.position_statement}; conclusion={analysis.conclusion}; "
        f"figures mentioned={analysis.numbers_count}; repeated words={[w for w, _ in analysis.repeated_words]}"
    )
    rule_text = "\n".join(f"- [{e.subcategory}] '{e.original}' -> '{e.corrected}'" for e in rule_errors[:25]) or "(none detected)"
    variables = {
        "task_label": task_label,
        "module_label": module_label,
        "category": task.category,
        "min_words": task.min_words,
        "prompt": task.prompt,
        "visual_summary": visual_summary(task),
        "key_points": task.key_points or ["(not specified)"],
        "metrics": metrics_text,
        "rule_errors": rule_text,
        "learner_context": ctx.for_prompt("writing"),
        "word_count": analysis.word_count,
        "response": text,
    }
    mock_context = {
        "analysis": analysis,
        "rule_errors": rule_errors,
        "task": {
            "task_type": task.task_type,
            "module": task.module,
            "category": task.category,
            "topic": task.topic,
            "min_words": task.min_words,
            "key_points": task.key_points,
            "prompt": task.prompt,
        },
        "recurring": ctx.recurring_subcategories,
    }
    parsed, result = ai_client.generate_model("writing_evaluate", variables, WritingEvaluationAI, user_id=user.id, mock_context=mock_context)

    bands = {key: snap_half(clamp_band(getattr(parsed, key).band)) for key in CRITERIA}
    # Enforce the under-length penalty even if the model was lenient.
    if analysis.word_count < task.min_words * 0.75:
        bands["task_response"] = min(bands["task_response"], 4.5)
    elif analysis.word_count < task.min_words:
        bands["task_response"] = min(bands["task_response"], 6.0)
    overall = round_band_down(sum(bands.values()) / 4)

    located, dropped = merge_errors(text, parsed.errors, rule_errors)
    if dropped:
        logger.info("Dropped %s AI-reported errors that were not found verbatim in submission %s", dropped, submission.id)
    recurring = set(ctx.recurring_subcategories)
    labels = {
        "task_response": "Task Achievement" if task.task_type == "task1" else "Task Response",
        "coherence_cohesion": "Coherence & Cohesion",
        "lexical_resource": "Lexical Resource",
        "grammatical_range_accuracy": "Grammatical Range & Accuracy",
    }
    evaluation = WritingEvaluation(
        submission_id=submission.id,
        user_id=user.id,
        overall_band=overall,
        task_response=bands["task_response"],
        coherence_cohesion=bands["coherence_cohesion"],
        lexical_resource=bands["lexical_resource"],
        grammatical_range_accuracy=bands["grammatical_range_accuracy"],
        criteria_feedback={key: {"label": labels[key], "band": bands[key], "comment": getattr(parsed, key).comment} for key in CRITERIA},
        strengths=parsed.strengths[:6],
        weaknesses=parsed.weaknesses[:6],
        task_response_issues=parsed.task_response_issues[:6],
        cohesion_issues=parsed.cohesion_issues[:6],
        vocabulary_issues=parsed.vocabulary_issues[:6],
        advice=parsed.advice[:6],
        summary=parsed.summary,
        recommended_exercise={
            "title": parsed.recommended_exercise.title,
            "focus": normalize_subcategory(parsed.recommended_exercise.focus)
            if parsed.recommended_exercise.focus != "argument_building"
            else "idea_development",
            "description": parsed.recommended_exercise.description,
        },
        metrics=metrics | {"rule_errors": len(rule_errors), "ai_errors_dropped": dropped},
        provider=result.provider,
        model=(result.model or "")[:60],
        is_mock=ai_client.is_mock,
    )
    db.add(evaluation)
    submission.evaluation = evaluation
    db.flush()
    records: list[ErrorRecord] = []
    for err in located:
        db.add(
            WritingError(
                evaluation_id=evaluation.id,
                submission_id=submission.id,
                user_id=user.id,
                category=err.category,
                subcategory=err.subcategory,
                original=err.original,
                corrected=err.corrected,
                explanation=err.explanation,
                severity=err.severity,
                start_offset=err.start,
                end_offset=err.end,
                repeated=err.subcategory in recurring,
                source=err.source,
            )
        )
        records.append(
            ErrorRecord(
                source="writing",
                category=err.category,
                subcategory=err.subcategory,
                original=err.original,
                corrected=err.corrected,
                explanation=err.explanation,
                context=err.context,
                severity=err.severity,
                ref_type="writing_submission",
                ref_id=submission.id,
            )
        )
    db.flush()
    misspelled = [e.corrected for e in located if e.subcategory == "spelling" and " " not in e.corrected]
    return evaluation, records, {"misspelled": misspelled, "analysis": analysis}


def link_mistakes(db: Session, evaluation: WritingEvaluation) -> None:
    """After SI Core stored the mistakes, link each error annotation to its tracker entry."""
    for err in evaluation.errors:
        record = ErrorRecord(source="writing", category=err.category, subcategory=err.subcategory, original=err.original, corrected=err.corrected)
        mistake = db.scalar(select(Mistake).where(Mistake.user_id == evaluation.user_id, Mistake.signature == signature_for(record)).limit(1))
        if mistake:
            err.mistake_id = mistake.id


def writing_band_estimate(db: Session, user: User, latest: WritingEvaluation, latest_task_type: str) -> float:
    """Combine the latest Task 1 and Task 2 bands with IELTS weighting (Task 2 counts double)."""
    rows = db.execute(
        select(WritingEvaluation.overall_band, WritingTask.task_type)
        .join(WritingSubmission, WritingSubmission.id == WritingEvaluation.submission_id)
        .join(WritingTask, WritingTask.id == WritingSubmission.task_id)
        .where(WritingEvaluation.user_id == user.id, WritingEvaluation.id != latest.id)
        .order_by(WritingEvaluation.created_at.desc())
        .limit(10)
    ).all()
    latest_by_type = {latest_task_type: latest.overall_band}
    for band, task_type in rows:
        latest_by_type.setdefault(task_type, band)
    t1, t2 = latest_by_type.get("task1"), latest_by_type.get("task2")
    if latest_task_type == "general":
        return latest.overall_band
    if t1 is not None and t2 is not None:
        return round_band((t1 + 2 * t2) / 3)
    return latest.overall_band


__all__ = ["evaluate_submission", "link_mistakes", "writing_band_estimate", "task_labels", "visual_summary", "label_for"]
