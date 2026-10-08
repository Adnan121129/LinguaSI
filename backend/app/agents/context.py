"""LearnerContext - SI Core's application-level memory.

Agents never receive the learner's whole history. Instead SI Core assembles a compact,
purpose-specific summary (target, skills, recurring mistakes, focus vocabulary, recent sessions,
streak...) so prompts stay small (cost control) while every agent shares the same picture of
the learner.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import get_zone, local_today
from app.core.levels import level_for_xp
from app.models import LearnerSkillProfile, Recommendation, StudySession, User, UserVocabulary, VocabularyItem
from app.repositories import stats
from app.services.gamification import display_streak

SKILL_ORDER = ("reading", "listening", "writing", "speaking", "vocabulary", "grammar")


@dataclass
class LearnerContext:
    user_id: int
    first_name: str
    goal: str
    module: str
    target_band: float
    test_date: str | None
    days_to_test: int | None
    self_reported_level: str
    cefr: str | None
    estimated_band: float | None
    band_confidence: float
    skills: dict[str, dict] = field(default_factory=dict)
    weak_areas: list[str] = field(default_factory=list)
    strong_areas: list[str] = field(default_factory=list)
    recurring: list[dict] = field(default_factory=list)
    focus_words: list[str] = field(default_factory=list)
    target_expressions: list[str] = field(default_factory=list)
    preferred_topics: list[str] = field(default_factory=list)
    streak: int = 0
    level: int = 1
    recent_activity: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def recurring_subcategories(self) -> list[str]:
        return [r["subcategory"] for r in self.recurring]

    @property
    def goal_label(self) -> str:
        if self.goal == "ielts":
            return f"IELTS {self.module.replace('_', ' ').title()} band {self.target_band:g}"
        return "fluent, confident English"

    def for_prompt(self, purpose: str = "general") -> str:
        lines = [f"Name: {self.first_name}", f"Goal: {self.goal_label}"]
        if self.days_to_test is not None:
            lines.append(f"Test date in {self.days_to_test} days")
        level = self.cefr or self.self_reported_level
        band = f", AI estimated band {self.estimated_band:g}" if self.estimated_band is not None else ""
        lines.append(f"Current level: {level}{band}")
        relevant = {
            "writing": ("writing", "grammar", "vocabulary"),
            "speaking": ("speaking", "grammar", "vocabulary"),
            "reading": ("reading", "vocabulary"),
            "listening": ("listening", "vocabulary"),
        }.get(purpose, SKILL_ORDER)
        skill_bits = []
        for skill in relevant:
            data = self.skills.get(skill)
            if not data or not data.get("attempts"):
                continue
            band_part = f" band {data['band']:g}" if data.get("band") is not None else ""
            skill_bits.append(f"{skill} {data['score']:.0f}/100{band_part} ({data['trend']})")
        if skill_bits:
            lines.append("Skills: " + "; ".join(skill_bits))
        if self.weak_areas:
            lines.append("Weak areas: " + ", ".join(self.weak_areas[:4]))
        if self.recurring and purpose in ("writing", "speaking", "tutor", "planner", "general", "practice"):
            items = []
            for r in self.recurring[:5]:
                example = f" e.g. '{r['example']['original']}' -> '{r['example']['corrected']}'" if r.get("example") else ""
                items.append(f"{r['label']} x{r['count']}{example}")
            lines.append("Recurring mistakes (last 30 days): " + "; ".join(items))
        if self.target_expressions and purpose in ("speaking", "reading", "listening", "writing", "planner"):
            lines.append("Target expressions being learned: " + ", ".join(self.target_expressions[:8]))
        if self.focus_words and purpose in ("tutor", "planner", "vocabulary"):
            lines.append("Words currently being learned: " + ", ".join(self.focus_words[:8]))
        if self.preferred_topics:
            lines.append("Preferred topics: " + ", ".join(self.preferred_topics[:6]))
        if purpose in ("planner", "tutor", "general"):
            lines.append(f"Streak: {self.streak} days, level {self.level}")
            if self.recent_activity:
                lines.append("Recent sessions: " + "; ".join(self.recent_activity[:5]))
        return "\n".join(lines)

    def as_mock(self) -> dict:
        data = asdict(self)
        data["recurring_subcategories"] = self.recurring_subcategories
        data["recurring"] = [r["label"] for r in self.recurring]
        data["goal_label"] = self.goal_label
        return data


def build_context(db: Session, user: User) -> LearnerContext:
    profile = user.profile
    skills = {
        sp.skill: {"score": sp.score, "band": sp.band, "trend": sp.trend, "difficulty": sp.difficulty, "attempts": sp.attempts}
        for sp in db.scalars(select(LearnerSkillProfile).where(LearnerSkillProfile.user_id == user.id))
    }
    learning = db.execute(
        select(VocabularyItem.word, VocabularyItem.is_phrase)
        .join(UserVocabulary, UserVocabulary.item_id == VocabularyItem.id)
        .where(UserVocabulary.user_id == user.id, UserVocabulary.state.in_(("new", "learning", "familiar")))
        .order_by(UserVocabulary.priority.desc(), UserVocabulary.added_at.desc())
        .limit(24)
    ).all()
    focus_words = [w for w, is_phrase in learning if not is_phrase][:10]
    expressions = [w for w, is_phrase in learning if is_phrase][:8]
    sessions = db.scalars(select(StudySession).where(StudySession.user_id == user.id).order_by(StudySession.started_at.desc()).limit(5)).all()
    today = local_today(profile.timezone)
    recent = []
    for s in sessions:
        days = (today - s.started_at.astimezone(get_zone(profile.timezone)).date()).days
        when = "today" if days <= 0 else "yesterday" if days == 1 else f"{days} days ago"
        score = f" ({s.score:.0f}%)" if s.score is not None else ""
        recent.append(f"{s.title or s.activity}{score} {when}")
    recs = db.scalars(
        select(Recommendation.title)
        .where(Recommendation.user_id == user.id, Recommendation.status == "active")
        .order_by(Recommendation.priority.desc())
        .limit(3)
    ).all()
    return LearnerContext(
        user_id=user.id,
        first_name=(user.name or "").split(" ")[0] or "there",
        goal=profile.goal,
        module=profile.ielts_module,
        target_band=profile.target_band,
        test_date=profile.test_date.isoformat() if profile.test_date else None,
        days_to_test=(profile.test_date - today).days if profile.test_date and profile.test_date >= today else None,
        self_reported_level=profile.self_reported_level,
        cefr=profile.estimated_cefr,
        estimated_band=profile.estimated_band,
        band_confidence=profile.band_confidence or 0.0,
        skills=skills,
        weak_areas=[w.get("label", "") for w in (profile.weak_areas or [])],
        strong_areas=[s.get("label", "") for s in (profile.strong_areas or [])],
        recurring=stats.recurring_mistakes(db, user.id),
        focus_words=focus_words,
        target_expressions=expressions,
        preferred_topics=list(profile.preferred_topics or []),
        streak=display_streak(db, user)["current"],
        level=level_for_xp(stats.total_xp(db, user.id)),
        recent_activity=recent,
        recommendations=list(recs),
    )
