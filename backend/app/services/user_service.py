"""Profile/preferences management and account deletion."""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.errors import AuthError
from app.core.security import verify_password
from app.models import AIInteractionLog, LearningGoal, ListeningScript, ReadingPassage, User, WritingTask
from app.schemas.auth import ProfileUpdate
from app.services.storage import storage


def update_profile(db: Session, user: User, data: ProfileUpdate) -> User:
    profile = user.profile
    fields = data.model_dump(exclude_unset=True)
    if "name" in fields and fields["name"]:
        user.name = " ".join(fields["name"].split())
    for key in (
        "goal",
        "ielts_module",
        "self_reported_level",
        "target_band",
        "daily_minutes",
        "preferred_mode",
        "confidence",
        "preferred_topics",
        "theme",
        "timezone",
        "keep_recordings",
    ):
        if key in fields and fields[key] is not None:
            setattr(profile, key, fields[key])
    if fields.get("clear_test_date"):
        profile.test_date = None
    elif "test_date" in fields and fields["test_date"] is not None:
        profile.test_date = fields["test_date"]

    if "target_band" in fields or "test_date" in fields or fields.get("clear_test_date"):
        sync_band_goal(db, user)
    db.commit()
    db.refresh(user)
    return user


def sync_band_goal(db: Session, user: User) -> None:
    """Keep the learner's primary goal row in step with the profile target."""
    profile = user.profile
    goal = db.scalar(
        select(LearningGoal).where(
            LearningGoal.user_id == user.id,
            LearningGoal.goal_type.in_(("overall_band", "cefr")),
            LearningGoal.status == "active",
        )
    )
    if profile.goal == "ielts":
        label = f"IELTS {profile.ielts_module.replace('_', ' ').title()} band {profile.target_band:g}"
        if goal is None:
            goal = LearningGoal(user_id=user.id, goal_type="overall_band")
            db.add(goal)
        goal.goal_type = "overall_band"
        goal.target_value = profile.target_band
        goal.target_label = label
        goal.target_date = profile.test_date
    else:
        cefr_target = {4.0: "B1", 4.5: "B1", 5.0: "B1", 5.5: "B2", 6.0: "B2", 6.5: "B2", 7.0: "C1", 7.5: "C1", 8.0: "C1"}
        target = cefr_target.get(profile.target_band, "C2" if profile.target_band >= 8.5 else "B2")
        if goal is None:
            goal = LearningGoal(user_id=user.id, goal_type="cefr")
            db.add(goal)
        goal.goal_type = "cefr"
        goal.target_value = profile.target_band
        goal.target_label = f"Reach CEFR {target}"
        goal.target_date = profile.test_date


def delete_account(db: Session, user: User, password: str) -> None:
    if not verify_password(password, user.password_hash):
        raise AuthError("Password is incorrect.", code="invalid_credentials")
    # Content generated for this learner can echo what they typed (a topic, their interests), so it is
    # deleted with them rather than joining the shared content bank. AI usage logs keep their metadata
    # but lose any stored prompt previews.
    script_ids = list(db.scalars(select(ListeningScript.id).where(ListeningScript.created_for_user_id == user.id)))
    for model in (WritingTask, ReadingPassage, ListeningScript):
        db.execute(delete(model).where(model.created_for_user_id == user.id))
    db.execute(update(AIInteractionLog).where(AIInteractionLog.user_id == user.id).values(debug_payload=None))
    storage.delete_prefix(f"users/{user.id}/")
    for script_id in script_ids:
        storage.delete_prefix(f"listening/{script_id}/")
    db.delete(user)
    db.commit()
