"""Mock handlers for the Speaking Examiner: test plans, examiner turns and evaluation."""

from __future__ import annotations

import random
from collections import Counter

from app.ai.mock import mock_handler
from app.ai.schemas import (
    CriterionAssessment,
    CueCardAI,
    LanguageErrorItem,
    Part1FrameAI,
    SpeakingEvaluationAI,
    SpeakingPlanAI,
    SpeakingTurnAI,
)
from app.analytics.speaking_metrics import heuristic_speaking
from app.services.content import speaking_bank


@mock_handler("speaking_plan")
def plan(ctx: dict) -> SpeakingPlanAI:
    rng = random.Random(ctx.get("seed", 0))
    bank = ctx.get("bank") or speaking_bank()
    avoid = set(ctx.get("avoid_topics") or [])
    themes = set(ctx.get("themes") or [])
    frames = [f for f in bank["part1"] if f["topic"] not in avoid] or bank["part1"]
    rng.shuffle(frames)
    cards = [c for c in bank["cue_cards"] if c["topic"] not in avoid] or bank["cue_cards"]
    preferred = [c for c in cards if themes & set(c.get("tags", []))]
    card = rng.choice(preferred or cards)
    return SpeakingPlanAI(
        topic=card["topic"],
        part1=[Part1FrameAI(topic=f["topic"], questions=f["questions"][:3]) for f in frames[:2]],
        cue_card=CueCardAI(**card["cue_card"]),
        part3=card["part3_questions"][:4],
    )


@mock_handler("speaking_turn")
def next_turn(ctx: dict) -> SpeakingTurnAI:
    bank = speaking_bank()
    part = int(ctx.get("part", 1))
    words = int(ctx.get("word_count", 0))
    asked = int(ctx.get("followups_asked", 0))
    max_followups = int(ctx.get("max_followups", 1))
    turn = int(ctx.get("turn_index", 0))
    acks = bank["examiner_lines"]["acknowledgements"]
    ack = acks[turn % len(acks)]
    if part == 2 or asked >= max_followups:
        return SpeakingTurnAI(action="next", acknowledgement=ack)
    if part == 1 and words < 15:
        options = bank["followups"]["part1"]
        return SpeakingTurnAI(action="followup", acknowledgement=ack, followup_question=options[turn % len(options)])
    if part == 3 and (words < 40 or asked == 0):
        # Like a real examiner, probe at least once in the discussion, and whenever an answer is underdeveloped.
        options = bank["followups"]["part3"]
        return SpeakingTurnAI(action="followup", acknowledgement=ack, followup_question=options[turn % len(options)])
    return SpeakingTurnAI(action="next", acknowledgement=ack)


@mock_handler("speaking_evaluate")
def evaluate(ctx: dict) -> SpeakingEvaluationAI:
    agg = ctx["aggregate"]
    errors = ctx["rule_errors"]
    used = ctx.get("expressions_used", [])
    h = heuristic_speaking(agg, errors, expressions_used=len(used))
    grammar_patterns = []
    for sub, count in Counter(e.subcategory for e in errors if e.category == "grammar").most_common(3):
        grammar_patterns.append(f"{sub.replace('_', ' ').capitalize()} errors appeared {count} time{'s' if count > 1 else ''}.")
    if agg.complexity_per_100 >= 3:
        grammar_patterns.append("You regularly combine ideas with subordinate clauses (because, which, when).")
    if not grammar_patterns:
        grammar_patterns.append("Mostly simple sentence patterns were used.")

    recs = []
    if agg.fillers_per_minute > 4:
        recs.append("Filler-free minute: answer a Part 1 question for 60 seconds, replacing 'um' with a short silent pause.")
    if agg.developed_ratio < 0.6:
        recs.append("Answer + Reason + Example drill: extend every Part 1 answer to at least three sentences.")
    if agg.lexical_variety < 0.84 or len(agg.repeated_words) >= 3:
        recs.append("Paraphrase practice: describe the same topic twice using different words each time.")
    if agg.complexity_per_100 < 3:
        recs.append("Complex sentence practice: use 'although', 'which' and 'if' at least once in each Part 3 answer.")
    if not agg.pauses_measured:
        recs.append("Record your answers with the microphone enabled so LinguaSI can measure pauses accurately.")
    recs.append("Part 2 practice: talk for the full two minutes using your one-minute notes.")

    relevance = (
        "Your answers stayed on topic."
        if agg.avg_relevance >= 0.3
        else "Some answers drifted away from the question - repeat the key words of the question at the start of your answer."
    )
    development = (
        "Most answers were developed with reasons or examples."
        if agg.developed_ratio >= 0.6
        else "Several answers were short; add a reason and a personal example to each one."
    )
    fc, lr, gra = h.fluency_coherence, h.lexical_resource, h.grammatical_range_accuracy
    return SpeakingEvaluationAI(
        fluency_coherence=CriterionAssessment(band=fc[0], comment=fc[1]),
        lexical_resource=CriterionAssessment(band=lr[0], comment=lr[1]),
        grammatical_range_accuracy=CriterionAssessment(band=gra[0], comment=gra[1]),
        pronunciation=CriterionAssessment(band=h.pronunciation[0], comment=h.pronunciation[1]) if h.pronunciation else None,
        errors=[
            LanguageErrorItem(
                category=e.category, subcategory=e.subcategory, original=e.original, corrected=e.corrected, explanation=e.explanation, severity=e.severity
            )
            for e in errors[:12]
        ],
        grammar_patterns=grammar_patterns,
        strengths=h.strengths,
        weaknesses=h.weaknesses,
        recommendations=recs[:5],
        relevance_notes=relevance,
        development_notes=development,
        summary=(
            f"AI practice evaluation: estimated speaking band {h.overall:g}"
            + (" based on fluency, vocabulary and grammar (pronunciation could not be assessed from a transcript)." if not h.pronunciation else ".")
            + " This is a practice estimate, not an official IELTS score."
        ),
    )
