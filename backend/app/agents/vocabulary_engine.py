"""SI Vocabulary Engine.

* chooses which words a learner should meet next (level fit + relevance to weak areas + topics)
* reacts to signals from other agents (e.g. collocation errors in Writing -> academic collocations)
* builds varied exercises whose type depends on the word's learning state
* schedules reviews with a simple spaced-repetition algorithm
* detects when learners actually USE their words in writing and speaking

Exercises are generated deterministically from an id (`<user_vocab_id>.<type>.<seed>`), so the
server can regenerate an exercise to verify an answer without storing exercise state and
without sending answers to the client.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.error_analyst import Signal
from app.analytics import srs
from app.analytics.grammar_rules import detect_errors
from app.analytics.scoring import normalize_completion
from app.analytics.text import stem, words
from app.core.clock import local_today, utcnow
from app.core.errors import NotFoundError, ValidationAppError
from app.core.levels import CEFR_LEVELS
from app.models import User, UserVocabulary, VocabularyItem, VocabularyReview
from app.repositories.stats import local_day_start_utc

EXERCISE_TYPES = (
    "multiple_choice",
    "synonym",
    "antonym",
    "fill_blank",
    "sentence_completion",
    "word_formation",
    "collocation",
    "contextual",
    "speaking_usage",
    "writing_usage",
)
STATE_EXERCISES = {
    "new": ("multiple_choice", "contextual"),
    "learning": ("synonym", "sentence_completion", "antonym", "contextual"),
    "familiar": ("fill_blank", "collocation", "sentence_completion"),
    "strong": ("word_formation", "writing_usage", "fill_blank"),
    "mastered": ("speaking_usage", "collocation", "writing_usage"),
}
SIGNAL_CRITERIA = {
    "collocation_weakness": {"phrase": True, "topics": {"collocation", "argument", "academic", "evidence", "cause_effect"}, "reason": "writing_error"},
    "lexical_range": {"phrase": None, "topics": {"academic", "argument", "evidence", "cause_effect", "comparison"}, "reason": "weak_area"},
    "academic_style": {"phrase": None, "topics": {"academic", "argument"}, "reason": "weak_area"},
    "data_description": {"phrase": None, "topics": {"data_description"}, "reason": "weak_area"},
}


@dataclass
class Exercise:
    id: str
    user_vocab_id: int
    item_id: int
    word: str
    state: str
    type: str
    prompt: str
    options: list[str] | None
    answer: str
    accepted: list[str]
    hint: str | None
    input: str  # choice | text | sentence

    def public(self) -> dict:
        return {
            "id": self.id,
            "user_vocab_id": self.user_vocab_id,
            "item_id": self.item_id,
            "word": self.word if self.type not in ("multiple_choice", "fill_blank", "sentence_completion") else None,
            "state": self.state,
            "type": self.type,
            "prompt": self.prompt,
            "options": self.options,
            "hint": self.hint,
            "input": self.input,
        }


def _level_window(cefr: str | None) -> list[str]:
    idx = CEFR_LEVELS.index(cefr) if cefr in CEFR_LEVELS else 2
    return list(CEFR_LEVELS[max(0, idx - 1) : min(len(CEFR_LEVELS), idx + 2)])


def _owned_ids(db: Session, user_id: int) -> set[int]:
    return set(db.scalars(select(UserVocabulary.item_id).where(UserVocabulary.user_id == user_id)))


def add_words(
    db: Session,
    user: User,
    items: list[VocabularyItem],
    *,
    reason: str,
    detail: str | None,
    priority: float = 1.0,
) -> list[VocabularyItem]:
    owned = _owned_ids(db, user.id)
    added = []
    now = utcnow()
    for item in items:
        if item.id in owned:
            continue
        db.add(
            UserVocabulary(
                user_id=user.id,
                item_id=item.id,
                state="new",
                due_at=now,
                priority=priority,
                reason=reason,
                reason_detail=(detail or "")[:300] or None,
                added_at=now,
            )
        )
        owned.add(item.id)
        added.append(item)
    db.flush()
    return added


def choose_items(
    db: Session,
    user: User,
    *,
    limit: int,
    topics: set[str] | None = None,
    phrase: bool | None = None,
    academic: bool | None = None,
    cefr: str | None = None,
    seed: int = 0,
) -> list[VocabularyItem]:
    owned = _owned_ids(db, user.id)
    candidates = [i for i in db.scalars(select(VocabularyItem).where(VocabularyItem.is_active.is_(True))) if i.id not in owned]
    if phrase is not None:
        candidates = [i for i in candidates if i.is_phrase == phrase] or candidates
    if academic is not None:
        candidates = [i for i in candidates if i.is_academic == academic] or candidates
    window = set(_level_window(cefr or user.profile.estimated_cefr))
    preferred = set(user.profile.preferred_topics or [])

    def score(item: VocabularyItem) -> float:
        s = 0.0
        item_topics = set(item.topics or [])
        if topics:
            s += 3.0 * len(item_topics & topics)
        if preferred:
            s += 1.0 * len(item_topics & preferred)
        if item.cefr in window:
            s += 2.0
        if user.profile.goal == "ielts" and item.is_academic:
            s += 1.0
        if user.profile.goal == "general" and ("daily_life" in item_topics or "feelings" in item_topics):
            s += 1.0
        return s

    rng = random.Random(seed or user.id)
    rng.shuffle(candidates)
    candidates.sort(key=score, reverse=True)
    return candidates[:limit]


def ensure_starter_vocabulary(db: Session, user: User, count: int = 12) -> list[VocabularyItem]:
    if _owned_ids(db, user.id):
        return []
    topics = set(user.profile.preferred_topics or []) | ({"academic", "argument"} if user.profile.goal == "ielts" else {"daily_life"})
    items = choose_items(db, user, limit=count, topics=topics)
    return add_words(db, user, items, reason="level", detail="Selected for your level and goals", priority=1.0)


def react_to_signals(db: Session, user: User, signals: list[Signal], *, topic: str | None = None) -> list[str]:
    """Cross-skill reaction: add words that target weaknesses detected elsewhere."""
    actions: list[str] = []
    for signal in signals:
        criteria = SIGNAL_CRITERIA.get(signal.key)
        if not criteria:
            continue
        topics = set(criteria["topics"]) | ({topic} if topic else set())
        items = choose_items(db, user, limit=8 if signal.key == "collocation_weakness" else 6, topics=topics, phrase=criteria["phrase"])
        added = add_words(db, user, items, reason=criteria["reason"], detail=f"{signal.title}: {signal.detail}", priority=2.0)
        if added:
            kind = "collocations" if signal.key == "collocation_weakness" else "words"
            actions.append(f"Added {len(added)} {kind} to your vocabulary queue to address {signal.title.lower()}.")
    return actions


def add_misspelled_words(db: Session, user: User, corrected_words: list[str]) -> list[str]:
    if not corrected_words:
        return []
    wanted = {w.lower() for w in corrected_words}
    items = [i for i in db.scalars(select(VocabularyItem).where(func.lower(VocabularyItem.word).in_(wanted)))]
    added = add_words(db, user, items, reason="writing_error", detail="You misspelled this word in your writing", priority=2.0)
    return [i.word for i in added]


def _forms(item: VocabularyItem) -> set[str]:
    base = item.word.lower()
    forms = {base}
    for value in (item.word_family or {}).values():
        if isinstance(value, str) and " " not in value:
            forms.add(value.lower())
    if " " not in base:
        for suffix in ("s", "es", "ed", "d", "ing", "ly"):
            forms.add(base + suffix)
        if base.endswith("e"):
            forms.add(base[:-1] + "ing")
        if base.endswith("y"):
            forms.update({base[:-1] + "ies", base[:-1] + "ied"})
    return forms


def contains_item(text: str, item: VocabularyItem) -> bool:
    lowered = (text or "").lower()
    if item.is_phrase or " " in item.word:
        core = re.sub(r"\b(a|an|the|of|to|in|on)\b", " ", item.word.lower())
        key_words = [w for w in core.split() if len(w) > 2]
        if item.word.lower() in lowered:
            return True
        tokens = set(words(lowered))
        stems = {stem(t) for t in tokens}
        return bool(key_words) and all(stem(w) in stems or w in tokens for w in key_words)
    tokens = set(words(lowered))
    return bool(tokens & _forms(item))


def record_usage(db: Session, user: User, text: str, source: str) -> list[str]:
    """Credit words the learner used in writing/speaking; usage counts as a successful retrieval."""
    if not text:
        return []
    now = utcnow()
    used = []
    rows = db.execute(
        select(UserVocabulary, VocabularyItem).join(VocabularyItem, VocabularyItem.id == UserVocabulary.item_id).where(UserVocabulary.user_id == user.id)
    ).all()
    for uv, item in rows:
        if not contains_item(text, item):
            continue
        if source == "writing":
            uv.used_in_writing += 1
        else:
            uv.used_in_speaking += 1
        if uv.state in ("new", "learning") and (uv.last_reviewed_at is None or now - uv.last_reviewed_at > timedelta(hours=12)):
            before = uv.state
            after = srs.schedule(uv, 4, now)
            db.add(
                VocabularyReview(
                    user_id=user.id,
                    item_id=item.id,
                    user_vocab_id=uv.id,
                    exercise_type=f"{source}_usage",
                    correct=True,
                    answer="(used in context)",
                    quality=4,
                    state_before=before,
                    state_after=after,
                )
            )
        used.append(item.word)
    return used


# --- Exercise generation -----------------------------------------------------------------------


def _blank(sentence: str, item: VocabularyItem) -> tuple[str, str] | None:
    """Blank the target word (any of its forms) in a sentence; return (blanked, removed_form)."""
    candidates = sorted(_forms(item), key=len, reverse=True)
    for form in candidates:
        m = re.search(rf"\b{re.escape(form)}\b", sentence, re.IGNORECASE)
        if m:
            return sentence[: m.start()] + "_____" + sentence[m.end() :], m.group(0)
    return None


def _distractors(pool: list[VocabularyItem], item: VocabularyItem, rng: random.Random, attr: str = "word", n: int = 3) -> list[str]:
    exclude = {item.word.lower(), *[s.lower() for s in item.synonyms or []]}
    same_pos = [p for p in pool if p.id != item.id and p.part_of_speech == item.part_of_speech and p.word.lower() not in exclude]
    others = [p for p in pool if p.id != item.id and p.word.lower() not in exclude]
    choices = same_pos if len(same_pos) >= n else others
    rng.shuffle(choices)
    values: list[str] = []
    for p in choices:
        value = getattr(p, attr)
        if value and value not in values:
            values.append(value)
        if len(values) == n:
            break
    return values


def build_exercise(uv: UserVocabulary, item: VocabularyItem, pool: list[VocabularyItem], ex_type: str, seed: int) -> Exercise:
    rng = random.Random(f"{uv.id}-{ex_type}-{seed}")
    ex_id = f"{uv.id}.{ex_type}.{seed}"
    base = dict(id=ex_id, user_vocab_id=uv.id, item_id=item.id, word=item.word, state=uv.state, type=ex_type, accepted=[], hint=None)

    def choice(prompt: str, answer: str, distract: list[str], hint: str | None = None) -> Exercise:
        options = distract[:3] + [answer]
        rng.shuffle(options)
        return Exercise(**{**base, "hint": hint}, prompt=prompt, options=options, answer=answer, input="choice")

    if ex_type == "synonym" and item.synonyms:
        answer = rng.choice(item.synonyms)
        distract = [rng.choice(p.synonyms) for p in pool if p.id != item.id and p.synonyms and p.part_of_speech == item.part_of_speech]
        distract = [d for d in dict.fromkeys(distract) if d not in item.synonyms]
        rng.shuffle(distract)
        return choice(f"Which word or phrase is closest in meaning to '{item.word}'?", answer, distract)
    if ex_type == "antonym" and item.antonyms:
        answer = rng.choice(item.antonyms)
        distract = [s for s in item.synonyms if s not in item.antonyms][:2]
        extra = [rng.choice(p.antonyms) for p in pool if p.id != item.id and p.antonyms]
        rng.shuffle(extra)
        distract = list(dict.fromkeys(distract + extra))
        return choice(f"Which word or phrase is opposite in meaning to '{item.word}'?", answer, distract)
    if ex_type in ("fill_blank", "sentence_completion"):
        sentences = [item.example] + list(item.extra_examples or [])
        for sentence in sentences:
            blanked = _blank(sentence, item)
            if blanked:
                text, removed = blanked
                if ex_type == "fill_blank":
                    return Exercise(
                        **{**base, "hint": f"Starts with '{removed[0]}' ({len(removed)} letters). Meaning: {item.definition}"},
                        prompt=f"Complete the sentence: {text}",
                        options=None,
                        answer=removed,
                        input="text",
                    )
                return choice(f"Choose the best word to complete the sentence: {text}", removed, _distractors(pool, item, rng), hint=None)
        ex_type = base["type"] = "multiple_choice"
    if ex_type == "word_formation":
        family = {
            k: v
            for k, v in (item.word_family or {}).items()
            if isinstance(v, str) and v.lower() != item.word.lower() and k in ("noun", "verb", "adjective", "adverb")
        }
        if family:
            form, answer = rng.choice(sorted(family.items()))
            return Exercise(
                **{**base, "hint": f"Think about the {form} suffixes such as -tion, -ment, -al, -ly."},
                prompt=f"Write the {form} form of '{item.word}'.",
                options=None,
                answer=answer,
                input="text",
            )
        ex_type = base["type"] = "contextual"
    if ex_type == "collocation" and item.collocations:
        coll = rng.choice(item.collocations)
        blanked = _blank(coll, item)
        if blanked and blanked[0].strip() != "_____":
            text, removed = blanked
            return choice(
                f"Complete the natural collocation: '{text}'",
                removed,
                _distractors(pool, item, rng),
                hint=f"Collocation means words that naturally go together. Meaning: {item.definition}",
            )
        ex_type = base["type"] = "contextual"
    if ex_type in ("speaking_usage", "writing_usage"):
        topic = (item.topics or ["your life"])[0].replace("_", " ")
        mode = "say aloud and then type" if ex_type == "speaking_usage" else "write"
        return Exercise(
            **{**base, "hint": f"Example: {item.example}"},
            prompt=f"Use '{item.word}' in a sentence of your own ({mode}) about {topic}.",
            options=None,
            answer=item.word,
            input="sentence",
        )
    if ex_type == "contextual":
        others = _distractors(pool, item, rng, attr="definition")
        return choice(f"In the sentence \"{item.example}\", what does '{item.word}' mean?", item.definition, others)
    # multiple_choice (default): definition -> word
    base["type"] = "multiple_choice"
    return choice(f'Which word or phrase means: "{item.definition}"?', item.word, _distractors(pool, item, rng))


def exercise_type_for(uv: UserVocabulary, item: VocabularyItem, review_count: int) -> str:
    options = list(STATE_EXERCISES.get(uv.state, ("multiple_choice",)))
    if not item.antonyms and "antonym" in options:
        options.remove("antonym")
    if not item.synonyms and "synonym" in options:
        options.remove("synonym")
    return options[(uv.id + review_count) % len(options)]


def build_session(db: Session, user: User, *, limit: int | None = None) -> dict:
    """Today's review session: due words first, then a few new words."""
    ensure_starter_vocabulary(db, user)
    minutes = user.profile.daily_minutes or 30
    new_limit = 5 if minutes <= 15 else 8 if minutes <= 30 else 12
    total_limit = limit or (12 if minutes <= 15 else 20)
    now = utcnow()
    due = db.execute(
        select(UserVocabulary, VocabularyItem)
        .join(VocabularyItem, VocabularyItem.id == UserVocabulary.item_id)
        .where(UserVocabulary.user_id == user.id, UserVocabulary.state != "new", UserVocabulary.due_at <= now)
        .order_by(UserVocabulary.priority.desc(), UserVocabulary.due_at.asc())
        .limit(total_limit)
    ).all()
    new_slots = max(0, min(new_limit, total_limit - len(due)))
    _top_up_new_words(db, user, new_slots, new_limit)
    fresh = db.execute(
        select(UserVocabulary, VocabularyItem)
        .join(VocabularyItem, VocabularyItem.id == UserVocabulary.item_id)
        .where(UserVocabulary.user_id == user.id, UserVocabulary.state == "new")
        .order_by(UserVocabulary.priority.desc(), UserVocabulary.added_at.asc())
        .limit(new_slots)
    ).all()
    pool = list(db.scalars(select(VocabularyItem)))
    seed = int(now.timestamp() // 3600)
    exercises = []
    for uv, item in list(due) + list(fresh):
        review_count = (uv.correct_count or 0) + (uv.incorrect_count or 0)
        ex = build_exercise(uv, item, pool, exercise_type_for(uv, item, review_count), seed)
        exercises.append(ex.public() | {"reason": uv.reason, "reason_detail": uv.reason_detail, "is_new": uv.state == "new"})
    return {"exercises": exercises, "due_count": len(due), "new_count": len(fresh)}


def _top_up_new_words(db: Session, user: User, slots: int, daily_limit: int) -> None:
    """Keep introducing new words: when the learner has run out of unseen words, add a few each day."""
    if slots <= 0:
        return
    waiting = db.scalar(select(func.count(UserVocabulary.id)).where(UserVocabulary.user_id == user.id, UserVocabulary.state == "new")) or 0
    if waiting >= slots:
        return
    day_start = local_day_start_utc(local_today(user.profile.timezone), user.profile.timezone)
    added_today = db.scalar(select(func.count(UserVocabulary.id)).where(UserVocabulary.user_id == user.id, UserVocabulary.added_at >= day_start)) or 0
    allowance = min(slots - waiting, daily_limit - added_today)
    if allowance <= 0:
        return
    topics = set(user.profile.preferred_topics or []) | ({"academic", "argument"} if user.profile.goal == "ielts" else {"daily_life"})
    items = choose_items(db, user, limit=allowance, topics=topics, seed=int(day_start.timestamp()))
    add_words(db, user, items, reason="level", detail="New word for your level and interests", priority=1.0)


def parse_exercise_id(exercise_id: str) -> tuple[int, str, int]:
    try:
        uv_part, ex_type, seed_part = exercise_id.split(".")
        if ex_type not in EXERCISE_TYPES:
            raise ValueError
        return int(uv_part), ex_type, int(seed_part)
    except ValueError as exc:
        raise ValidationAppError("Invalid exercise id.") from exc


def check_review(db: Session, user: User, exercise_id: str, answer: str, response_ms: int | None, *, hinted: bool = False) -> dict:
    uv_id, ex_type, seed = parse_exercise_id(exercise_id)
    uv = db.get(UserVocabulary, uv_id)
    if uv is None or uv.user_id != user.id:
        raise NotFoundError("This vocabulary item is not in your word list.")
    item = db.get(VocabularyItem, uv.item_id)
    pool = list(db.scalars(select(VocabularyItem)))
    ex = build_exercise(uv, item, pool, ex_type, seed)
    feedback = None
    if ex.input == "sentence":
        sentence = (answer or "").strip()
        contains = contains_item(sentence, item)
        long_enough = len(words(sentence)) >= 6
        issues = detect_errors(sentence, mode="writing", academic=False) if sentence else []
        correct = contains and long_enough and not issues
        if not contains:
            feedback = f"Your sentence needs to include '{item.word}' (or one of its forms)."
        elif not long_enough:
            feedback = "Write a full sentence of at least six words so the meaning is clear."
        elif issues:
            feedback = "Nearly there - check: " + "; ".join(f"'{e.original}' → '{e.corrected}'" for e in issues[:2])
        else:
            feedback = "Great - natural and correct use."
    elif ex.input == "text":
        correct = normalize_completion(answer) in {normalize_completion(ex.answer), *map(normalize_completion, ex.accepted)}
    else:
        correct = (answer or "").strip().lower() == ex.answer.strip().lower()

    now = utcnow()
    before = uv.state
    quality = srs.quality_from(correct, response_ms, hinted=hinted)
    after = srs.schedule(uv, quality, now)
    if response_ms:
        uv.avg_response_ms = int(response_ms if uv.avg_response_ms is None else 0.7 * uv.avg_response_ms + 0.3 * response_ms)
    db.add(
        VocabularyReview(
            user_id=user.id,
            item_id=item.id,
            user_vocab_id=uv.id,
            exercise_type=ex_type,
            correct=correct,
            answer=(answer or "")[:300],
            response_ms=response_ms,
            quality=quality,
            state_before=before,
            state_after=after,
        )
    )
    return {
        "correct": correct,
        "correct_answer": ex.answer,
        "feedback": feedback,
        "state_before": before,
        "state_after": after,
        "next_review_at": uv.due_at,
        "item": item,
        "user_vocab": uv,
    }


def mark_known(db: Session, user: User, user_vocab_id: int) -> UserVocabulary:
    uv = db.get(UserVocabulary, user_vocab_id)
    if uv is None or uv.user_id != user.id:
        raise NotFoundError("This vocabulary item is not in your word list.")
    before = uv.state
    srs.mark_known(uv, utcnow())
    db.add(
        VocabularyReview(
            user_id=user.id,
            item_id=uv.item_id,
            user_vocab_id=uv.id,
            exercise_type="marked_known",
            correct=True,
            answer="(already known)",
            quality=5,
            state_before=before,
            state_after=uv.state,
        )
    )
    return uv


def retention_stats(db: Session, user_id: int, last_n: int = 20) -> dict:
    rows = db.scalars(
        select(VocabularyReview.correct)
        .where(VocabularyReview.user_id == user_id, VocabularyReview.exercise_type.in_(EXERCISE_TYPES))
        .order_by(VocabularyReview.created_at.desc())
        .limit(last_n)
    ).all()
    if not rows:
        return {"reviews": 0, "accuracy": None}
    return {"reviews": len(rows), "accuracy": round(sum(1 for r in rows if r) / len(rows) * 100, 1)}
