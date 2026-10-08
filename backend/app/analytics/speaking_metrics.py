"""Speaking practice metrics computed from transcripts and (when available) measured audio timing.

Honesty rules:
  * pause counts are only reported as "measured" when the client analysed the audio signal;
    otherwise they are explicitly marked as estimates;
  * filler detection depends on the transcription (some speech engines drop "um"/"uh");
  * pronunciation is never inferred from text alone.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from app.analytics.grammar_rules import DetectedError
from app.analytics.text import (
    SUBORDINATORS,
    content_words,
    find_linkers,
    keyword_coverage,
    mattr,
    stem,
    words,
)
from app.core.levels import round_band_down, snap_half

FILLERS: dict[str, re.Pattern] = {
    "um": re.compile(r"\bu+m+\b", re.I),
    "uh": re.compile(r"\bu+h+\b", re.I),
    "er": re.compile(r"\ber+\b", re.I),
    "erm": re.compile(r"\berm+\b", re.I),
    "ah": re.compile(r"\bah+\b", re.I),
    "hmm": re.compile(r"\bhm+\b", re.I),
    "you know": re.compile(r"\byou know\b(?=\s*[,.?!]|\s+(?:i|it|like|um|uh|so|and)\b|\s*$)", re.I),
    "i mean": re.compile(r"\bi mean\b(?=\s*[,.]|\s+(?:like|um|uh|so)\b)", re.I),
    "like": re.compile(r"(?:^|[,.]\s*|\b(?:um|uh|and|so)\s+)like\s*,", re.I),
    "kind of": re.compile(
        r"(?<!\ba )(?<!\bthe )(?<!\bthis )(?<!\bthat )(?<!\bwhat )(?<!\bany )(?<!\bsome )\bkind of\b(?=\s+(?:\w+ly|good|nice|bad|hard|difficult|interesting|boring|like|feel|think)\b)",
        re.I,
    ),
    "sort of": re.compile(
        r"(?<!\ba )(?<!\bthe )(?<!\bthis )(?<!\bthat )(?<!\bwhat )\bsort of\b(?=\s+(?:\w+ly|good|nice|bad|hard|difficult|interesting|boring|like|feel|think)\b)",
        re.I,
    ),
    "basically": re.compile(r"\bbasically\b", re.I),
    "literally": re.compile(r"\bliterally\b", re.I),
}

REASON_MARKERS = re.compile(r"\b(because|since|so|that's why|that is why|the reason|due to|as a result|which means)\b", re.I)
EXAMPLE_MARKERS = re.compile(r"\b(for example|for instance|such as|like when|one time|i remember|last (year|week|month|summer)|when i was)\b", re.I)

EXPECTED_WORDS = {1: 25, 2: 140, 3: 45}


@dataclass
class ResponseMetrics:
    word_count: int
    duration_seconds: float
    duration_estimated: bool
    wpm: float
    fillers: dict[str, int]
    filler_total: int
    fillers_per_minute: float
    pauses: int
    long_pauses: int
    pauses_measured: bool
    silence_seconds: float
    lexical_variety: float
    repeated_words: list[tuple[str, int]]
    complexity_per_100: float
    relevance: float
    has_reason: bool
    has_example: bool
    developed: bool

    def to_dict(self) -> dict:
        return {
            **{k: v for k, v in self.__dict__.items() if k != "repeated_words"},
            "repeated_words": [{"word": w, "count": c} for w, c in self.repeated_words],
        }


def count_fillers(text: str) -> dict[str, int]:
    counts = {}
    for name, pattern in FILLERS.items():
        n = len(pattern.findall(text or ""))
        if n:
            counts[name] = n
    return counts


def _complexity_markers(text: str) -> int:
    lowered = f" {(text or '').lower()} "
    return sum(len(re.findall(rf"(?<![a-z]){re.escape(m)}(?![a-z])", lowered)) for m in SUBORDINATORS)


def analyze_response(
    transcript: str,
    *,
    question: str,
    part: int,
    duration_seconds: float | None = None,
    pauses: dict | None = None,
) -> ResponseMetrics:
    tokens = words(transcript)
    n = len(tokens)
    estimated = not duration_seconds or duration_seconds <= 0
    duration = float(duration_seconds) if not estimated else round(n / 2.2, 1)  # ~130 wpm when unknown
    minutes = max(duration / 60.0, 1e-6)
    fillers = count_fillers(transcript)
    filler_total = sum(fillers.values())
    measured = bool(pauses) and pauses.get("measured", True)
    if measured:
        pause_count = int(pauses.get("count", 0))
        long_pauses = int(pauses.get("long_count", 0))
        silence = float(pauses.get("total_silence_seconds", 0.0))
    else:
        pause_count = filler_total + transcript.count("...")
        long_pauses = transcript.count("...")
        silence = 0.0
    question_stems = {stem(w) for w in content_words(words(question))}
    repeated = [(w, c) for w, c in Counter(content_words(tokens)).most_common() if c >= 3 and stem(w) not in question_stems][:5]
    has_reason = bool(REASON_MARKERS.search(transcript))
    has_example = bool(EXAMPLE_MARKERS.search(transcript))
    expected = EXPECTED_WORDS.get(part, 30)
    return ResponseMetrics(
        word_count=n,
        duration_seconds=round(duration, 1),
        duration_estimated=estimated,
        wpm=round(n / minutes, 1) if n else 0.0,
        fillers=fillers,
        filler_total=filler_total,
        fillers_per_minute=round(filler_total / minutes, 2) if n else 0.0,
        pauses=pause_count,
        long_pauses=long_pauses,
        pauses_measured=measured,
        silence_seconds=round(silence, 1),
        lexical_variety=round(mattr(tokens, window=30), 3),
        repeated_words=repeated,
        complexity_per_100=round(_complexity_markers(transcript) / max(n, 1) * 100, 2),
        relevance=round(keyword_coverage(question, transcript), 3),
        has_reason=has_reason,
        has_example=has_example,
        developed=n >= expected and (has_reason or has_example or part == 2),
    )


@dataclass
class SpeakingAggregate:
    responses: int
    total_words: int
    total_seconds: float
    avg_wpm: float
    filler_counts: dict[str, int]
    fillers_per_minute: float
    pauses: int
    long_pauses: int
    pauses_measured: bool
    pauses_per_minute: float
    lexical_variety: float
    less_common_ratio: float
    repeated_words: list[tuple[str, int]]
    complexity_per_100: float
    avg_relevance: float
    developed_ratio: float
    short_answers: int
    linker_variety: int
    part_words: dict[str, float]
    stt_confidence: float | None

    def to_dict(self) -> dict:
        data = dict(self.__dict__)
        data["repeated_words"] = [{"word": w, "count": c} for w, c in self.repeated_words]
        return data


def aggregate(responses: list[dict]) -> SpeakingAggregate:
    """`responses`: [{transcript, part, metrics (ResponseMetrics dict), stt_confidence}]"""
    all_text = " ".join(r["transcript"] for r in responses)
    tokens = words(all_text)
    total_seconds = sum(r["metrics"]["duration_seconds"] for r in responses) or 1.0
    minutes = total_seconds / 60.0
    filler_counts: Counter = Counter()
    for r in responses:
        filler_counts.update(r["metrics"].get("fillers", {}))
    measured = any(r["metrics"].get("pauses_measured") for r in responses)
    pauses = sum(r["metrics"].get("pauses", 0) for r in responses)
    long_pauses = sum(r["metrics"].get("long_pauses", 0) for r in responses)
    unique_content = set(content_words(tokens))
    by_part: dict[str, list[int]] = {}
    for r in responses:
        by_part.setdefault(str(r["part"]), []).append(r["metrics"]["word_count"])
    confidences = [r["stt_confidence"] for r in responses if r.get("stt_confidence") is not None]
    developed = [r for r in responses if r["metrics"].get("developed")]
    short = [r for r in responses if r["metrics"]["word_count"] < EXPECTED_WORDS.get(r["part"], 30) * 0.6]
    repeated = [(w, c) for w, c in Counter(content_words(tokens)).most_common() if c >= 4][:6]
    return SpeakingAggregate(
        responses=len(responses),
        total_words=len(tokens),
        total_seconds=round(total_seconds, 1),
        avg_wpm=round(len(tokens) / minutes, 1) if tokens else 0.0,
        filler_counts=dict(filler_counts),
        fillers_per_minute=round(sum(filler_counts.values()) / minutes, 2),
        pauses=pauses,
        long_pauses=long_pauses,
        pauses_measured=measured,
        pauses_per_minute=round(pauses / minutes, 2),
        lexical_variety=round(mattr(tokens, window=30), 3),
        less_common_ratio=round(len({w for w in unique_content if len(w) >= 9}) / len(unique_content), 3) if unique_content else 0.0,
        repeated_words=repeated,
        complexity_per_100=round(_complexity_markers(all_text) / max(len(tokens), 1) * 100, 2),
        avg_relevance=round(sum(r["metrics"].get("relevance", 0) for r in responses) / len(responses), 3) if responses else 0.0,
        developed_ratio=round(len(developed) / len(responses), 2) if responses else 0.0,
        short_answers=len(short),
        linker_variety=len({h for hits in find_linkers(all_text).values() for h in hits}),
        part_words={k: round(sum(v) / len(v), 1) for k, v in by_part.items()},
        stt_confidence=round(sum(confidences) / len(confidences), 3) if confidences else None,
    )


@dataclass
class SpeakingHeuristic:
    fluency_coherence: tuple[float, str]
    lexical_resource: tuple[float, str]
    grammatical_range_accuracy: tuple[float, str]
    pronunciation: tuple[float, str] | None
    overall: float
    strengths: list[str]
    weaknesses: list[str]
    hesitation: dict


def heuristic_speaking(agg: SpeakingAggregate, errors: list[DetectedError], expressions_used: int = 0) -> SpeakingHeuristic:
    strengths: list[str] = []
    weaknesses: list[str] = []

    fc = 5.5
    if 110 <= agg.avg_wpm <= 170:
        fc += 0.5
        strengths.append(f"Comfortable speaking pace (about {agg.avg_wpm:.0f} words per minute)")
    elif agg.avg_wpm < 80:
        fc -= 0.5
        weaknesses.append(f"Slow speaking pace (about {agg.avg_wpm:.0f} words per minute) suggests searching for words")
    elif agg.avg_wpm > 190:
        fc -= 0.25
        weaknesses.append("Very fast pace - slow down slightly so ideas are clear")
    if agg.fillers_per_minute < 2:
        fc += 0.5
    elif agg.fillers_per_minute > 7:
        fc -= 1.0
        weaknesses.append(f"Frequent filler words ({agg.fillers_per_minute:.1f} per minute)")
    elif agg.fillers_per_minute > 4:
        fc -= 0.5
        weaknesses.append(f"Noticeable filler words ({agg.fillers_per_minute:.1f} per minute)")
    if agg.pauses_measured:
        long_per_min = agg.long_pauses / max(agg.total_seconds / 60, 1e-6)
        if long_per_min < 0.5:
            fc += 0.5
            strengths.append("Few long pauses")
        elif long_per_min > 2:
            fc -= 0.5
            weaknesses.append("Long pauses interrupt the flow of speech")
    if agg.developed_ratio >= 0.7:
        fc += 0.5
        strengths.append("Answers are developed with reasons or examples")
    elif agg.developed_ratio < 0.4:
        fc -= 1.0
        weaknesses.append("Many answers are short - extend them with a reason and an example")
    if agg.linker_variety >= 4:
        fc += 0.5
        strengths.append("Uses a range of discourse markers to connect ideas")

    lr = 5.5
    if agg.lexical_variety >= 0.88:
        lr += 1.0
        strengths.append("Wide and varied vocabulary")
    elif agg.lexical_variety >= 0.84:
        lr += 0.5
    elif agg.lexical_variety < 0.76:
        lr -= 0.5
        weaknesses.append("Vocabulary is repetitive")
    if agg.less_common_ratio >= 0.06:
        lr += 0.5
    if len(agg.repeated_words) >= 3:
        lr -= 0.5
        top = ", ".join(f"'{w}'" for w, _ in agg.repeated_words[:3])
        weaknesses.append(f"Some words are repeated often ({top}) - try paraphrasing")
    if expressions_used >= 2:
        lr += 0.25
        strengths.append("Used your target expressions naturally")
    lexis_errors = sum(1 for e in errors if e.subcategory in ("collocation", "word_choice", "word_formation"))
    if lexis_errors >= 2:
        lr -= 0.5
        weaknesses.append("Some collocations sound unnatural")

    gra = 5.5
    grammar_errors = [e for e in errors if e.category == "grammar"]
    per100 = len(grammar_errors) / max(agg.total_words, 1) * 100
    if not grammar_errors:
        gra += 1.5
        strengths.append("No grammatical errors detected in the transcript")
    elif per100 < 1:
        gra += 1.0
    elif per100 < 2:
        gra += 0.5
    elif per100 >= 4:
        gra -= 1.0
        weaknesses.append("Frequent grammatical errors")
    if agg.complexity_per_100 >= 5:
        gra += 1.0
        strengths.append("Uses complex sentences with subordinate clauses")
    elif agg.complexity_per_100 >= 3:
        gra += 0.5
    elif agg.complexity_per_100 < 1.5:
        gra -= 0.5
        weaknesses.append("Mostly simple sentences - add 'because', 'which', 'although' clauses")

    if agg.total_words < 60:
        fc, lr, gra = min(fc, 5.0), min(lr, 5.0), min(gra, 5.0)
        weaknesses.append("The sample is very short, so this estimate has low reliability")

    fc_b, lr_b, gra_b = (snap_half(max(3.0, min(8.5, v))) for v in (fc, lr, gra))
    pron: tuple[float, str] | None = None
    if agg.stt_confidence is not None:
        c = agg.stt_confidence
        p_band = 7.5 if c >= 0.95 else 7.0 if c >= 0.9 else 6.5 if c >= 0.85 else 6.0 if c >= 0.8 else 5.5 if c >= 0.7 else 5.0
        pron = (p_band, "Low-confidence estimate based on how reliably speech recognition understood you; not a phoneme-level assessment.")
    bands = [fc_b, lr_b, gra_b] + ([pron[0]] if pron else [])
    overall = round_band_down(sum(bands) / len(bands))

    if agg.pauses_measured:
        level = "low" if agg.long_pauses <= 1 else "moderate" if agg.long_pauses <= 4 else "high"
        note = f"{agg.pauses} pauses detected from your audio, {agg.long_pauses} of them longer than two seconds."
    else:
        level = "low" if agg.fillers_per_minute < 2 else "moderate" if agg.fillers_per_minute < 5 else "high"
        note = "Pauses could not be measured from audio, so hesitation is estimated from filler words."
    hesitation = {
        "level": level,
        "measured": agg.pauses_measured,
        "pauses": agg.pauses,
        "long_pauses": agg.long_pauses,
        "pauses_per_minute": agg.pauses_per_minute,
        "fillers_per_minute": agg.fillers_per_minute,
        "note": note,
    }
    return SpeakingHeuristic(
        fluency_coherence=(fc_b, "Fluency & Coherence: estimated from pace, hesitation, fillers and answer development."),
        lexical_resource=(lr_b, "Lexical Resource: estimated from vocabulary range, variety and repetition."),
        grammatical_range_accuracy=(gra_b, "Grammatical Range & Accuracy: estimated from errors and sentence complexity in the transcript."),
        pronunciation=pron,
        overall=overall,
        strengths=strengths[:5] or ["You completed the speaking session - every session builds fluency."],
        weaknesses=weaknesses[:6],
        hesitation=hesitation,
    )
