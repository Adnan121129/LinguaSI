"""Demo data: replays four weeks of a realistic learner's activity through the real services.

Nothing is inserted directly. The generator runs the same service functions the API uses inside a
simulated clock, so every record (evaluations, mistakes, vocabulary reviews, XP, streaks, missions,
recommendations, progress snapshots, SI activity feed) is produced by SI Core exactly as it would be
for a real learner. The learner's original essays and answers improve over time, so the history
shows genuine progress.
"""

from __future__ import annotations

import json
import logging
import random
import re
from dataclasses import dataclass, field
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import speaking_examiner, vocabulary_engine
from app.core.clock import SimulatedClock, simulated_clock, utcnow
from app.core.errors import AppError
from app.models import ListeningQuestion, ReadingQuestion, User, UserVocabulary, VocabularyItem, WritingTask
from app.schemas.onboarding import OnboardingRequest, SpeakingSample
from app.services import (
    auth_service,
    dashboard_service,
    diagnostic_service,
    lab_service,
    listening_service,
    practice_service,
    reading_service,
    speaking_service,
    tutor_service,
    vocabulary_service,
    writing_service,
)
from app.services.content import pronunciation_sets, seed_dir

logger = logging.getLogger("linguasi.demo")

DEMO_DAYS = 28
SKIPPED_DAYS = {4, 9, 15}  # realistic gaps; the final streak is 12 days
SPEAKING_DAYS = {2: "part1", 8: "part1", 14: "full", 21: "part1", 26: "full"}
READING_DAYS = {5, 11, 18, 23, 27}
LISTENING_DAYS = {7, 13, 20, 24}
PRACTICE_DAYS = {3, 10, 16, 22, 27}
PRONUNCIATION_DAYS = {13, 20}
DAILY_QUIZ_DAYS = {16, 24}
TUTOR_DAY = 3
CONVERSATION_DAY = 11


@lru_cache(maxsize=1)
def demo_content() -> dict:
    path = Path(seed_dir()).parent / "demo" / "demo_learner.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@dataclass
class DemoReport:
    email: str
    password: str
    days: int
    actions: dict[str, int] = field(default_factory=dict)

    def count(self, key: str) -> None:
        self.actions[key] = self.actions.get(key, 0) + 1


def create_demo_learner(db: Session, *, reset: bool = False, days: int = DEMO_DAYS) -> DemoReport:
    data = demo_content()
    learner = data["learner"]
    existing = db.scalar(select(User).where(User.email == learner["email"]))
    if existing is not None:
        if not reset:
            raise AppError("The demo learner already exists. Run with --reset to recreate it.", code="demo_exists")
        db.delete(existing)
        db.commit()

    rng = random.Random(2026)
    report = DemoReport(email=learner["email"], password=learner["password"], days=days)
    # Every simulated day stays safely in the past: the last day starts three hours before now.
    start = utcnow() - timedelta(days=days - 1, hours=3)
    with simulated_clock(start) as clock:
        user = _register_and_onboard(db, clock, data, days)
        report.count("diagnostic")
        for day in range(1, days):
            clock.set(start + timedelta(days=day, minutes=rng.randint(0, 40)))
            if day in SKIPPED_DAYS:
                continue
            _run_day(db, user, clock, data, day, days, rng, report)
    db.expire_all()
    logger.info("Demo learner created: %s", report.actions)
    return report


def _register_and_onboard(db: Session, clock: SimulatedClock, data: dict, days: int) -> User:
    learner = data["learner"]
    user, _ = auth_service.register(db, email=learner["email"], password=learner["password"], name=learner["name"], user_agent="demo-generator")
    user.is_demo = True
    db.commit()
    diagnostic_service.complete_onboarding(
        db,
        user,
        OnboardingRequest(
            goal="ielts",
            ielts_module="academic",
            self_reported_level="intermediate",
            target_band=learner["target_band"],
            test_date=(utcnow() + timedelta(days=days + 60)).date(),
            daily_minutes=learner["daily_minutes"],
            preferred_mode="balanced",
            confidence=3,
            preferred_topics=learner["preferred_topics"],
            timezone=learner["timezone"],
        ),
    )
    clock.advance(minutes=2)
    attempt, _ = diagnostic_service.start(db, user)
    items = attempt.items
    answers: dict[str, str] = {}
    rng = random.Random(7)
    for section, accuracy in (("vocabulary", 0.7), ("grammar", 0.6)):
        for item in items[section]:
            answers[item["id"]] = _pick(item.get("options"), item["answer"], rng.random() < accuracy, rng)
    for section, accuracy in (("reading", 0.6), ("listening", 0.55)):
        for q in items[section]["questions"]:
            answers[q["id"]] = _pick(q.get("options"), q["answer"], rng.random() < accuracy, rng)
    clock.advance(minutes=25)
    speaking = [SpeakingSample(id=items["speaking"][0]["id"], transcript=data["diagnostic_speaking"], duration_seconds=28, source="browser")]
    diagnostic_service.submit(db, user, attempt.id, answers, data["diagnostic_writing"], speaking)
    dashboard_service.dashboard(db, user)
    return user


