"""SI Speaking Examiner - realistic IELTS-style speaking tests.

The examiner behaves like a real one during the test: neutral acknowledgements, no scores, no
corrections, occasional follow-up questions in Parts 1 and 3, and scripted transitions between
parts. Evaluation happens only at the end, from transcripts plus measured speech metrics.
Pronunciation is only estimated when audio-derived indicators exist (speech-recognition
confidence); otherwise it is reported as "not assessed".
"""

from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.context import build_context
from app.agents.error_analyst import ErrorRecord
from app.agents.vocabulary_engine import contains_item
from app.ai.client import ai_client
from app.ai.mock.speaking import plan as bank_plan
from app.ai.providers.base import AIError
from app.ai.schemas import SpeakingEvaluationAI, SpeakingPlanAI, SpeakingTurnAI
from app.analytics.grammar_rules import detect_errors
from app.analytics.speaking_metrics import aggregate, heuristic_speaking
from app.core.clock import get_zone, utcnow
from app.core.levels import clamp_band, round_band_down, snap_half
from app.core.taxonomy import category_for, normalize_subcategory
from app.models import SpeakingEvaluation, SpeakingSession, SpeakingTopic, User, VocabularyItem
from app.services.content import speaking_bank

MAX_FOLLOWUPS = {1: 2, 2: 0, 3: 2}
PART_TIMING = {1: {"max_seconds": 45}, 3: {"max_seconds": 75}}


def _time_of_day(user: User) -> str:
    hour = utcnow().astimezone(get_zone(user.profile.timezone)).hour
    return "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"


def topic_bank(db: Session) -> dict:
    """Active speaking topics from the database (admins can hide topics); falls back to the seed file."""
    rows = db.scalars(select(SpeakingTopic).where(SpeakingTopic.is_active.is_(True))).all()
    part1 = [{"topic": r.topic, "questions": r.questions} for r in rows if r.kind == "part1" and r.questions]
    cards = [
        {"topic": r.topic, "tags": r.tags, "cue_card": r.cue_card, "part3_questions": r.part3_questions}
        for r in rows
        if r.kind == "cue_card" and r.cue_card and len(r.part3_questions) >= 3
    ]
    if part1 and cards:
        return {"part1": part1, "cue_cards": cards}
    bank = speaking_bank()
    return {"part1": bank["part1"], "cue_cards": bank["cue_cards"]}


def create_plan(db: Session, user: User, mode: str) -> tuple[dict, list[str]]:
    """Returns (plan, target_expressions)."""
    ctx = build_context(db, user)
    seed = random.randint(1, 10_000_000)
    themes = list(ctx.preferred_topics)
    recent = [
        t for t in db.scalars(select(SpeakingSession.topic).where(SpeakingSession.user_id == user.id).order_by(SpeakingSession.created_at.desc()).limit(3)) if t
    ]
    bank_context = {"seed": seed, "themes": themes, "avoid_topics": recent, "bank": topic_bank(db)}
    try:
        parsed, _ = ai_client.generate_model(
            "speaking_plan",
            {
                "mode": mode,
                "learner_context": ctx.for_prompt("speaking"),
                "themes": ", ".join(themes) or "(any)",
                "avoid_topics": ", ".join(recent) or "(none)",
            },
            SpeakingPlanAI,
            user_id=user.id,
            mock_context=bank_context,
        )
        if len(parsed.cue_card.bullets) < 3 or not parsed.part1 or len(parsed.part3) < 3:
            raise ValueError("incomplete plan")
    except (AIError, ValueError):
        parsed = bank_plan(bank_context)

    lines = speaking_bank()["examiner_lines"]
    queue: list[dict] = []
    if mode in ("full", "part1"):
        for frame in parsed.part1[:2]:
            for q in frame.questions[:3]:
                queue.append({"part": 1, "kind": "question", "question": q, **PART_TIMING[1]})
    if mode in ("full", "part2"):
        card = parsed.cue_card.model_dump()
        queue.append({"part": 2, "kind": "cue_card", "question": card["prompt"], "cue_card": card, "prep_seconds": 60, "max_seconds": 120})
        queue.append({"part": 2, "kind": "rounding_off", "question": card["rounding_off"], "max_seconds": 30})
    if mode in ("full", "part3"):
        for q in parsed.part3[:4]:
            queue.append({"part": 3, "kind": "question", "question": q, **PART_TIMING[3]})
    plan = {
        "topic": parsed.topic,
        "queue": queue,
        "intro": lines["intro"].format(time_of_day=_time_of_day(user)),
        "part2_intro": lines["part2_intro"],
        "part3_intro": lines["part3_intro"].format(topic=parsed.cue_card.title.lower()),
        "closing": lines["closing"],
        "followups": {"1": 0, "3": 0},
        "last_followup_index": -1,
    }
    return plan, ctx.target_expressions[:3]


