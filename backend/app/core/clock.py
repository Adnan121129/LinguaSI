"""Time helpers.

All timestamps are timezone-aware UTC. The clock can be overridden inside a context
(`simulated_clock`) which the demo-data generator uses to replay several weeks of
realistic learner activity through the real services.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class SimulatedClock:
    def __init__(self, start: datetime) -> None:
        self.now = start if start.tzinfo else start.replace(tzinfo=UTC)

    def advance(self, **kwargs: float) -> datetime:
        self.now = self.now + timedelta(**kwargs)
        return self.now

    def set(self, value: datetime) -> None:
        self.now = value if value.tzinfo else value.replace(tzinfo=UTC)


_clock: ContextVar[SimulatedClock | None] = ContextVar("linguasi_clock", default=None)


def utcnow() -> datetime:
    simulated = _clock.get()
    if simulated is not None:
        return simulated.now
    return datetime.now(UTC)


@contextmanager
def simulated_clock(start: datetime) -> Iterator[SimulatedClock]:
    clock = SimulatedClock(start)
    token = _clock.set(clock)
    try:
        yield clock
    finally:
        _clock.reset(token)


def get_zone(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def local_now(tz_name: str | None) -> datetime:
    return utcnow().astimezone(get_zone(tz_name))


def local_today(tz_name: str | None) -> date:
    return local_now(tz_name).date()


def ensure_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def iso_week_key(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def start_of_week(day: date) -> date:
    return day - timedelta(days=day.weekday())
