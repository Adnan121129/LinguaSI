"""Idempotent seed-content loader.

Loads the original content bank from database/seed into PostgreSQL. Running it repeatedly
updates existing rows in place (matched by seed key / word / code), so the JSON files are the
source of truth for curated content. Learner data is never touched, and curated rows that an
admin edited in the admin panel (source == "edited") keep their edits.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.text import word_count
from app.core.database import SessionLocal
from app.models import (
    Achievement,
    GrammarExercise,
    ListeningQuestion,
    ListeningScript,
    ReadingPassage,
    ReadingQuestion,
    SpeakingTopic,
    VocabularyItem,
    WritingTask,
)
from app.services.content import load_json, load_many

logger = logging.getLogger("linguasi.seed")

CEFR_DIFFICULTY = {"A1": 1, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}


def _load_vocabulary(db: Session) -> int:
    existing = {(v.word.lower(), v.part_of_speech): v for v in db.scalars(select(VocabularyItem))}
    count = 0
    for raw in load_many("vocabulary_"):
        key = (raw["word"].lower(), raw["pos"])
        item = existing.get(key) or VocabularyItem(word=raw["word"], part_of_speech=raw["pos"])
        count += 1
        if item.source == "edited":
            continue
        item.definition = raw["definition"]
        item.example = raw["example"]
        item.synonyms = raw.get("synonyms", [])
        item.antonyms = raw.get("antonyms", [])
        item.collocations = raw.get("collocations", [])
        item.word_family = raw.get("family", {})
        item.topics = raw.get("topics", [])
        item.cefr = raw.get("cefr", "B2")
        item.difficulty = CEFR_DIFFICULTY.get(item.cefr, 3)
        item.is_academic = bool(raw.get("academic"))
        item.is_phrase = bool(raw.get("phrase")) or " " in raw["word"]
        item.source = "seed"
        if key not in existing:
            db.add(item)
    return count


def _load_grammar(db: Session) -> int:
    existing = {g.seed_key: g for g in db.scalars(select(GrammarExercise).where(GrammarExercise.seed_key.is_not(None)))}
    rows = load_json("grammar_exercises.json")
    for raw in rows:
        ex = existing.get(raw["key"]) or GrammarExercise(seed_key=raw["key"])
        if ex.source == "edited":
            continue
        ex.topic = raw["topic"]
        ex.qtype = raw["qtype"]
        ex.prompt = raw["prompt"]
        ex.options = raw.get("options")
        ex.answer = raw["answer"]
        ex.accepted = raw.get("accepted", [])
        ex.explanation = raw.get("explanation", "")
        ex.difficulty = raw.get("difficulty", 2)
        ex.cefr = raw.get("cefr", "B1")
        ex.source = "seed"
        if raw["key"] not in existing:
            db.add(ex)
    return len(rows)


def _sync_questions(owner, questions_attr: str, model, raw_questions: list[dict], fk_name: str) -> None:
    current = {q.position: q for q in getattr(owner, questions_attr)}
    for position, raw in enumerate(raw_questions, start=1):
        q = current.get(position) or model(position=position)
        q.qtype = raw["qtype"]
        q.prompt = raw["prompt"]
        q.options = raw.get("options")
        q.answer = raw["answer"]
        q.accepted = raw.get("accepted", [])
        q.explanation = raw.get("explanation", "")
        q.evidence = raw.get("evidence", "")
        q.word_limit = raw.get("word_limit")
        if hasattr(q, "evidence_paragraph"):
            q.evidence_paragraph = raw.get("evidence_paragraph")
        if position not in current:
            getattr(owner, questions_attr).append(q)


def _load_reading(db: Session) -> int:
    existing = {p.seed_key: p for p in db.scalars(select(ReadingPassage).where(ReadingPassage.seed_key.is_not(None)))}
    rows = load_json("reading_passages.json")
    for raw in rows:
        passage = existing.get(raw["key"]) or ReadingPassage(seed_key=raw["key"])
        if passage.source == "edited":
            continue
        passage.title = raw["title"]
        passage.topic = raw["topic"]
        passage.module = raw.get("module", "academic")
        passage.difficulty = raw.get("difficulty", 3)
        passage.paragraphs = raw["paragraphs"]
        passage.headings = raw.get("headings", [])
        passage.word_count = sum(word_count(p["text"]) for p in raw["paragraphs"])
        passage.estimated_minutes = max(8, round(passage.word_count / 40) + len(raw["questions"]))
        passage.source = "seed"
        passage.quality = {"validated": True, "method": "curated"}
        if raw["key"] not in existing:
            db.add(passage)
        _sync_questions(passage, "questions", ReadingQuestion, raw["questions"], "passage_id")
    return len(rows)


def _load_listening(db: Session) -> int:
    existing = {s.seed_key: s for s in db.scalars(select(ListeningScript).where(ListeningScript.seed_key.is_not(None)))}
    rows = load_json("listening_scripts.json")
    for raw in rows:
        script = existing.get(raw["key"]) or ListeningScript(seed_key=raw["key"])
        if script.source == "edited":
            continue
        script.title = raw["title"]
        script.topic = raw["topic"]
        script.scenario = raw.get("scenario", "conversation")
        script.difficulty = raw.get("difficulty", 3)
        script.speakers = raw["speakers"]
        script.segments = raw["segments"]
        script.word_count = sum(word_count(s["text"]) for s in raw["segments"])
        script.speech_rate = raw.get("speech_rate", 1.0)
        script.accent = raw.get("accent", "british")
        script.context = raw.get("context", "")
        script.source = "seed"
        script.quality = {"validated": True, "method": "curated"}
        if raw["key"] not in existing:
            db.add(script)
        _sync_questions(script, "questions", ListeningQuestion, raw["questions"], "script_id")
    return len(rows)


def _load_writing(db: Session) -> int:
    existing = {t.seed_key: t for t in db.scalars(select(WritingTask).where(WritingTask.seed_key.is_not(None)))}
    rows = load_json("writing_tasks.json")
    for raw in rows:
        task = existing.get(raw["key"]) or WritingTask(seed_key=raw["key"])
        if task.source == "edited":
            continue
        for field in (
            "task_type",
            "module",
            "category",
            "topic",
            "title",
            "prompt",
            "instructions",
            "visual",
            "key_points",
            "min_words",
            "time_limit_minutes",
            "difficulty",
        ):
            setattr(task, field, raw.get(field))
        task.source = "seed"
        if raw["key"] not in existing:
            db.add(task)
    return len(rows)


def _load_speaking(db: Session) -> int:
    existing = {t.seed_key: t for t in db.scalars(select(SpeakingTopic))}
    bank = load_json("speaking_topics.json")
    count = 0
    for raw in bank["part1"]:
        topic = existing.get(raw["key"]) or SpeakingTopic(seed_key=raw["key"])
        topic.kind = "part1"
        topic.topic = raw["topic"]
        topic.tags = raw.get("tags", [])
        topic.questions = raw["questions"]
        if raw["key"] not in existing:
            db.add(topic)
        count += 1
    for raw in bank["cue_cards"]:
        topic = existing.get(raw["key"]) or SpeakingTopic(seed_key=raw["key"])
        topic.kind = "cue_card"
        topic.topic = raw["topic"]
        topic.tags = raw.get("tags", [])
        topic.cue_card = raw["cue_card"]
        topic.part3_questions = raw["part3_questions"]
        if raw["key"] not in existing:
            db.add(topic)
        count += 1
    return count


def _load_achievements(db: Session) -> int:
    existing = {a.code: a for a in db.scalars(select(Achievement))}
    rows = load_json("achievements.json")
    for raw in rows:
        ach = existing.get(raw["code"]) or Achievement(code=raw["code"])
        for field in ("name", "description", "icon", "category", "tier", "xp_reward", "criteria", "sort_order"):
            setattr(ach, field, raw[field])
        if raw["code"] not in existing:
            db.add(ach)
    return len(rows)


def load_all(db: Session) -> dict[str, int]:
    counts = {
        "vocabulary": _load_vocabulary(db),
        "grammar_exercises": _load_grammar(db),
        "reading_passages": _load_reading(db),
        "listening_scripts": _load_listening(db),
        "writing_tasks": _load_writing(db),
        "speaking_topics": _load_speaking(db),
        "achievements": _load_achievements(db),
    }
    db.commit()
    logger.info("Seed content loaded: %s", counts)
    return counts


def content_is_empty(db: Session) -> bool:
    return (db.scalar(select(func.count(VocabularyItem.id))) or 0) == 0


def ensure_seed_content() -> dict[str, int] | None:
    """Load seed content if the content tables are empty (used on application start-up)."""
    db = SessionLocal()
    try:
        if content_is_empty(db):
            return load_all(db)
        return None
    finally:
        db.close()