def first_turn(session: SpeakingSession) -> dict:
    plan = session.plan
    first = plan["queue"][0]
    lead = plan["intro"]
    if first["part"] == 2:
        lead = plan["part2_intro"]
    elif first["part"] == 3:
        lead = plan["part3_intro"]
    return _turn_payload(first, f"{lead} {first['question']}" if first["kind"] == "question" else lead, is_followup=False, index=0, total=len(plan["queue"]))


def _turn_payload(item: dict, examiner_text: str, *, is_followup: bool, index: int, total: int) -> dict:
    return {
        "part": item["part"],
        "kind": "followup" if is_followup else item["kind"],
        "question": item["question"],
        "examiner_text": examiner_text,
        "is_followup": is_followup,
        "cue_card": item.get("cue_card"),
        "prep_seconds": item.get("prep_seconds", 0) if not is_followup else 0,
        "max_seconds": item.get("max_seconds", 60),
        "index": index,
        "total": total,
    }


def next_turn(db: Session, user: User, session: SpeakingSession, answer: str, word_count: int, current_question: dict) -> dict | None:
    """Decide the examiner's next move. Returns the next turn payload, or None when the test ends."""
    plan = dict(session.plan)
    queue = plan["queue"]
    index = session.current_index
    item = queue[index]
    part = item["part"]
    followups = dict(plan.get("followups", {"1": 0, "3": 0}))
    asked = followups.get(str(part), 0)
    acknowledgement = "Thank you."
    if part in (1, 3) and asked < MAX_FOLLOWUPS[part] and not current_question.get("is_followup") and plan.get("last_followup_index") != index:
        next_question = queue[index + 1]["question"] if index + 1 < len(queue) else "(end of test)"
        try:
            decision, _ = ai_client.generate_model(
                "speaking_turn",
                {
                    "part": part,
                    "followups_asked": asked,
                    "max_followups": MAX_FOLLOWUPS[part],
                    "question": current_question.get("question", item["question"]),
                    "word_count": word_count,
                    "answer": answer or "(no answer)",
                    "next_question": next_question,
                },
                SpeakingTurnAI,
                user_id=user.id,
                mock_context={
                    "part": part,
                    "word_count": word_count,
                    "followups_asked": asked,
                    "max_followups": MAX_FOLLOWUPS[part],
                    "turn_index": session.followups_asked + index,
                },
            )
            acknowledgement = (decision.acknowledgement or "Thank you.").strip()[:40]
            if decision.action == "followup" and decision.followup_question:
                followups[str(part)] = asked + 1
                plan["followups"] = followups
                plan["last_followup_index"] = index
                session.plan = plan
                session.followups_asked += 1
                followup_item = {**item, "question": decision.followup_question.strip()[:200]}
                return _turn_payload(followup_item, f"{acknowledgement} {followup_item['question']}", is_followup=True, index=index, total=len(queue))
        except AIError:
            pass  # a failed follow-up decision must never break the test: just move on
    index += 1
    session.current_index = index
    session.plan = plan
    if index >= len(queue):
        return None
    nxt = queue[index]
    lead = acknowledgement
    if nxt["part"] != part:
        lead = f"{acknowledgement} {plan['part2_intro'] if nxt['part'] == 2 else plan['part3_intro']}"
    session.current_part = nxt["part"]
    text = lead if nxt["kind"] == "cue_card" else f"{lead} {nxt['question']}"
    return _turn_payload(nxt, text, is_followup=False, index=index, total=len(queue))


