"""Database engine, session factory and FastAPI dependency."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TypeVar

from sqlalchemy import Select, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _make_engine(url: str):
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        echo=settings.db_echo,
        future=True,
    )


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


T = TypeVar("T")


def insert_or_existing(db: Session, row: T, existing: Select[tuple[T]]) -> T:
    """Insert `row`, or return the row a concurrent request inserted first with the same unique key.

    Rows created on first use (today's mission, a skill profile, a week's challenges...) can be created
    by two requests for the same learner at once, e.g. the web and mobile apps opening the dashboard
    together. The insert runs in a savepoint, so losing that race leaves the request's transaction
    usable. Callers can tell which happened with `result is row`.
    """
    db.flush()  # anything already pending is not part of this race
    try:
        with db.begin_nested():
            db.add(row)
        return row
    except IntegrityError:
        found = db.scalar(existing)
        if found is None:
            raise
        return found
