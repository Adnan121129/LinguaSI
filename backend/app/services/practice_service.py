"""Practice sets (grammar drills, mistake repair challenges, revision sessions) and the mistake tracker."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents import error_analyst, practice_generator, si_core
from app.agents.progress_analyst import SkillResult
from app.analytics.scoring import normalize_completion
from app.core.clock import iso_week_key, start_of_week, utcnow
from app.core.errors import NotFoundError, ValidationAppError
from app.core.taxonomy import CATEGORY_LABELS, SUBCATEGORIES, label_for
from app.models import GrammarExercise, Mistake, PracticeSet, User
from app.repositories import stats
from app.schemas.practice import MistakeDetail, MistakeOut, PracticeItemOut, PracticeResultItem, PracticeSetOut
from app.services.content import kb_entry

VOCAB_TOPICS = {"collocation", "word_formation", "daily_english"}
WRITING_TOPICS = {"argument_building", "linking_words", "academic_style"}
LAB_KINDS = {"daily_english", "sentence_building"}


# --- Mistakes ---------------------------------------------------------------------------------


def mistake_out(m: Mistake) -> MistakeOut:
    return MistakeOut(
        id=m.id,
        source=m.source,
        category=m.category,
        category_label=CATEGORY_LABELS.get(m.category, m.category.title()),
        subcategory=m.subcategory,
        label=label_for(m.subcategory),
        original=m.original,
        corrected=m.corrected,
        explanation=m.explanation,
        context=m.context,
        severity=m.severity,
        occurrences=m.occurrences,
        repeated=m.repeated,
        status=m.status,
        practice_attempts=m.practice_attempts,
        practice_correct=m.practice_correct,
        revisit_at=m.revisit_at,
        mastered_at=m.mastered_at,
        first_seen_at=m.first_seen_at,
        last_seen_at=m.last_seen_at,
    )


def list_mistakes(
    db: Session, user: User, *, status: str | None, category: str | None, source: str | None, subcategory: str | None, page: int, page_size: int
) -> tuple[list[MistakeOut], int]:
    q = select(Mistake).where(Mistake.user_id == user.id)
    now = utcnow()
    if status == "due":
        q = q.where(Mistake.revisit_at.is_not(None), Mistake.revisit_at <= now, Mistake.status != "mastered")
    elif status == "recurring":
        q = q.where(Mistake.status != "mastered", (Mistake.occurrences > 1) | (Mistake.repeated.is_(True)))
    elif status:
        q = q.where(Mistake.status == status)
        if status == "unresolved":
            q = q.where((Mistake.revisit_at.is_(None)) | (Mistake.revisit_at <= now))
    if category:
        q = q.where(Mistake.category == category)
    if source:
        q = q.where(Mistake.source == source)
    if subcategory:
        q = q.where(Mistake.subcategory == subcategory)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(Mistake.last_seen_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return [mistake_out(m) for m in rows], total


def mistake_summary(db: Session, user: User) -> dict:
    counts = stats.mistake_counts(db, user.id)
    rows = db.execute(
        select(Mistake.source, Mistake.category, Mistake.subcategory, func.sum(Mistake.occurrences))
        .where(Mistake.user_id == user.id)
        .group_by(Mistake.source, Mistake.category, Mistake.subcategory)
    ).all()
    by_category: Counter = Counter()
    by_sub: Counter = Counter()
    speaking_sub: Counter = Counter()
    for source, category, sub, n in rows:
        by_category[category] += int(n)
        by_sub[(category, sub)] += int(n)
        if source == "speaking":
            speaking_sub[sub] += int(n)

    def most_common(cats: tuple[str, ...]) -> dict | None:
        candidates = [(sub, n) for (cat, sub), n in by_sub.items() if cat in cats]
        if not candidates:
            return None
        sub, n = max(candidates, key=lambda x: x[1])
        return {"subcategory": sub, "label": label_for(sub), "count": n}

    speaking_top = None
    if speaking_sub:
        sub, n = speaking_sub.most_common(1)[0]
        speaking_top = {"subcategory": sub, "label": label_for(sub), "count": n}

    # weekly trend and heatmap (last 8 weeks, by category, using first_seen_at)
    now = utcnow()
    week_starts = [start_of_week((now - timedelta(weeks=i)).date()) for i in range(7, -1, -1)]
    since = week_starts[0]
    recent = db.execute(
        select(Mistake.category, Mistake.first_seen_at, Mistake.occurrences).where(
            Mistake.user_id == user.id, Mistake.first_seen_at >= stats.local_day_start_utc(since, "UTC")
        )
    ).all()
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: {iso_week_key(w): 0 for w in week_starts})
    weekly_totals = {iso_week_key(w): 0 for w in week_starts}
    for category, first_seen, _occ in recent:
        key = iso_week_key(first_seen.date())
        if key in weekly_totals:
            matrix[category][key] += 1
            weekly_totals[key] += 1
    categories = sorted(matrix, key=lambda c: -sum(matrix[c].values()))
    due = (
        db.scalar(
            select(func.count(Mistake.id)).where(
                Mistake.user_id == user.id, Mistake.revisit_at.is_not(None), Mistake.revisit_at <= now, Mistake.status != "mastered"
            )
        )
        or 0
    )
    return {
        "totals": counts,
        "most_common": {
            "grammar": most_common(("grammar",)),
            "vocabulary": most_common(("vocabulary", "spelling")),
            "speaking": speaking_top,
            "comprehension": most_common(("comprehension",)),
        },
        "recurring": stats.recurring_mistakes(db, user.id, days=60, limit=8),
        "by_category": [{"category": c, "label": CATEGORY_LABELS.get(c, c.title()), "count": n} for c, n in by_category.most_common()],
        "weekly_trend": [{"week": w, "count": n} for w, n in weekly_totals.items()],
        "heatmap": {
            "weeks": list(weekly_totals),
            "rows": [{"category": c, "label": CATEGORY_LABELS.get(c, c.title()), "values": list(matrix[c].values())} for c in categories],
        },
        "due_for_revision": due,
    }


def get_mistake(db: Session, user: User, mistake_id: int) -> Mistake:
    m = db.get(Mistake, mistake_id)
    if m is None or m.user_id != user.id:
        raise NotFoundError("Mistake not found.")
    return m


def mistake_detail(db: Session, user: User, mistake_id: int) -> MistakeDetail:
    m = get_mistake(db, user, mistake_id)
    related = db.scalars(
        select(Mistake)
        .where(Mistake.user_id == user.id, Mistake.subcategory == m.subcategory, Mistake.id != m.id)
        .order_by(Mistake.last_seen_at.desc())
        .limit(5)
    ).all()
    return MistakeDetail(**mistake_out(m).model_dump(), guide=kb_entry(m.subcategory), related=[mistake_out(r) for r in related])


def update_mistake_status(db: Session, user: User, mistake_id: int, status: str | None, revisit_in_days: int | None) -> Mistake:
    m = get_mistake(db, user, mistake_id)
    now = utcnow()
    if status == "mastered":
        m.status = "mastered"
        m.mastered_at = now
        m.revisit_at = None
    elif status == "unresolved":
        m.status = "unresolved"
        m.mastered_at = None
    if revisit_in_days:
        m.revisit_at = now + timedelta(days=revisit_in_days)
    db.commit()
    return m


# --- Practice sets ------------------------------------------------------------------------------


def practice_out(ps: PracticeSet) -> PracticeSetOut:
    results = [PracticeResultItem(**r) for r in (ps.results or [])] if ps.status == "completed" else []
    return PracticeSetOut(
        id=ps.id,
        kind=ps.kind,
        title=ps.title,
        description=ps.description,
        why=ps.why,
        focus=ps.focus,
        status=ps.status,
        items=[
            PracticeItemOut(
                id=i["id"], qtype=i["qtype"], prompt=i["prompt"], options=i.get("options"), source=i.get("source", "bank"), mistake_id=i.get("mistake_id")
            )
            for i in ps.items
        ],
        total=ps.total,
        score=ps.score,
        accuracy=ps.accuracy,
        estimated_minutes=ps.estimated_minutes,
        results=results,
        created_at=ps.created_at,
        completed_at=ps.completed_at,
    )


def create_practice(
    db: Session, user: User, *, focus: str, kind: str, mistake_ids: list[int] | None, item_count: int, title: str | None = None, why: str | None = None
) -> PracticeSet:
    if focus not in SUBCATEGORIES and practice_generator.resolve_topic(db, focus) is None and not kb_entry(focus):
        raise ValidationAppError(f"Unknown practice focus '{focus}'.")
    if why is None:
        rec = next((r for r in stats.recurring_mistakes(db, user.id, days=30, limit=10) if r["subcategory"] == focus), None)
        if rec:
            why = f"You made {rec['count']} {rec['label'].lower()} mistakes in the last 30 days, so this set mixes your own sentences with targeted practice."
        else:
            why = f"Focused practice on {label_for(focus).lower()} to strengthen accuracy."
    ps = practice_generator.build_practice_set(db, user, focus=focus, kind=kind, mistake_ids=mistake_ids, item_count=item_count, title=title, why=why)
    if not ps.items:
        raise ValidationAppError("SI couldn't build practice items for this focus yet. Try another topic.")
    db.commit()
    return ps


def practice_for_mistake(db: Session, user: User, mistake_id: int) -> PracticeSet:
    m = get_mistake(db, user, mistake_id)
    return create_practice(
        db,
        user,
        focus=m.subcategory,
        kind="mistake_repair",
        mistake_ids=[m.id],
        item_count=6,
        title=f"Mini practice: {label_for(m.subcategory)}",
        why=f"Built around your mistake '{m.original}' and the same rule in new sentences.",
    )


def revision_session(db: Session, user: User) -> PracticeSet:
    now = utcnow()
    due = db.scalars(
        select(Mistake)
        .where(Mistake.user_id == user.id, Mistake.revisit_at.is_not(None), Mistake.revisit_at <= now, Mistake.status != "mastered")
        .order_by(Mistake.revisit_at.asc())
        .limit(5)
    ).all()
    candidates = [
        r
        for r in stats.recurring_mistakes(db, user.id, days=60, limit=8, min_count=1)
        if practice_generator.resolve_topic(db, r["subcategory"]) or kb_entry(r["subcategory"])
    ]
    if due:
        focus = Counter(m.subcategory for m in due).most_common(1)[0][0]
        ids = [m.id for m in due if m.subcategory == focus]
        why = f"{len(due)} mistake{'s' if len(due) > 1 else ''} you saved for later {'are' if len(due) > 1 else 'is'} due for revision."
    elif candidates:
        focus = candidates[0]["subcategory"]
        ids = None
        why = f"Your most frequent recent mistake type is {candidates[0]['label'].lower()} ({candidates[0]['count']} times)."
    else:
        raise ValidationAppError("You have no mistakes to revise yet - complete a writing or speaking task first.", code="nothing_to_revise")
    return create_practice(
        db, user, focus=focus, kind="revision", mistake_ids=ids, item_count=7, title=f"5-minute {label_for(focus)} Repair Challenge", why=why
    )


def get_practice(db: Session, user: User, practice_id: int) -> PracticeSet:
    ps = db.get(PracticeSet, practice_id)
    if ps is None or ps.user_id != user.id:
        raise NotFoundError("Practice set not found.")
    return ps


def _norm_sentence(value: str) -> str:
    text = normalize_completion(value)
    return re.sub(r"[.!?]+$", "", text).strip()


def check_item(item: dict, answer: str) -> bool:
    if not (answer or "").strip():
        return False
    qtype = item["qtype"]
    if qtype == "multiple_choice":
        return answer.strip().lower() == item["answer"].strip().lower() or any(answer.strip().lower() == a.strip().lower() for a in item.get("accepted", []))
    if qtype == "gap_fill":
        return normalize_completion(answer) in {normalize_completion(item["answer"]), *map(normalize_completion, item.get("accepted", []))}
    user = _norm_sentence(answer)
    if user in {_norm_sentence(item["answer"]), *map(_norm_sentence, item.get("accepted", []))}:
        return True
    if item.get("partial_ok") and item.get("accepted"):
        fragment = _norm_sentence(item["accepted"][0])
        return bool(fragment) and fragment in user
    return False


def submit_practice(db: Session, user: User, practice_id: int, answers: dict[str, str], duration_seconds: int):
    ps = get_practice(db, user, practice_id)
    if ps.status == "completed":
        raise ValidationAppError("This practice set has already been submitted.", code="already_submitted")
    results, correct = [], 0
    per_mistake: dict[int, bool] = {}
    for item in ps.items:
        given = answers.get(item["id"], "")
        ok = check_item(item, given)
        correct += int(ok)
        results.append({"id": item["id"], "correct": ok, "your_answer": given, "answer": item["answer"], "explanation": item.get("explanation", "")})
        if item.get("mistake_id"):
            per_mistake[item["mistake_id"]] = per_mistake.get(item["mistake_id"], True) and ok
    accuracy = round(correct / len(ps.items) * 100, 1) if ps.items else 0.0
    ps.results = results
    ps.score = correct
    ps.accuracy = accuracy
    ps.status = "completed"
    ps.completed_at = utcnow()

    mastered: list[int] = []
    for mid in ps.mistake_ids or []:
        m = db.get(Mistake, mid)
        if m is None or m.user_id != user.id:
            continue
        ok = per_mistake.get(mid, accuracy >= 80)
        if error_analyst.record_practice_result(m, ok):
            mastered.append(m.id)

    topic = practice_generator.resolve_topic(db, ps.focus or "") or ps.focus or ""
    skill = "vocabulary" if topic in VOCAB_TOPICS else "writing" if topic in WRITING_TOPICS else "grammar"
    repair = ps.kind in ("mistake_repair", "revision")
    xp = [(10 + 2 * correct, "practice_set", f"Practice: {ps.title}")]
    if mastered:
        xp.append((10 * len(mastered), "mistake_mastered", f"Mastered {len(mastered)} mistake{'s' if len(mastered) > 1 else ''}"))
    # "grammar_items" counts correct practice answers for missions; the daily phrase quiz is vocabulary-only.
    metrics = {"grammar_items": correct} if ps.kind != "daily_english" else {}
    if repair:
        metrics |= {"mistake_repair": 1, "mistakes_fixed": 1}
    completes = {"grammar", "mistakes"} if skill == "grammar" else {skill}
    if ps.kind in LAB_KINDS:
        metrics["lab_sessions"] = 1
        completes.add("lab")
    outcome = si_core.process_activity(
        db,
        user,
        si_core.ActivityEvent(
            activity="lab" if ps.kind in LAB_KINDS else "grammar" if skill == "grammar" else skill,
            title=ps.title,
            duration_seconds=duration_seconds,
            ref_type="practice_set",
            ref_id=ps.id,
            score=accuracy,
            skill_results=[SkillResult(skill, accuracy, None, None)] if skill != "writing" else [],
            xp=xp,
            mission_metrics=metrics,
            completes_kinds=completes,
            focus=ps.focus,
            meta={"kind": ps.kind, "focus": ps.focus, "accuracy": accuracy},
        ),
    )
    if mastered:
        outcome.si_actions.append(f"{len(mastered)} mistake{'s' if len(mastered) > 1 else ''} marked as mastered after two correct practices.")
    return ps, mastered, outcome


def list_practice(db: Session, user: User, page: int, page_size: int) -> tuple[list[PracticeSet], int]:
    q = select(PracticeSet).where(PracticeSet.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(PracticeSet.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return list(rows), total


def practice_topics(db: Session) -> list[dict]:
    rows = db.execute(select(GrammarExercise.topic, func.count(GrammarExercise.id)).group_by(GrammarExercise.topic)).all()
    out = []
    for topic, n in sorted(rows):
        label = "Argument building" if topic == "argument_building" else "Academic style" if topic == "academic_style" else label_for(topic)
        out.append({"focus": topic, "label": label, "items": n, "guide": (kb_entry(topic) or {}).get("rule")})
    return out