def evaluate_session(db: Session, user: User, session: SpeakingSession) -> tuple[SpeakingEvaluation, list[ErrorRecord], dict]:
    transcripts = [t for t in session.transcripts if (t.transcript or "").strip()]
    responses = [{"transcript": t.transcript, "part": t.part, "metrics": t.metrics, "stt_confidence": t.stt_confidence} for t in transcripts]
    agg = aggregate(responses)
    rule_errors = []
    for t in transcripts:
        for e in detect_errors(t.transcript, mode="speaking"):
            e.context = e.context or t.transcript[:300]
            rule_errors.append(e)
    expressions = session.target_expressions or []
    items = {i.word: i for i in db.scalars(select(VocabularyItem).where(VocabularyItem.word.in_(expressions)))} if expressions else {}
    all_text = " ".join(t.transcript for t in transcripts)
    used = [w for w in expressions if (items.get(w) and contains_item(all_text, items[w])) or (not items.get(w) and w.lower() in all_text.lower())]
    ctx = build_context(db, user)
    transcript_text = "\n\n".join(
        f"Part {t.part}{' (follow-up)' if t.is_followup else ''} - Q: {t.question}\nA ({t.duration_seconds:.0f}s, source: {t.transcript_source}): {t.transcript}"
        for t in transcripts
    )
    metrics_text = (
        f"responses={agg.responses}; total speaking time={agg.total_seconds}s; words={agg.total_words}; average rate={agg.avg_wpm} wpm; "
        f"fillers per minute={agg.fillers_per_minute} {agg.filler_counts}; pauses={'measured from audio' if agg.pauses_measured else 'estimated'}: "
        f"{agg.pauses} ({agg.long_pauses} long); lexical variety (MATTR)={agg.lexical_variety}; repeated words={[w for w, _ in agg.repeated_words]}; "
        f"subordinate clauses per 100 words={agg.complexity_per_100}; developed answers={agg.developed_ratio * 100:.0f}%; "
        f"average relevance={agg.avg_relevance}; average words by part={agg.part_words}"
    )
    pron_text = (
        f"Average speech-recognition confidence: {agg.stt_confidence} (from server transcription of the learner's audio)."
        if agg.stt_confidence is not None
        else "None available (transcripts came from typing or browser recognition). Set pronunciation to null."
    )
    variables = {
        "metrics": metrics_text,
        "pronunciation_indicators": pron_text,
        "target_expressions": expressions or ["(none)"],
        "rule_errors": "\n".join(f"- [{e.subcategory}] '{e.original}' -> '{e.corrected}'" for e in rule_errors[:20]) or "(none)",
        "learner_context": ctx.for_prompt("speaking"),
        "transcripts": transcript_text or "(no answers)",
    }
    parsed, result = ai_client.generate_model(
        "speaking_evaluate",
        variables,
        SpeakingEvaluationAI,
        user_id=user.id,
        mock_context={"aggregate": agg, "rule_errors": rule_errors, "expressions_used": used},
    )
    fc = snap_half(clamp_band(parsed.fluency_coherence.band))
    lr = snap_half(clamp_band(parsed.lexical_resource.band))
    gra = snap_half(clamp_band(parsed.grammatical_range_accuracy.band))
    pron = None
    pron_note = "Not assessed: pronunciation can't be judged reliably from a transcript. Record with server transcription enabled for a cautious estimate."
    if agg.stt_confidence is not None and parsed.pronunciation is not None:
        pron = snap_half(clamp_band(parsed.pronunciation.band))
        pron_note = parsed.pronunciation.comment or "Low-confidence estimate based on speech-recognition clarity; not a phoneme-level assessment."
    bands = [fc, lr, gra] + ([pron] if pron is not None else [])
    if agg.total_words < 60:
        bands = [min(b, 5.0) for b in bands]
        fc, lr, gra = bands[0], bands[1], bands[2]
    overall = round_band_down(sum(bands) / len(bands))

    errors_out, records = [], []
    seen = set()
    for err in list(parsed.errors) + rule_errors:
        original = (err.original or "").strip()
        corrected = (err.corrected or "").strip()
        if not original or not corrected or original.lower() == corrected.lower() or original.lower() in seen:
            continue
        source_t = next((t for t in transcripts if original.lower() in t.transcript.lower()), None)
        if source_t is None:
            continue  # not verbatim in any transcript: discard
        seen.add(original.lower())
        sub = normalize_subcategory(err.subcategory, err.category)
        errors_out.append(
            {
                "category": category_for(sub),
                "subcategory": sub,
                "original": original,
                "corrected": corrected,
                "explanation": err.explanation,
                "severity": err.severity,
                "part": source_t.part,
            }
        )
        records.append(
            ErrorRecord(
                source="speaking",
                category=category_for(sub),
                subcategory=sub,
                original=original,
                corrected=corrected,
                explanation=err.explanation,
                context=source_t.transcript[:300],
                severity=err.severity,
                ref_type="speaking_session",
                ref_id=session.id,
            )
        )
    if agg.fillers_per_minute > 4 and agg.filler_counts:
        top = ", ".join(f"'{w}' x{n}" for w, n in sorted(agg.filler_counts.items(), key=lambda kv: -kv[1])[:3])
        records.append(
            ErrorRecord(
                source="speaking",
                category="fluency",
                subcategory="filler_words",
                original=f"Frequent fillers: {top}",
                corrected="Pause briefly instead, or use a discourse marker such as 'Well,' or 'Let me think,'",
                explanation="Frequent fillers make speech sound hesitant.",
                severity="medium",
                ref_type="speaking_session",
                ref_id=session.id,
                signature_hint="fillers",
            )
        )
    if agg.short_answers >= 2:
        records.append(
            ErrorRecord(
                source="speaking",
                category="fluency",
                subcategory="short_answers",
                original=f"{agg.short_answers} answers were too short to show your range",
                corrected="Answer + reason + example (aim for 3 sentences in Part 1)",
                explanation="Extended answers show fluency and give the examiner more evidence of your range.",
                severity="medium",
                ref_type="speaking_session",
                ref_id=session.id,
                signature_hint="short",
            )
        )

    evaluation = SpeakingEvaluation(
        session_id=session.id,
        user_id=user.id,
        overall_band=overall,
        fluency_coherence=fc,
        lexical_resource=lr,
        grammatical_range_accuracy=gra,
        pronunciation=pron,
        pronunciation_note=pron_note,
        criteria_feedback={
            "fluency_coherence": {"label": "Fluency & Coherence", "band": fc, "comment": parsed.fluency_coherence.comment},
            "lexical_resource": {"label": "Lexical Resource", "band": lr, "comment": parsed.lexical_resource.comment},
            "grammatical_range_accuracy": {"label": "Grammatical Range & Accuracy", "band": gra, "comment": parsed.grammatical_range_accuracy.comment},
            "pronunciation": {"label": "Pronunciation", "band": pron, "comment": pron_note},
        },
        metrics=agg.to_dict(),
        hesitation=_hesitation(agg),
        repeated_words=[{"word": w, "count": c} for w, c in agg.repeated_words],
        fillers={
            "counts": agg.filler_counts,
            "per_minute": agg.fillers_per_minute,
            "note": "Filler detection depends on the transcription; some speech engines omit 'um' and 'uh'.",
        },
        grammar_patterns=parsed.grammar_patterns[:6],
        errors=errors_out[:15],
        strengths=parsed.strengths[:6],
        weaknesses=parsed.weaknesses[:6],
        recommendations=parsed.recommendations[:6],
        expressions_used=used,
        summary=f"{parsed.summary}\n\nRelevance: {parsed.relevance_notes}\nDevelopment: {parsed.development_notes}".strip(),
        provider=result.provider,
        model=(result.model or "")[:60],
        is_mock=ai_client.is_mock,
    )
    db.add(evaluation)
    db.flush()
    return evaluation, records, {"aggregate": agg, "used": used, "text": all_text}


def _hesitation(agg) -> dict:
    return heuristic_speaking(agg, []).hesitation
