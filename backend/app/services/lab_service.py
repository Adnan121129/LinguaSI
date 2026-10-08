"""English Lab: general English practice (daily English, pronunciation, sentence building, conversation)."""

from __future__ import annotations

import difflib
import random
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents import si_core
from app.analytics.text import words
from app.core.clock import local_today
from app.core.errors import ValidationAppError
from app.models import GrammarExercise, PracticeSet, User, VocabularyItem
from app.services.content import conversation_scenarios, daily_english, pronunciation_sets


def overview(db: Session, user: User) -> dict:
    topics = db.scalar(select(func.count(func.distinct(GrammarExercise.topic)))) or 0
    phrase = daily_phrase(user)
    return {
        "goal": user.profile.goal,
        "sections": [
            {
                "key": "grammar",
                "title": "Grammar",
                "description": "Focused drills on the rules that matter most for you.",
                "route": "/lab/grammar",
                "count": topics,
            },
            {"key": "vocabulary", "title": "Vocabulary", "description": "Adaptive spaced-repetition reviews.", "route": "/vocabulary"},
            {
                "key": "pronunciation",
                "title": "Pronunciation",
                "description": "Listen, repeat and check how clearly you were understood.",
                "route": "/lab/pronunciation",
                "count": len(pronunciation_sets()),
            },
            {
                "key": "conversation",
                "title": "Conversation",
                "description": "Role-play real situations with an SI partner.",
                "route": "/lab/conversation",
                "count": len(conversation_scenarios()),
            },
            {
                "key": "sentence_building",
                "title": "Sentence building",
                "description": "Rebuild natural sentences from scrambled words.",
                "route": "/lab/sentence-building",
            },
            {"key": "reading", "title": "Reading", "description": "Practice passages with explanations.", "route": "/reading"},
            {"key": "listening", "title": "Listening", "description": "Conversations and talks at your level.", "route": "/listening"},
            {
                "key": "writing",
                "title": "Writing",
                "description": "Emails, reviews and short opinion texts with feedback.",
                "route": "/writing?module=general_english",
            },
            {"key": "daily", "title": "Daily English", "description": "One useful everyday expression a day.", "route": "/lab/daily"},
        ],
        "daily_phrase": phrase,
    }


def daily_phrase(user: User) -> dict:
    phrases = daily_english()
    today = local_today(user.profile.timezone)
    rng = random.Random(f"{today.isoformat()}")
    return phrases[rng.randrange(len(phrases))] | {"day": today.isoformat()}


def daily_quiz(db: Session, user: User) -> PracticeSet:
    phrases = daily_english()
    today_phrase = daily_phrase(user)
    rng = random.Random(f"{user.id}-{today_phrase['day']}")
    pool = [p for p in phrases if p["phrase"] != today_phrase["phrase"]]
    rng.shuffle(pool)
    targets = [today_phrase] + pool[:2]
    items = []
    for idx, target in enumerate(targets, start=1):
        distract = [p["meaning"] for p in phrases if p["phrase"] != target["phrase"]]
        rng.shuffle(distract)
        options = distract[:3] + [target["meaning"]]
        rng.shuffle(options)
        items.append(
            {
                "id": f"i{idx}",
                "qtype": "multiple_choice",
                "prompt": f"What does '{target['phrase']}' mean? Example: {target['example']}",
                "options": options,
                "answer": target["meaning"],
                "accepted": [],
                "explanation": f"'{target['phrase']}' means {target['meaning']}.",
                "source": "lab",
            }
        )
    practice = PracticeSet(
        user_id=user.id,
        kind="daily_english",
        title=f"Daily English: {today_phrase['phrase']}",
        description="Learn one everyday expression and review two more.",
        why="A short daily habit builds natural, idiomatic English.",
        focus="daily_english",
        items=items,
        total=len(items),
        estimated_minutes=2,
        source="seed",
    )
    db.add(practice)
    db.commit()
    return practice


def sentence_building(db: Session, user: User, count: int = 5) -> PracticeSet:
    items_pool = list(db.scalars(select(VocabularyItem).where(VocabularyItem.is_active.is_(True))))
    rng = random.Random()
    rng.shuffle(items_pool)
    items = []
    for vocab in items_pool:
        sentence = vocab.example.strip()
        tokens = sentence.rstrip(".!?").split()
        if not 6 <= len(tokens) <= 13 or any(ch in sentence for ch in ';:"()'):
            continue
        # Lower-case the opening word so its capital letter doesn't give the answer away.
        display = tokens[:]
        is_acronym = len(display[0]) > 1 and display[0].isupper()  # keep "UK", "IELTS"; lower-case "A", "The"
        if display[0] != "I" and not is_acronym:
            display[0] = display[0][0].lower() + display[0][1:]
        shuffled = display[:]
        while shuffled == display:
            rng.shuffle(shuffled)
        items.append(
            {
                "id": f"i{len(items) + 1}",
                "qtype": "sentence_order",
                "prompt": "Put the words in order: " + " / ".join(shuffled),
                "options": None,
                "answer": " ".join(tokens),
                "accepted": [],
                "explanation": f"Natural order: {sentence}",
                "source": "lab",
            }
        )
        if len(items) >= count:
            break
    if not items:
        raise ValidationAppError("No sentences are available yet. Run the seed command to load the vocabulary bank.")
    practice = PracticeSet(
        user_id=user.id,
        kind="sentence_building",
        title="Sentence building",
        description="Rebuild each sentence in natural English word order.",
        why="Putting words in order trains grammar and natural phrasing together.",
        focus="word_order",
        items=items,
        total=len(items),
        estimated_minutes=4,
        source="seed",
    )
    db.add(practice)
    db.commit()
    return practice


def check_pronunciation(db: Session, user: User, sentence: str, transcript: str, duration_seconds: float | None) -> dict:
    target = words(sentence)
    heard = words(transcript)
    matcher = difflib.SequenceMatcher(a=target, b=heard, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    missing, extra = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            missing.extend(target[i1:i2])
        if tag in ("replace", "insert"):
            extra.extend(heard[j1:j2])
    score = round(matched / len(target) * 100, 1) if target else 0.0
    outcome = si_core.process_activity(
        db,
        user,
        si_core.ActivityEvent(
            activity="lab",
            title="Pronunciation practice",
            duration_seconds=int(duration_seconds or 20),
            score=score,
            xp=[(5, "lab_activity", "Pronunciation practice")],
            mission_metrics={"lab_sessions": 1},
            completes_kinds={"lab"},
            meta={"sentence": sentence[:200], "match": score},
        ),
    )
    tip = (
        "Clearly understood - great!"
        if score >= 90
        else "Mostly clear. Practise the highlighted words slowly, then at normal speed."
        if score >= 70
        else "Several words were not recognised. Listen again, then repeat in short chunks."
    )
    return {
        "match": score,
        "matched_words": matched,
        "total_words": len(target),
        "missing_words": missing[:12],
        "unexpected_words": extra[:12],
        "tip": tip,
        "note": "This checks how many words speech recognition understood as you intended. It is a practice signal, not a phonetic pronunciation score.",
        "outcome": outcome,
    }


def normalise_sentence(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().rstrip(".!?")).lower()
