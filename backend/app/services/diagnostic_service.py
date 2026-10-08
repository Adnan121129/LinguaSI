"""Onboarding and the lightweight diagnostic assessment that initialises the learner profile."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import learning_planner, progress_analyst, si_core, vocabulary_engine, writing_examiner
from app.ai.providers.base import AIError
from app.analytics.grammar_rules import detect_errors
from app.analytics.scoring import check_answer
from app.analytics.speaking_metrics import aggregate, analyze_response, heuristic_speaking
from app.analytics.text import word_count
from app.analytics.writing_metrics import analyze_essay, heuristic_evaluation
from app.core.clock import utcnow
from app.core.errors import NotFoundError, ValidationAppError
from app.core.levels import accuracy_to_band, band_to_cefr, band_to_score, cefr_to_band, round_band, score_to_cefr
from app.models import DiagnosticAttempt, Recommendation, User, WritingSubmission, WritingTask
from app.schemas.onboarding import DiagnosticResult, DiagnosticSection, OnboardingRequest
from app.services import user_service
from app.services.content import diagnostic_bank

logger = logging.getLogger("linguasi.diagnostic")
LEVEL_WEIGHT = {"A1": 1.0, "A2": 1.0, "B1": 1.5, "B2": 2.0, "C1": 2.5, "C2": 3.0}
CEFR_DIFFICULTY = {"A1": 1, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}


def complete_onboarding(db: Session, user: User, data: OnboardingRequest) -> User:
    profile = user.profile
    if data.name:
        user.name = " ".join(data.name.split())
    for field in ("goal", "ielts_module", "self_reported_level", "target_band", "test_date", "daily_minutes", "preferred_mode", "confidence"):
        setattr(profile, field, getattr(data, field))
    profile.preferred_topics = [t.strip().lower()[:40] for t in data.preferred_topics if t.strip()]
    if data.timezone:
        profile.timezone = data.timezone
    profile.onboarding_completed = True
    user_service.sync_band_goal(db, user)
    db.commit()
    db.refresh(user)
    return user


def _public_items(items: list[dict]) -> list[dict]:
    return [{"id": i["id"], "level": i.get("level"), "qtype": i.get("qtype"), "prompt": i["prompt"], "options": i.get("options")} for i in items]


def start(db: Session, user: User) -> tuple[DiagnosticAttempt, dict]:
    attempt = db.scalar(
        select(DiagnosticAttempt)
        .where(DiagnosticAttempt.user_id == user.id, DiagnosticAttempt.status == "in_progress")
        .order_by(DiagnosticAttempt.started_at.desc())
        .limit(1)
    )
    bank = diagnostic_bank()
    if attempt is None:
        attempt = DiagnosticAttempt(user_id=user.id, status="in_progress", items=bank, started_at=utcnow())
        db.add(attempt)
        db.commit()
    items = attempt.items
    public = {
        "vocabulary": _public_items(items["vocabulary"]),
        "grammar": _public_items(items["grammar"]),
        "reading": {"title": items["reading"]["title"], "text": items["reading"]["text"], "questions": _public_items(items["reading"]["questions"])},
        "listening": {
            "title": items["listening"]["title"],
            "speakers": items["listening"]["speakers"],
            "segments": items["listening"]["segments"],
            "questions": _public_items(items["listening"]["questions"]),
        },
        "writing": items["writing"],
        "speaking": items["speaking"],
    }
    return attempt, public


def _weighted(items: list[dict], answers: dict[str, str]) -> tuple[float, int]:
    total_w = sum(LEVEL_WEIGHT.get(i["level"], 1.0) for i in items)
    got_w, correct = 0.0, 0
    for i in items:
        if (answers.get(i["id"]) or "").strip().lower() == i["answer"].strip().lower():
            got_w += LEVEL_WEIGHT.get(i["level"], 1.0)
            correct += 1
    return round(got_w / total_w * 100, 1) if total_w else 0.0, correct


def _comprehension(questions: list[dict], answers: dict[str, str]) -> tuple[float, int]:
    correct = 0
    for q in questions:
        ok, _ = check_answer(answers.get(q["id"]), q["answer"], qtype=q["qtype"], accepted=q.get("accepted"), options=q.get("options"))
        correct += int(ok)
    return round(correct / len(questions) * 100, 1) if questions else 0.0, correct


def _diagnostic_task(db: Session, prompt: str, min_words: int, minutes: int) -> WritingTask:
    task = db.scalar(select(WritingTask).where(WritingTask.seed_key == "diagnostic-writing"))
    if task is None:
        task = WritingTask(
            seed_key="diagnostic-writing",
            task_type="general",
            module="general_english",
            category="general_opinion",
            topic="urban",
            title="Diagnostic: city or countryside",
            prompt=prompt,
            instructions=f"Write at least {min_words} words.",
            key_points=["clear opinion", "reasons", "examples"],
            min_words=min_words,
            time_limit_minutes=minutes,
            difficulty=2,
            source="seed",
        )
        db.add(task)
        db.flush()
    return task


def submit(db: Session, user: User, attempt_id: int, answers: dict[str, str], writing: str, speaking: list) -> DiagnosticResult:
    attempt = db.get(DiagnosticAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise NotFoundError("Diagnostic attempt not found.")
    if attempt.status == "completed":
        raise ValidationAppError("This diagnostic has already been submitted.", code="already_submitted")
    items = attempt.items
    vocab_score, vocab_correct = _weighted(items["vocabulary"], answers)
    grammar_score, grammar_correct = _weighted(items["grammar"], answers)
    reading_acc, reading_correct = _comprehension(items["reading"]["questions"], answers)
    listening_acc, listening_correct = _comprehension(items["listening"]["questions"], answers)
    reading_band = accuracy_to_band(reading_acc, 2)
    listening_band = accuracy_to_band(listening_acc, 2)

    writing_band, writing_feedback, error_records = None, None, []
    if word_count(writing) >= 30:
        cfg = items["writing"]
        task = _diagnostic_task(db, cfg["prompt"], cfg["min_words"], cfg["time_limit_minutes"])
        sub = WritingSubmission(
            user_id=user.id, task_id=task.id, mode="exam", content=writing, word_count=word_count(writing), status="submitted", submitted_at=utcnow()
        )
        db.add(sub)
        db.flush()
        try:
            evaluation, error_records, _ = writing_examiner.evaluate_submission(db, user, sub)
            sub.status = "evaluated"
            sub.evaluated_at = utcnow()
            writing_band = evaluation.overall_band
            writing_feedback = {
                "band": evaluation.overall_band,
                "summary": evaluation.summary,
                "submission_id": sub.id,
                "top_errors": [{"original": e.original, "corrected": e.corrected, "label": e.subcategory} for e in evaluation.errors[:3]],
            }
        except AIError:
            logger.info("Diagnostic writing AI evaluation unavailable; using heuristic estimate")
            errs = detect_errors(writing, academic=False)
            analysis = analyze_essay(writing, task_type="general", module="general_english", prompt=task.prompt, min_words=task.min_words, errors=errs)
            heuristic = heuristic_evaluation(analysis, errs, task_type="general", module="general_english", category="general_opinion")
            writing_band = heuristic.overall
            sub.status = "evaluation_failed"
            writing_feedback = {"band": writing_band, "summary": "Quick estimate (AI analysis was unavailable).", "submission_id": sub.id, "top_errors": []}

    speaking_band = None
    if speaking:
        prompts = {s["id"]: s["prompt"] for s in items["speaking"]}
        responses = []
        for sample in speaking:
            text = sample.transcript.strip()
            if not text:
                continue
            metrics = analyze_response(text, question=prompts.get(sample.id, ""), part=1, duration_seconds=sample.duration_seconds)
            responses.append({"transcript": text, "part": 1, "metrics": metrics.to_dict(), "stt_confidence": None})
        if responses:
            agg = aggregate(responses)
            errs = [e for r in responses for e in detect_errors(r["transcript"], mode="speaking")]
            speaking_band = heuristic_speaking(agg, errs).overall

    estimates: dict[str, dict] = {
        "vocabulary": {"score": vocab_score},
        "grammar": {"score": grammar_score},
        "reading": {"score": reading_acc, "band": reading_band},
        "listening": {"score": listening_acc, "band": listening_band},
    }
    if writing_band is not None:
        estimates["writing"] = {"score": band_to_score(writing_band), "band": writing_band}
    if speaking_band is not None:
        estimates["speaking"] = {"score": band_to_score(speaking_band), "band": speaking_band}
    ielts_bands = [e["band"] for k, e in estimates.items() if k in ("reading", "listening", "writing", "speaking")]
    overall = round_band(sum(ielts_bands) / len(ielts_bands)) if ielts_bands else None
    vg_cefr = score_to_cefr((vocab_score + grammar_score) / 2)
    cefr = band_to_cefr(overall) if overall is not None else vg_cefr
    if overall is not None and abs((cefr_to_band(vg_cefr) or overall) - overall) >= 2:
        cefr = band_to_cefr(round_band((overall + (cefr_to_band(vg_cefr) or overall)) / 2))
    base_difficulty = CEFR_DIFFICULTY.get(cefr, 2)
    for key, est in estimates.items():
        bump = 1 if key in ("reading", "listening") and est["score"] >= 85 else -1 if key in ("reading", "listening") and est["score"] < 40 else 0
        est["difficulty"] = max(1, min(5, base_difficulty + bump))

    profile = user.profile
    progress_analyst.initialise_from_diagnostic(db, user, estimates)
    profile.diagnostic_completed = True
    profile.estimated_cefr = cefr
    profile.estimated_band = overall
    profile.band_confidence = 0.25
    vocabulary_engine.ensure_starter_vocabulary(db, user, count=15)

    attempt.answers = answers
    attempt.writing_sample = writing
    attempt.writing_band = writing_band
    attempt.speaking_sample = "\n".join(s.transcript for s in speaking) or None
    attempt.speaking_band = speaking_band
    attempt.estimated_cefr = cefr
    attempt.estimated_band = overall
    attempt.skill_estimates = estimates
    attempt.section_scores = {
        "vocabulary": {"score": vocab_score, "correct": vocab_correct, "total": len(items["vocabulary"])},
        "grammar": {"score": grammar_score, "correct": grammar_correct, "total": len(items["grammar"])},
        "reading": {"score": reading_acc, "band": reading_band, "correct": reading_correct, "total": len(items["reading"]["questions"])},
        "listening": {"score": listening_acc, "band": listening_band, "correct": listening_correct, "total": len(items["listening"]["questions"])},
        "writing": {"band": writing_band, "feedback": writing_feedback},
        "speaking": {"band": speaking_band},
    }
    attempt.status = "completed"
    attempt.completed_at = utcnow()
    db.flush()
    outcome = si_core.process_activity(
        db,
        user,
        si_core.ActivityEvent(
            activity="diagnostic",
            title="Diagnostic assessment",
            duration_seconds=int((utcnow() - attempt.started_at).total_seconds()) if attempt.started_at else 900,
            ref_type="diagnostic_attempt",
            ref_id=attempt.id,
            score=round((vocab_score + grammar_score + reading_acc + listening_acc) / 4, 1),
            errors=error_records,
            xp=[(100, "diagnostic", "Diagnostic assessment completed")],
            completes_kinds={"diagnostic"},
            meta={"cefr": cefr, "band": overall},
        ),
    )
    learning_planner.get_or_create_mission(db, user)
    db.commit()
    return result(db, user, attempt, outcome)


def result(db: Session, user: User, attempt: DiagnosticAttempt, outcome=None) -> DiagnosticResult:
    s = attempt.section_scores or {}
    labels = {"vocabulary": "Vocabulary", "grammar": "Grammar", "reading": "Reading", "listening": "Listening", "writing": "Writing", "speaking": "Speaking"}
    sections = []
    for key in ("vocabulary", "grammar", "reading", "listening", "writing", "speaking"):
        data = s.get(key, {})
        note = None
        if key == "writing" and data.get("band") is None:
            note = "Skipped - write at least 30 words to include writing."
        if key == "speaking" and data.get("band") is None:
            note = "Optional section skipped."
        sections.append(
            DiagnosticSection(
                key=key, label=labels[key], score=data.get("score"), band=data.get("band"), correct=data.get("correct"), total=data.get("total"), note=note
            )
        )
    scored = [(sec.label, sec.score if sec.score is not None else band_to_score(sec.band)) for sec in sections if sec.score is not None or sec.band is not None]
    scored.sort(key=lambda x: x[1], reverse=True)
    strengths = [f"{label} ({value:.0f}/100)" for label, value in scored[:2]]
    focus = [w.get("reason") or w.get("label") for w in (user.profile.weak_areas or [])][:3] or [f"{label} ({value:.0f}/100)" for label, value in scored[-2:]]
    recs = db.scalars(
        select(Recommendation).where(Recommendation.user_id == user.id, Recommendation.status == "active").order_by(Recommendation.priority.desc()).limit(3)
    ).all()
    return DiagnosticResult(
        attempt_id=attempt.id,
        estimated_cefr=attempt.estimated_cefr,
        estimated_band=attempt.estimated_band,
        confidence="low",
        sections=sections,
        strengths=strengths,
        focus_areas=focus,
        writing_feedback=(s.get("writing") or {}).get("feedback"),
        next_steps=[{"title": r.title, "why": r.why, "route": (r.action or {}).get("route")} for r in recs],
        completed_at=attempt.completed_at,
        outcome=outcome,
    )


def latest(db: Session, user: User) -> DiagnosticResult | None:
    attempt = db.scalar(
        select(DiagnosticAttempt)
        .where(DiagnosticAttempt.user_id == user.id, DiagnosticAttempt.status == "completed")
        .order_by(DiagnosticAttempt.completed_at.desc())
        .limit(1)
    )
    return result(db, user, attempt) if attempt else None