def _run_day(db: Session, user: User, clock: SimulatedClock, data: dict, day: int, days: int, rng: random.Random, report: DemoReport) -> None:
    progress = day / max(1, days - 1)  # 0 -> 1 across the period
    dashboard_service.dashboard(db, user)  # opening the app creates today's mission and recommendations
    clock.advance(minutes=1)
    _vocabulary_session(db, user, clock, 0.6 + 0.32 * progress, rng)
    report.count("vocabulary_sessions")

    essay = next((e for e in data["essays"] if e["day"] == day), None)
    if essay:
        _writing(db, user, clock, essay)
        report.count("writing_evaluations")
    if day in SPEAKING_DAYS:
        _speaking(db, user, clock, SPEAKING_DAYS[day], data["speaking_answers"], 0.15 + 0.7 * progress, rng)
        report.count("speaking_sessions")
    if day in READING_DAYS:
        _reading(db, user, clock, 0.5 + 0.26 * progress, rng)
        report.count("reading_attempts")
    if day in LISTENING_DAYS:
        _listening(db, user, clock, 0.45 + 0.28 * progress, rng)
        report.count("listening_attempts")
    if day in PRACTICE_DAYS and _practice(db, user, clock, 0.5 + 0.45 * progress, rng):
        report.count("practice_sets")
    if day == TUTOR_DAY:
        _tutor_chat(db, user, clock, data["tutor_messages"])
        report.count("tutor_chats")
    if day == CONVERSATION_DAY:
        _conversation(db, user, clock, data["conversation"])
        report.count("lab_conversations")
    if day in PRONUNCIATION_DAYS:
        _pronunciation(db, user, clock, rng)
        report.count("pronunciation_checks")
    if day in DAILY_QUIZ_DAYS:
        _daily_quiz(db, user, clock)
        report.count("daily_quizzes")


def _pick(options: list[str] | None, answer: str, correct: bool, rng: random.Random) -> str:
    if correct:
        return answer
    wrong = [o for o in (options or []) if o.strip().lower() != answer.strip().lower()]
    return rng.choice(wrong) if wrong else "not sure"


def _vocabulary_session(db: Session, user: User, clock: SimulatedClock, accuracy: float, rng: random.Random) -> None:
    session = vocabulary_service.today(db, user)
    started = utcnow()
    pool = list(db.scalars(select(VocabularyItem)))
    for public in session["exercises"][:12]:
        uv_id, ex_type, seed = vocabulary_engine.parse_exercise_id(public["id"])
        uv = db.get(UserVocabulary, uv_id)
        item = db.get(VocabularyItem, uv.item_id)
        exercise = vocabulary_engine.build_exercise(uv, item, pool, ex_type, seed)
        correct = rng.random() < accuracy
        if exercise.input == "sentence":
            answer = item.example if correct else item.word
        elif exercise.input == "choice":
            answer = _pick(exercise.options, exercise.answer, correct, rng)
        else:
            answer = exercise.answer if correct else "no idea"
        clock.advance(seconds=rng.randint(10, 30))
        vocabulary_service.review(db, user, public["id"], answer, response_ms=rng.randint(2500, 9000), hinted=False)
    clock.advance(seconds=20)
    vocabulary_service.complete_session(db, user, started, int((utcnow() - started).total_seconds()))


