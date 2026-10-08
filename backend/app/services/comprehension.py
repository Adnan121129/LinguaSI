"""Shared scoring and selection helpers for Reading and Listening practice."""

from __future__ import annotations

import random

from app.agents.error_analyst import ErrorRecord
from app.analytics.scoring import check_answer

QTYPE_TO_SUBCATEGORY = {
    "true_false_not_given": "true_false_not_given",
    "yes_no_not_given": "yes_no_not_given",
    "matching_headings": "matching_headings",
    "matching_information": "matching_information",
    "multiple_choice": "multiple_choice",
    "sentence_completion": "sentence_completion",
    "summary_completion": "summary_completion",
    "short_answer": "short_answer",
    "form_completion": "form_completion",
    "note_completion": "note_completion",
}


def pick_questions(questions: list, count: int, types: list[str] | None) -> list:
    ordered = sorted(questions, key=lambda q: q.position)
    if types:
        preferred = [q for q in ordered if q.qtype in types]
        others = [q for q in ordered if q.qtype not in types]
        chosen = preferred[:count]
        if len(chosen) < count:
            chosen += others[: count - len(chosen)]
    else:
        chosen = _balanced(ordered, count)
    return sorted(chosen, key=lambda q: q.position)


def _balanced(ordered: list, count: int) -> list:
    """Take questions round-robin across types so a short set still shows variety."""
    by_type: dict[str, list] = {}
    for q in ordered:
        by_type.setdefault(q.qtype, []).append(q)
    chosen: list = []
    while len(chosen) < count and any(by_type.values()):
        for qtype in list(by_type):
            if by_type[qtype] and len(chosen) < count:
                chosen.append(by_type[qtype].pop(0))
    return chosen


def score(questions: list, answers: dict[str, str]) -> tuple[list[dict], int]:
    results, correct = [], 0
    for q in questions:
        given = (answers.get(str(q.id)) or "").strip()
        ok, note = check_answer(given, q.answer, qtype=q.qtype, accepted=q.accepted, options=q.options, word_limit=q.word_limit)
        correct += int(ok)
        results.append(
            {
                "question_id": q.id,
                "qtype": q.qtype,
                "correct": ok,
                "your_answer": given,
                "answer": q.answer,
                "explanation": q.explanation,
                "evidence": q.evidence,
                "evidence_paragraph": getattr(q, "evidence_paragraph", None),
                "note": note,
            }
        )
    return results, correct


def mistake_records(source: str, questions: list, results: list[dict], ref_type: str, ref_id: int) -> list[ErrorRecord]:
    by_id = {q.id: q for q in questions}
    records = []
    for r in results:
        if r["correct"]:
            continue
        q = by_id[r["question_id"]]
        sub = QTYPE_TO_SUBCATEGORY.get(q.qtype, "listening_detail" if source == "listening" else "multiple_choice")
        records.append(
            ErrorRecord(
                source=source,
                category="comprehension",
                subcategory=sub,
                original=f"{q.prompt[:160]} - your answer: '{r['your_answer'] or '(blank)'}'",
                corrected=f"Correct answer: {q.answer}",
                explanation=q.explanation or "",
                context=q.evidence or q.prompt,
                severity="medium",
                ref_type=ref_type,
                ref_id=ref_id,
                signature_hint=f"{source}-q{q.id}",
            )
        )
    return records


def choose_best(candidates: list, *, difficulty: int, topic: str | None, attempted: dict[int, object], types: list[str] | None) -> object | None:
    if not candidates:
        return None

    def rank(item) -> tuple:
        s = -abs(item.difficulty - difficulty) * 2.0
        if topic and item.topic == topic:
            s += 3.0
        if types and any(q.qtype in types for q in item.questions):
            s += 1.5
        if item.id in attempted:
            s -= 6.0
        return (s, random.random())

    ranked = sorted(candidates, key=rank, reverse=True)
    best = ranked[0]
    unattempted = [c for c in ranked if c.id not in attempted]
    if not unattempted:
        # everything attempted: use the least recently practised item at a suitable level
        best = sorted(candidates, key=lambda c: (abs(c.difficulty - difficulty), attempted.get(c.id)))[0]
    return best
