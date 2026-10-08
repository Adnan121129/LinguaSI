"""SI Learning Planner - hybrid recommendations and daily missions.

1. A rule engine reads the learner's real performance data and proposes candidate activities,
   each with the exact signals that triggered it and a factual "Why this?" explanation.
2. Candidates are ranked by weakness severity and goal relevance.
3. The AI (or the mock planner) only turns the chosen tasks into a short personalised narrative;
   it never decides on its own what the learner needs, and it cannot invent the facts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.context import LearnerContext, build_context
from app.agents.vocabulary_engine import retention_stats
from app.ai.client import ai_client
from app.ai.providers.base import AIError
from app.ai.schemas import DailyPlanAI
from app.core.clock import ensure_aware, local_today, utcnow
from app.core.taxonomy import label_for, practice_topic_for
from app.models import (
    DailyMission,
    ListeningAttempt,
    Mistake,
    ReadingAttempt,
    Recommendation,
    SpeakingEvaluation,
    StudySession,
    User,
    WritingEvaluation,
)
from app.repositories import stats

logger = logging.getLogger("linguasi.agents.planner")


@dataclass
class Candidate:
    rule: str
    kind: str
    title: str
    description: str
    why: str
    priority: float
    route: str
    minutes: int
    signals: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    focus: str | None = None
    mission_metric: str | None = None
    mission_target: int = 1

    @property
    def key(self) -> str:
        return f"{self.rule}:{self.focus or ''}"


QTYPE_LABELS = {
    "true_false_not_given": "True/False/Not Given",
    "yes_no_not_given": "Yes/No/Not Given",
    "matching_headings": "matching headings",
    "matching_information": "matching information",
    "multiple_choice": "multiple choice",
    "sentence_completion": "sentence completion",
    "summary_completion": "summary completion",
    "short_answer": "short answer",
    "form_completion": "form completion",
    "note_completion": "note completion",
}


def build_candidates(db: Session, user: User, ctx: LearnerContext | None = None) -> list[Candidate]:
    ctx = ctx or build_context(db, user)
    profile = user.profile
    ielts = profile.goal == "ielts"
    out: list[Candidate] = []
    skills = ctx.skills

    if not profile.diagnostic_completed:
        out.append(
            Candidate(
                "diagnostic",
                "diagnostic",
                "Take your diagnostic assessment",
                "A 15-minute check of vocabulary, grammar, reading, listening and writing.",
                "SI needs a starting point to personalise your plan - every recommendation after this uses your results.",
                1.0,
                "/onboarding/diagnostic",
                15,
            )
        )

    # R1 - recurring grammar patterns -> targeted repair challenge
    for rec in ctx.recurring:
        topic = practice_topic_for(rec["subcategory"])
        if rec["category"] in ("grammar", "vocabulary", "academic_style", "spelling") and topic and rec["count"] >= 3:
            example = f" (e.g. '{rec['example']['original']}' → '{rec['example']['corrected']}')" if rec.get("example") else ""
            out.append(
                Candidate(
                    "grammar_repair",
                    "grammar",
                    f"5-minute {rec['label']} Repair Challenge",
                    f"A short drill built from your own {rec['label'].lower()} mistakes.",
                    f"You made {rec['count']} {rec['label'].lower()} mistakes in the last 30 days{example}. Repairing one pattern at a time is the fastest way to raise your grammar score.",
                    0.85 + min(0.1, rec["count"] / 100),
                    f"/practice/new?focus={rec['subcategory']}",
                    5,
                    signals={"subcategory": rec["subcategory"], "count_30d": rec["count"]},
                    focus=rec["subcategory"],
                    mission_metric="grammar_items",
                    mission_target=5,
                )
            )
            break

    grammar = skills.get("grammar")
    if grammar and grammar.get("attempts") and grammar["score"] < 60 and not any(c.rule == "grammar_repair" for c in out):
        out.append(
            Candidate(
                "grammar_low",
                "grammar",
                "Grammar drill: sentence structure",
                "Ten quick items on complete, accurate sentences.",
                f"Your grammar score is {grammar['score']:.0f}/100, below the 60 needed for steady progress.",
                0.8,
                "/practice/new?focus=sentence_structure",
                6,
                signals={"grammar_score": grammar["score"]},
                focus="sentence_structure",
                mission_metric="grammar_items",
                mission_target=5,
            )
        )

    # R8 - collocation weakness (the core cross-skill example)
    collocation_count = sum(r["count"] for r in ctx.recurring if r["subcategory"] in ("collocation", "word_choice"))
    if collocation_count >= 3:
        writing_with = db.scalars(
            select(Mistake.ref_id)
            .where(Mistake.user_id == user.id, Mistake.subcategory.in_(("collocation", "word_choice")), Mistake.source == "writing")
            .distinct()
            .limit(5)
        ).all()
        out.append(
            Candidate(
                "collocations",
                "vocabulary",
                "Practise 8 academic collocations",
                "Review collocations SI added to your queue, then use them in your next essay.",
                f"You often understand academic vocabulary but don't always combine words naturally. Your recent writing showed {collocation_count} collocation issues"
                + (f" across {len(writing_with)} submissions." if len(writing_with) > 1 else "."),
                0.82,
                "/vocabulary?focus=collocation",
                8,
                signals={"collocation_errors_30d": collocation_count},
                focus="collocation",
                mission_metric="vocab_reviews",
                mission_target=8,
            )
        )

    # R2 - vocabulary retention / due reviews
    retention = retention_stats(db, user.id)
    due = stats.vocab_due_count(db, user.id)
    if retention["reviews"] >= 10 and retention["accuracy"] is not None and retention["accuracy"] < 70:
        out.append(
            Candidate(
                "vocab_retention",
                "vocabulary",
                "Strengthen words you're forgetting",
                "Short, frequent reviews of words you recently got wrong.",
                f"Your accuracy over the last {retention['reviews']} vocabulary reviews is {retention['accuracy']:.0f}%, so SI is reviewing words more often.",
                0.75,
                "/vocabulary",
                6,
                signals=retention,
                mission_metric="vocab_reviews",
                mission_target=10,
            )
        )
    elif due >= 5:
        out.append(
            Candidate(
                "vocab_due",
                "vocabulary",
                f"Review {min(due, 20)} due words",
                "Spaced repetition works best when reviews happen on time.",
                f"{due} words are due for review today - reviewing them now prevents forgetting.",
                0.6,
                "/vocabulary",
                5,
                signals={"due": due},
                mission_metric="vocab_reviews",
                mission_target=min(due, 10),
            )
        )

    # R3 - speaking hesitation
    last_speaking = db.scalar(select(SpeakingEvaluation).where(SpeakingEvaluation.user_id == user.id).order_by(SpeakingEvaluation.created_at.desc()).limit(1))
    if last_speaking:
        fpm = (last_speaking.metrics or {}).get("fillers_per_minute", 0)
        developed = (last_speaking.metrics or {}).get("developed_ratio", 1)
        if fpm > 4 or (last_speaking.hesitation or {}).get("level") == "high":
            out.append(
                Candidate(
                    "speaking_fluency",
                    "speaking",
                    "Short speaking drill: smooth Part 1 answers",
                    "Three Part 1 questions focusing on fewer fillers and pauses.",
                    f"Your last speaking session had about {fpm:.1f} filler words per minute. Short, frequent drills build fluency faster than occasional long tests.",
                    0.78,
                    "/speaking?mode=part1",
                    8,
                    signals={"fillers_per_minute": fpm},
                    mission_metric="speaking_sessions",
                )
            )
        elif developed < 0.5:
            out.append(
                Candidate(
                    "speaking_development",
                    "speaking",
                    "Speaking drill: extend your answers",
                    "Practise the Answer + Reason + Example pattern.",
                    f"Only {developed * 100:.0f}% of your answers in the last session were developed with reasons or examples.",
                    0.7,
                    "/speaking?mode=part1",
                    8,
                    signals={"developed_ratio": developed},
                    mission_metric="speaking_sessions",
                )
            )

    # R4 - lowest writing criterion (recent evaluations) -> targeted practice for that criterion
    evals = db.scalars(select(WritingEvaluation).where(WritingEvaluation.user_id == user.id).order_by(WritingEvaluation.created_at.desc()).limit(3)).all()
    if evals:
        criteria = {
            "task_response": (
                "Task Response",
                "argument_building",
                "Argument development practice",
                "Build clear positions and fully developed body paragraphs, then apply them in a Task 2 essay.",
                "/practice/new?focus=argument_building",
            ),
            "coherence_cohesion": (
                "Coherence & Cohesion",
                "linking_words",
                "Cohesion workout: linking words and paragraphing",
                "Practise precise linking devices, then plan paragraphs with one central idea each.",
                "/practice/new?focus=linking_words",
            ),
            "lexical_resource": (
                "Lexical Resource",
                "collocation",
                "Lexical range: academic collocations",
                "Review topic collocations and use three of them in your next essay.",
                "/vocabulary?focus=collocation",
            ),
            "grammatical_range_accuracy": (
                "Grammatical Range & Accuracy",
                "sentence_structure",
                "Grammar for writing: accurate complex sentences",
                "Short drills on complex sentences, then a tutor-mode essay with grammar hints.",
                "/practice/new?focus=sentence_structure",
            ),
        }
        averages = {k: sum(getattr(e, k) for e in evals) / len(evals) for k in criteria}
        lowest = min(averages, key=averages.get)
        others = [v for k, v in averages.items() if k != lowest]
        target = profile.target_band or 6.5
        if averages[lowest] < target - 0.25 or (others and averages[lowest] <= min(others) - 0.5):
            label, focus, title, desc, route = criteria[lowest]
            out.append(
                Candidate(
                    f"writing_{lowest}",
                    "writing",
                    title,
                    desc,
                    f"{label} averages {averages[lowest]:.1f} in your last {len(evals)} writing evaluation{'s' if len(evals) > 1 else ''} - "
                    f"your lowest criterion (target {target:g}).",
                    0.84,
                    route,
                    10,
                    signals={"criterion": lowest, "average": round(averages[lowest], 2), "evaluations": len(evals)},
                    focus=focus,
                    mission_metric="vocab_reviews" if focus == "collocation" else "grammar_items",
                    mission_target=5 if focus != "collocation" else 8,
                )
            )

    # R5/R6 - reading and listening difficulty
    reading = skills.get("reading")
    if reading and reading.get("attempts", 0) >= 3:
        recent = [
            r
            for r in db.scalars(
                select(ReadingAttempt.accuracy)
                .where(ReadingAttempt.user_id == user.id, ReadingAttempt.status == "submitted")
                .order_by(ReadingAttempt.submitted_at.desc())
                .limit(3)
            )
            if r is not None
        ]
        if len(recent) == 3 and sum(recent) / 3 >= 85:
            nxt = min(5, (reading.get("difficulty") or 3) + 1)
            out.append(
                Candidate(
                    "reading_harder",
                    "reading",
                    f"Challenge yourself: level {nxt} reading",
                    "A longer passage with more demanding vocabulary and question types.",
                    f"You averaged {sum(recent) / 3:.0f}% in your last three reading sessions, so you're ready for harder texts.",
                    0.65,
                    f"/reading?difficulty={nxt}",
                    18,
                    signals={"avg_last3": round(sum(recent) / 3, 1)},
                    mission_metric="reading_exercises",
                )
            )
    listening = skills.get("listening")
    if listening and listening.get("attempts") and listening["score"] < 55:
        lower = max(1, (listening.get("difficulty") or 2) - 1)
        out.append(
            Candidate(
                "listening_support",
                "listening",
                "Targeted listening at a comfortable level",
                "Slower audio with form and note completion to build accuracy.",
                f"Your listening score is {listening['score']:.0f}/100. Practising at level {lower} with replays builds accuracy before speed.",
                0.77,
                f"/listening?difficulty={lower}",
                12,
                signals={"listening_score": listening["score"]},
                mission_metric="listening_exercises",
            )
        )

    # R13 - question-type weakness
    for model, skill in ((ReadingAttempt, "reading"), (ListeningAttempt, "listening")):
        qstats = stats.question_type_accuracy(db, user.id, model)
        weakest = sorted(((k, v) for k, v in qstats.items() if v["total"] >= 4 and v["accuracy"] < 60), key=lambda kv: kv[1]["accuracy"])
        if weakest:
            qtype, data = weakest[0]
            label = QTYPE_LABELS.get(qtype, qtype.replace("_", " "))
            out.append(
                Candidate(
                    f"{skill}_qtype",
                    skill,
                    f"{skill.title()} practice: {label} questions",
                    f"A {skill} set focusing on {label} questions, with explanations.",
                    f"You answered {data['correct']} of {data['total']} {label} questions correctly ({data['accuracy']:.0f}%) in recent {skill} practice.",
                    0.68,
                    f"/{skill}?types={qtype}",
                    15,
                    signals={"qtype": qtype, **data},
                    focus=qtype,
                    mission_metric=f"{skill}_exercises",
                )
            )

    # R14 - mistakes saved for later that are now due
    now = utcnow()
    revisit = db.scalars(
        select(Mistake.id).where(Mistake.user_id == user.id, Mistake.revisit_at.is_not(None), Mistake.revisit_at <= now, Mistake.status != "mastered")
    ).all()
    if revisit:
        out.append(
            Candidate(
                "revisit_mistakes",
                "mistakes",
                f"Revisit {len(revisit)} saved mistake{'s' if len(revisit) > 1 else ''}",
                "Mistakes you chose to revisit later are due now.",
                f"You asked SI to remind you about {len(revisit)} mistake{'s' if len(revisit) > 1 else ''} - they are due today.",
                0.6,
                "/mistakes?status=due",
                5,
                signals={"due": len(revisit)},
                mission_metric="mistake_repair",
            )
        )

    # R7 - neglected skills (IELTS goal) / lab activities (general goal)
    if ielts and profile.diagnostic_completed:
        for skill in ("writing", "speaking", "reading", "listening"):
            last = ensure_aware(db.scalar(select(func.max(StudySession.started_at)).where(StudySession.user_id == user.id, StudySession.activity == skill)))
            days = (now - last).days if last else None
            if days is None or days >= 5:
                data = skills.get(skill) or {}
                if days is not None:
                    why = f"You haven't practised {skill} for {days} days."
                elif data.get("attempts") and data.get("band") is not None:
                    why = f"Your diagnostic gave a first {skill} estimate (band {data['band']:g}); a full practice session will make it more accurate."
                else:
                    why = f"You haven't tried {skill} practice yet."
                route = {"writing": "/writing", "speaking": "/speaking", "reading": "/reading", "listening": "/listening"}[skill]
                out.append(
                    Candidate(
                        f"neglected_{skill}",
                        skill,
                        f"Time for some {skill} practice",
                        "Keep all four IELTS skills moving forward.",
                        why + " Balanced practice keeps your overall band estimate reliable.",
                        0.55 + (0.05 if days is None else 0),
                        route,
                        {"writing": 25, "speaking": 10, "reading": 18, "listening": 12}[skill],
                        signals={"days_since": days},
                        mission_metric=f"{skill}_{'tasks' if skill == 'writing' else 'sessions' if skill == 'speaking' else 'exercises'}",
                    )
                )
    if not ielts:
        out.append(
            Candidate(
                "lab_conversation",
                "lab",
                "Conversation practice in the English Lab",
                "A short role-play conversation with the SI conversation partner.",
                "Your goal is everyday fluency, so regular conversation practice is the most direct route.",
                0.62,
                "/lab/conversation",
                10,
                mission_metric="lab_sessions",
            )
        )

    # R9 - test date approaching
    if ielts and ctx.days_to_test is not None and ctx.days_to_test <= 30:
        out.append(
            Candidate(
                "test_soon",
                "speaking",
                "Full speaking mock test (exam conditions)",
                "All three parts with realistic timing and no hints.",
                f"Your test is in {ctx.days_to_test} days - practising under exam conditions now builds confidence and stamina.",
                0.72,
                "/speaking?mode=full",
                15,
                signals={"days_to_test": ctx.days_to_test},
                mission_metric="speaking_sessions",
            )
        )

    # Goal relevance weighting
    for c in out:
        if ielts and c.kind in ("writing", "speaking", "reading", "listening"):
            c.priority += 0.03
        if not ielts and c.kind in ("lab", "vocabulary", "grammar"):
            c.priority += 0.05
    out.sort(key=lambda c: c.priority, reverse=True)
    return out


def refresh_recommendations(db: Session, user: User, ctx: LearnerContext | None = None) -> list[Recommendation]:
    candidates = build_candidates(db, user, ctx)[:6]
    existing = {
        f"{r.rule}:{(r.action or {}).get('focus') or ''}": r
        for r in db.scalars(select(Recommendation).where(Recommendation.user_id == user.id, Recommendation.status == "active"))
    }
    now = utcnow()
    keep: list[Recommendation] = []
    for c in candidates:
        rec = existing.pop(c.key, None)
        if rec is None:
            rec = Recommendation(user_id=user.id, rule=c.rule, created_at=now)
            db.add(rec)
        rec.kind, rec.title, rec.description, rec.why = c.kind, c.title, c.description, c.why
        rec.priority = round(c.priority, 3)
        rec.signals = c.signals
        rec.action = {"route": c.route, "params": c.params, "focus": c.focus}
        rec.estimated_minutes = c.minutes
        rec.expires_at = now + timedelta(days=3)
        keep.append(rec)
    for stale in existing.values():
        stale.status = "expired"
    db.flush()
    return keep


def complete_recommendations(db: Session, user: User, kinds: set[str], focus: str | None = None) -> None:
    now = utcnow()
    for rec in db.scalars(select(Recommendation).where(Recommendation.user_id == user.id, Recommendation.status == "active")):
        if rec.kind in kinds and (focus is None or (rec.action or {}).get("focus") in (None, focus)):
            rec.status = "completed"
            rec.completed_at = now


MISSION_TASKS = {
    "vocab_reviews": ("Review {n} vocabulary words", "/vocabulary", 15, 5),
    "grammar_items": ("Get {n} grammar corrections right", "/practice/new", 15, 5),
    "mistake_repair": ("Fix one recurring mistake", "/mistakes", 20, 5),
    "speaking_sessions": ("Complete a short speaking session", "/speaking?mode=part1", 25, 8),
    "reading_exercises": ("Complete a reading exercise", "/reading", 20, 15),
    "listening_exercises": ("Complete a listening exercise", "/listening", 20, 12),
    "writing_tasks": ("Write and submit one task", "/writing", 30, 25),
    "lab_sessions": ("Do one English Lab activity", "/lab", 15, 8),
}


def get_or_create_mission(db: Session, user: User) -> DailyMission:
    today = local_today(user.profile.timezone)
    mission = db.scalar(select(DailyMission).where(DailyMission.user_id == user.id, DailyMission.day == today))
    if mission is not None:
        return mission
    ctx = build_context(db, user)
    candidates = build_candidates(db, user, ctx)
    budget = user.profile.daily_minutes or 30
    tasks: list[dict] = []
    used_metrics: set[str] = set()
    minutes_used = 0

    def add_task(metric: str, target: int, why: str, route: str | None = None, title: str | None = None, focus: str | None = None) -> None:
        nonlocal minutes_used
        if metric in used_metrics or len(tasks) >= 5:
            return
        tmpl_title, tmpl_route, xp, minutes = MISSION_TASKS[metric]
        if tasks and minutes_used + minutes > budget + 5:
            return
        used_metrics.add(metric)
        minutes_used += minutes
        tasks.append(
            {
                "id": f"t{len(tasks) + 1}",
                "metric": metric,
                "title": title or tmpl_title.format(n=target),
                "target": target,
                "progress": 0,
                "completed": False,
                "xp": xp,
                "route": route or tmpl_route,
                "minutes": minutes,
                "why": why,
                "focus": focus,
            }
        )

    due = stats.vocab_due_count(db, user.id)
    add_task(
        "vocab_reviews",
        10,
        f"{due} words are due and new words are waiting - daily reviews keep vocabulary from fading."
        if due
        else "A few minutes of vocabulary every day compounds quickly.",
    )
    for c in candidates:
        if c.rule == "diagnostic":
            continue
        if c.mission_metric and c.mission_metric in MISSION_TASKS:
            target = c.mission_target if c.mission_metric in ("grammar_items", "vocab_reviews") else 1
            title = None
            if c.mission_metric == "grammar_items" and c.focus:
                title = f"Get 5 {label_for(c.focus).lower()} corrections right"
            add_task(c.mission_metric, target, c.why, route=c.route, title=title, focus=c.focus)
    if len(tasks) < 3:
        fallback = (
            ["reading_exercises", "speaking_sessions", "listening_exercises"]
            if user.profile.goal == "ielts"
            else ["lab_sessions", "reading_exercises", "speaking_sessions"]
        )
        for metric in fallback:
            add_task(metric, 1, "Balanced practice across skills keeps every area improving.")
            if len(tasks) >= 3:
                break

    focus_label = next((c.title for c in candidates if c.rule != "diagnostic"), "balanced practice")
    weak = ctx.weak_areas[0] if ctx.weak_areas else None
    focus = weak or focus_label
    title, summary, generated_by = f"Today's focus: {focus}"[:60], "", "rules"
    try:
        plan, result = ai_client.generate_model(
            "plan_daily",
            {
                "first_name": ctx.first_name,
                "goal": ctx.goal_label,
                "learner_context": ctx.for_prompt("planner"),
                "tasks": "\n".join(f"- [{t['id']}] {t['title']} ({t['minutes']} min). Signal: {t['why']}" for t in tasks),
            },
            DailyPlanAI,
            user_id=user.id,
            mock_context={"first_name": ctx.first_name, "tasks": tasks, "focus": focus, "goal_label": ctx.goal_label},
        )
        title, summary = plan.title[:200], plan.summary
        notes = {n.task_id: n.why for n in plan.task_notes if n.why}
        for t in tasks:
            if t["id"] in notes and not ai_client.is_mock:
                t["why"] = notes[t["id"]]
        generated_by = "ai" if not ai_client.is_mock else "rules+mock"
    except AIError:
        logger.info("Planner AI unavailable; using rule-based mission summary")
        summary = f"Today's mission focuses on {focus}. It takes about {minutes_used} minutes."

    mission = DailyMission(
        user_id=user.id,
        day=local_today(user.profile.timezone),
        title=title,
        summary=summary,
        focus=str(focus)[:60],
        tasks=tasks,
        status="active",
        bonus_xp=50,
        generated_by=generated_by,
    )
    db.add(mission)
    db.flush()
    return mission
