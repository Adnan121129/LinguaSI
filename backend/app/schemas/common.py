"""Schema building blocks shared across the API."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size if self.page_size else 0


class Message(BaseModel):
    message: str


class XPGain(BaseModel):
    amount: int
    reason: str
    description: str = ""


class AchievementUnlocked(BaseModel):
    code: str
    name: str
    description: str
    icon: str
    tier: str
    xp_reward: int


class ActivityOutcome(BaseModel):
    """What SI Core did after an activity: rewards, streak, missions and cross-skill actions."""

    xp_gained: int = 0
    xp_breakdown: list[XPGain] = []
    total_xp: int = 0
    level: int = 1
    level_title: str = ""
    leveled_up: bool = False
    streak: int = 0
    streak_extended: bool = False
    achievements: list[AchievementUnlocked] = []
    mission_progress: list[str] = []
    mission_completed: bool = False
    si_actions: list[str] = []