def _writing(db: Session, user: User, clock: SimulatedClock, essay: dict) -> None:
    task = db.scalar(select(WritingTask).where(WritingTask.seed_key == essay["task"]))
    if task is None:
        logger.warning("Demo writing task %s is missing; run the seed command first", essay["task"])
        return
    sub = writing_service.start_submission(db, user, task.id, essay.get("mode", "exam"))
    text = essay["text"]
    draft = text[: len(text) // 2]
    clock.advance(minutes=12)
    writing_service.autosave(db, user, sub.id, draft, 12 * 60)
    if essay.get("hint_question"):
        writing_service.hint(db, user, sub.id, essay["hint_question"], draft)
    minutes = 36 if task.task_type == "task2" else 19
    clock.advance(minutes=minutes - 12)
    writing_service.evaluate(db, user, sub.id, text, minutes * 60)
    clock.advance(minutes=3)


def _roughen(text: str, quality: float, rng: random.Random) -> str:
    """Earlier answers are shorter and more hesitant; later ones are complete and fluent."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    keep = max(2, round(len(sentences) * (0.5 + 0.5 * quality)))
    sentences = sentences[:keep]
    if quality < 0.7:
        fillers = ["Um,", "Uh,", "Well, um,", "You know,", "Er,"]
        sentences = [f"{rng.choice(fillers)} {s[0].lower()}{s[1:]}" if rng.random() < 0.65 - 0.6 * quality else s for s in sentences]
    return " ".join(sentences)


def _match(question: str, bank: list[dict]) -> str | None:
    lowered = question.lower()
    for entry in bank:
        if any(k in lowered for k in entry["keywords"]):
            return entry["text"]
    return None


def _speaking_answer(turn: dict, answers: dict, quality: float, rng: random.Random) -> str:
    part, kind, question = turn["part"], turn["kind"], turn["question"]
    if part == 2 and kind == "cue_card":
        title = (turn.get("cue_card") or {}).get("title", question)
        text = _match(title, answers["part2"]) or answers["part2"][0]["text"]
    elif part == 2:
        text = "Yes, I think so. It's something I really care about, so I'd like to keep doing it in the future."
    elif part == 1:
        text = (
            _match(question, answers["part1"])
            or "I'd say it depends, but generally yes. I enjoy it because it helps me relax and spend time with people I care about."
        )
        if kind == "followup":
            text = text.split(". ")[-1]
    else:
        text = _match(question, answers["part3"]) or answers["generic"]
    return _roughen(text, quality, rng)


def _speaking(db: Session, user: User, clock: SimulatedClock, mode: str, answers: dict, quality: float, rng: random.Random) -> None:
    session = speaking_service.start(db, user, mode)
    turn = session.current_question or speaking_examiner.first_turn(session)
    for _ in range(25):
        if not turn:
            break
        text = _speaking_answer(turn, answers, quality, rng)
        word_total = len(text.split())
        wpm = 92 + 45 * quality
        duration = round(word_total / wpm * 60, 1)
        pauses = {
            "measured": True,
            "count": max(1, round(word_total / 14 * (1.6 - quality))),
            "long_count": max(0, round(3 * (1 - quality))),
            "total_silence_seconds": round(duration * (0.18 - 0.1 * quality), 1),
        }
        clock.advance(seconds=duration + rng.randint(5, 12))
        _, turn = speaking_service.respond(
            db,
            user,
            session.id,
            client_transcript=text,
            transcript_source="browser",
            duration_seconds=duration,
            pauses_json=json.dumps(pauses),
            audio_bytes=None,
            audio_mime=None,
        )
    speaking_service.finish(db, user, session.id)
    clock.advance(minutes=2)


def _reading(db: Session, user: User, clock: SimulatedClock, accuracy: float, rng: random.Random) -> None:
    attempt, _ = reading_service.generate(db, user, difficulty=None, topic=None, question_count=8, time_limit=20, module=None, question_types=None)
    questions = db.scalars(select(ReadingQuestion).where(ReadingQuestion.id.in_(attempt.question_ids))).all()
    answers = {str(q.id): _pick(q.options, q.answer, rng.random() < accuracy, rng) for q in questions}
    clock.advance(minutes=17)
    reading_service.submit(db, user, attempt.id, answers, 17 * 60)


def _listening(db: Session, user: User, clock: SimulatedClock, accuracy: float, rng: random.Random) -> None:
    attempt, _ = listening_service.generate(
        db, user, difficulty=None, topic=None, scenario=None, question_count=8, time_limit=15, accent=None, question_types=None
    )
    questions = db.scalars(select(ListeningQuestion).where(ListeningQuestion.id.in_(attempt.question_ids))).all()
    answers = {str(q.id): _pick(q.options, q.answer, rng.random() < accuracy, rng) for q in questions}
    clock.advance(minutes=12)
    listening_service.submit(db, user, attempt.id, answers, 12 * 60, replays=1 if accuracy < 0.7 else 0)


def _practice(db: Session, user: User, clock: SimulatedClock, accuracy: float, rng: random.Random) -> bool:
    try:
        practice = practice_service.revision_session(db, user)
    except AppError:
        return False
    answers = {item["id"]: item["answer"] if rng.random() < accuracy else "not sure" for item in practice.items}
    clock.advance(minutes=6)
    practice_service.submit_practice(db, user, practice.id, answers, 6 * 60)
    return True


def _tutor_chat(db: Session, user: User, clock: SimulatedClock, messages: list[str]) -> None:
    conv = tutor_service.create_conversation(db, user, "tutor", None, None)
    for message in messages:
        clock.advance(minutes=1)
        tutor_service.send_message(db, user, conv.id, message)


def _conversation(db: Session, user: User, clock: SimulatedClock, conversation: dict) -> None:
    conv = tutor_service.create_conversation(db, user, "conversation", conversation["scenario"], None)
    for message in conversation["messages"]:
        clock.advance(minutes=1)
        tutor_service.send_message(db, user, conv.id, message)


def _pronunciation(db: Session, user: User, clock: SimulatedClock, rng: random.Random) -> None:
    sentence_set = rng.choice(pronunciation_sets())
    for sentence in sentence_set["sentences"]:
        words = sentence.rstrip(".!?").split()
        if len(words) > 4 and rng.random() < 0.5:
            words[rng.randrange(1, len(words))] = "the"  # one misrecognised word, as speech recognition often reports
        clock.advance(seconds=20)
        lab_service.check_pronunciation(db, user, sentence, " ".join(words), duration_seconds=4.5)


def _daily_quiz(db: Session, user: User, clock: SimulatedClock) -> None:
    quiz = lab_service.daily_quiz(db, user)
    clock.advance(minutes=2)
    practice_service.submit_practice(db, user, quiz.id, {item["id"]: item["answer"] for item in quiz.items}, 120)
