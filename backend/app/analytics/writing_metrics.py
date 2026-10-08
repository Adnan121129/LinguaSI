"""Essay analysis and a transparent, rubric-inspired heuristic band estimator.

The heuristic estimator is what the mock Writing Examiner uses. It follows the structure of the
public IELTS Writing criteria (Task Response / Task Achievement, Coherence & Cohesion, Lexical
Resource, Grammatical Range & Accuracy) using measurable features, so every band it produces
can be explained. Real AI evaluations receive the same metrics as grounding facts.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field

from app.analytics.grammar_rules import DetectedError
from app.analytics.text import academic_words as _academic_words
from app.analytics.text import (
    content_words,
    find_linkers,
    is_complex_sentence,
    keyword_coverage,
    mattr,
    split_paragraphs,
    split_sentences,
    stem,
    words,
)
from app.core.levels import clamp_band, round_band_down, snap_half

OPINION_MARKERS = re.compile(
    r"\b(i (strongly |completely |partly |firmly )?(agree|disagree|believe|think|feel|would argue)|in my (view|opinion)|"
    r"from my (point of view|perspective)|this essay (will )?(argue|argues)|i am (convinced|of the opinion)|"
    r"my (own )?view is|personally,)",
    re.IGNORECASE,
)
CONCLUSION_MARKERS = re.compile(r"\b(in conclusion|to conclude|to sum up|in summary|to summarise|to summarize|all in all|overall, i)\b", re.IGNORECASE)
OVERVIEW_MARKERS = re.compile(
    r"\b(overall|in general|it is (clear|evident|noticeable) that|it can be seen that|the most (striking|noticeable|significant) (feature|trend))\b",
    re.IGNORECASE,
)
EXAMPLE_MARKERS = re.compile(r"\b(for example|for instance|such as|to illustrate|a case in point|in particular)\b", re.IGNORECASE)
COMPARISON_MARKERS = re.compile(
    r"\b(compared (to|with)|than|whereas|while|in contrast|by contrast|the (highest|lowest|largest|smallest)|similarly|twice|half)\b", re.IGNORECASE
)
BOTH_VIEWS_MARKERS = re.compile(r"\b(some people|others|on the other hand|opponents|supporters|proponents|critics|while some)\b", re.IGNORECASE)
SEQUENCE_MARKERS = re.compile(r"\b(first(ly)?|then|next|after (that|this)|subsequently|finally|at the (next|final) stage|following this|once)\b", re.IGNORECASE)
GREETING = re.compile(r"^\s*(dear\b|hi\b|hello\b)", re.IGNORECASE)
SIGN_OFF = re.compile(
    r"\b(yours (faithfully|sincerely|truly)|best (wishes|regards)|kind regards|warm regards|regards,|love,|cheers,|all the best)\b", re.IGNORECASE
)
PURPOSE = re.compile(r"\b(i am writing|i'm writing|i write to|the (reason|purpose) (for|of) (this|my) (letter|email))\b", re.IGNORECASE)
NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:%|percent|per cent|million|billion|thousand)?", re.IGNORECASE)
REFERENCE_WORDS = re.compile(r"\b(this|these|those|such|which|it|they|former|latter)\b", re.IGNORECASE)


@dataclass
class EssayAnalysis:
    word_count: int
    min_words: int
    under_length: bool
    sentence_count: int
    paragraph_count: int
    avg_sentence_length: float
    long_sentences: int
    lexical_diversity: float
    academic_words: list[str]
    academic_ratio: float
    less_common_ratio: float
    linkers: dict[str, list[str]]
    linker_variety: int
    overused_linkers: list[tuple[str, int]]
    complex_ratio: float
    repeated_words: list[tuple[str, int]]
    reference_density: float
    position_statement: bool
    conclusion: bool
    overview: bool
    examples: bool
    comparisons: bool
    numbers_count: int
    sequence_markers: int
    both_views: bool
    greeting: bool
    sign_off: bool
    purpose_statement: bool
    prompt_coverage: float
    key_point_coverage: float
    body_paragraph_avg_words: float
    error_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["overused_linkers"] = [{"linker": w, "count": c} for w, c in self.overused_linkers]
        data["repeated_words"] = [{"word": w, "count": c} for w, c in self.repeated_words]
        return data


def analyze_essay(
    text: str,
    *,
    task_type: str,
    module: str,
    prompt: str,
    key_points: list[str] | None = None,
    min_words: int = 250,
    errors: list[DetectedError] | None = None,
) -> EssayAnalysis:
    tokens = words(text)
    sentences = split_sentences(text)
    paragraphs = split_paragraphs(text)
    content = content_words(tokens)
    unique_content = set(content)
    academic = sorted(set(_academic_words(tokens)))
    long_unique = {w for w in unique_content if len(w) >= 9}
    linkers = find_linkers(text)
    linker_counter: Counter = Counter()
    for hits in linkers.values():
        linker_counter.update(hits)
    prompt_stems = {stem(w) for w in content_words(words(prompt))}
    repeated = [(w, c) for w, c in Counter(content).most_common() if c >= max(4, len(tokens) // 60) and stem(w) not in prompt_stems][:6]
    key_cov = 1.0
    if key_points:
        key_cov = sum(1 for kp in key_points if keyword_coverage(kp, text) >= 0.4) / len(key_points)
    body = paragraphs[1:-1] if len(paragraphs) > 2 else paragraphs
    error_counts: Counter = Counter()
    for err in errors or []:
        error_counts[err.category] += 1
        error_counts[f"sub:{err.subcategory}"] += 1
    return EssayAnalysis(
        word_count=len(tokens),
        min_words=min_words,
        under_length=len(tokens) < min_words,
        sentence_count=len(sentences),
        paragraph_count=len(paragraphs),
        avg_sentence_length=round(len(tokens) / len(sentences), 1) if sentences else 0.0,
        long_sentences=sum(1 for s in sentences if len(words(s)) > 40),
        lexical_diversity=round(mattr(tokens), 3),
        academic_words=academic,
        academic_ratio=round(len(academic) / len(unique_content), 3) if unique_content else 0.0,
        less_common_ratio=round(len(long_unique) / len(unique_content), 3) if unique_content else 0.0,
        linkers={k: sorted(set(v)) for k, v in linkers.items()},
        linker_variety=len(linker_counter),
        overused_linkers=[(w, c) for w, c in linker_counter.most_common() if c >= 4],
        complex_ratio=round(sum(1 for s in sentences if is_complex_sentence(s)) / len(sentences), 3) if sentences else 0.0,
        repeated_words=repeated,
        reference_density=round(len(REFERENCE_WORDS.findall(text)) / len(sentences), 2) if sentences else 0.0,
        position_statement=bool(OPINION_MARKERS.search(text)),
        conclusion=bool(CONCLUSION_MARKERS.search(text)),
        overview=bool(OVERVIEW_MARKERS.search(text)),
        examples=bool(EXAMPLE_MARKERS.search(text)),
        comparisons=bool(COMPARISON_MARKERS.search(text)),
        numbers_count=len(NUMBER.findall(text)),
        sequence_markers=len(SEQUENCE_MARKERS.findall(text)),
        both_views=bool(BOTH_VIEWS_MARKERS.search(text)),
        greeting=bool(GREETING.search(text)),
        sign_off=bool(SIGN_OFF.search(text)),
        purpose_statement=bool(PURPOSE.search(text)),
        prompt_coverage=round(keyword_coverage(prompt, text), 3),
        key_point_coverage=round(key_cov, 3),
        body_paragraph_avg_words=round(sum(len(words(p)) for p in body) / len(body), 1) if body else 0.0,
        error_counts=dict(error_counts),
    )


@dataclass
class CriterionResult:
    band: float
    comment: str
    positives: list[str] = field(default_factory=list)
    negatives: list[str] = field(default_factory=list)


@dataclass
class HeuristicEvaluation:
    criteria: dict[str, CriterionResult]
    overall: float
    strengths: list[str]
    weaknesses: list[str]
    task_response_issues: list[str]
    cohesion_issues: list[str]
    vocabulary_issues: list[str]
    advice: list[str]


def _finish(base: float, positives: list[str], negatives: list[str], lead: str) -> CriterionResult:
    band = snap_half(max(3.0, min(8.5, base)))
    parts = [lead]
    if positives:
        parts.append("Strengths: " + "; ".join(positives[:2]) + ".")
    if negatives:
        parts.append("To improve: " + "; ".join(negatives[:2]) + ".")
    return CriterionResult(band, " ".join(parts), positives, negatives)


def _task_response(a: EssayAnalysis, task_type: str, module: str, category: str) -> CriterionResult:
    pos: list[str] = []
    neg: list[str] = []
    is_letter = task_type == "task1" and module == "general_training"
    is_report = task_type == "task1" and module == "academic"

    if is_report:
        band = 5.5
        if a.overview:
            band += 1.0
            pos.append("you include an overview of the main features")
        else:
            band -= 0.5
            neg.append("add a clear overview sentence summarising the main trends (e.g. 'Overall, ...')")
        if category == "process":
            if a.sequence_markers >= 4:
                band += 0.5
                pos.append("the stages are sequenced clearly")
            else:
                neg.append("describe every stage in order using sequencers (first, then, finally)")
        else:
            if a.numbers_count >= 5:
                band += 0.5
                pos.append("key figures are supported with data")
            elif a.numbers_count == 0:
                band -= 1.0
                neg.append("support the description with specific figures from the chart")
            if a.comparisons:
                band += 0.5
                pos.append("you make relevant comparisons")
            else:
                neg.append("compare the data rather than listing figures")
        if a.position_statement:
            band -= 0.5
            neg.append("remove personal opinions - Task 1 reports only what the visual shows")
    elif is_letter:
        band = 5.5
        if a.greeting:
            band += 0.5
        else:
            neg.append("open with an appropriate greeting (Dear ...)")
        if a.sign_off:
            band += 0.5
        else:
            neg.append("close with an appropriate sign-off")
        if a.purpose_statement:
            band += 0.5
            pos.append("the purpose of the letter is stated early")
        else:
            neg.append("state the purpose of the letter in the first paragraph")
        if a.key_point_coverage >= 0.66:
            band += 0.5
            pos.append("all bullet points are addressed")
        elif a.key_point_coverage < 0.34:
            band -= 1.0
            neg.append("cover every bullet point in the task")
    else:
        band = 6.0
        needs_position = category in ("opinion", "two_part", "discussion", "general_opinion")
        if needs_position:
            if a.position_statement:
                band += 0.5
                pos.append("your position is clearly stated")
            else:
                band -= 0.5
                neg.append("state your position clearly in the introduction and conclusion")
        if category == "discussion":
            if a.both_views:
                band += 0.5
                pos.append("both views are discussed")
            else:
                band -= 0.5
                neg.append("discuss both views before giving your own")
        if category == "advantages_disadvantages":
            has_adv = re.search(r"\b(advantage|benefit)", " ".join(a.academic_words) + " ") is not None
            if a.both_views or has_adv:
                band += 0.25
        if a.conclusion:
            band += 0.5
            pos.append("there is a clear conclusion")
        else:
            band -= 0.5
            neg.append("finish with a conclusion that restates your main point")
        if a.examples:
            band += 0.5
            pos.append("ideas are supported with examples")
        else:
            band -= 0.25
            neg.append("support each main idea with a specific example")
        if a.body_paragraph_avg_words >= 70:
            band += 0.25
            pos.append("body paragraphs are well developed")
        elif a.paragraph_count >= 3 and a.body_paragraph_avg_words < 45:
            band -= 0.5
            neg.append("extend each body paragraph with explanation and evidence")

    # Relevance and length apply to every task.
    if a.prompt_coverage < 0.2:
        band -= 1.5
        neg.insert(0, "the response does not clearly address the question - stay on the topic set")
    elif a.prompt_coverage < 0.3:
        band -= 0.5
        neg.append("refer more directly to the key ideas in the question")
    elif a.prompt_coverage >= 0.45:
        band += 0.25
    if a.word_count < a.min_words * 0.75:
        band -= 2.0
        neg.insert(0, f"the response is well under the {a.min_words}-word minimum")
    elif a.word_count < a.min_words:
        band -= 1.0
        neg.insert(0, f"write at least {a.min_words} words (you wrote {a.word_count})")
    label = "Task Achievement" if task_type == "task1" else "Task Response"
    lead = f"{label}: estimated from how fully and relevantly the task is addressed."
    return _finish(band, pos, neg, lead)


def _coherence(a: EssayAnalysis, task_type: str, errors: list[DetectedError]) -> CriterionResult:
    pos: list[str] = []
    neg: list[str] = []
    band = 5.5
    good_paragraphs = 4 if task_type == "task2" else 3
    if a.paragraph_count >= good_paragraphs:
        band += 0.5
        pos.append("the response is logically paragraphed")
    elif a.paragraph_count <= 1:
        band -= 1.0
        neg.append("organise your ideas into separate paragraphs")
    elif a.paragraph_count == 2 and task_type == "task2":
        band -= 0.5
        neg.append("use an introduction, two or three body paragraphs and a conclusion")
    if a.linker_variety >= 8:
        band += 1.0
        pos.append("a wide range of linking devices is used")
    elif a.linker_variety >= 5:
        band += 0.5
        pos.append("a good range of linking devices is used")
    elif a.linker_variety <= 1:
        band -= 1.0
        neg.append("use linking words to connect ideas (however, therefore, for example)")
    elif a.linker_variety <= 3:
        band -= 0.5
        neg.append("vary your linking devices")
    if a.overused_linkers:
        band -= 0.5
        word, count = a.overused_linkers[0]
        neg.append(f"'{word}' is used {count} times - vary or reduce linkers so they don't feel mechanical")
    if a.reference_density >= 0.4:
        band += 0.25
        pos.append("referencing (this, these, which) links sentences smoothly")
    structure_errors = sum(1 for e in errors if e.subcategory in ("sentence_structure", "punctuation"))
    if structure_errors >= 2:
        band -= 0.5
        neg.append("fix sentence boundaries (fragments and comma splices) so ideas flow clearly")
    if a.avg_sentence_length > 35:
        band -= 0.5
        neg.append("very long sentences make the argument hard to follow")
    return _finish(band, pos, neg, "Coherence & Cohesion: estimated from organisation, paragraphing and linking.")


def _lexical(a: EssayAnalysis, module: str, academic: bool, errors: list[DetectedError]) -> CriterionResult:
    pos: list[str] = []
    neg: list[str] = []
    band = 5.0
    # Thresholds are calibrated for a 40-token moving-average type-token ratio.
    if a.lexical_diversity >= 0.93:
        band += 1.5
        pos.append("vocabulary is varied and precise")
    elif a.lexical_diversity >= 0.90:
        band += 1.0
        pos.append("a good range of vocabulary is used")
    elif a.lexical_diversity >= 0.86:
        band += 0.5
    elif a.lexical_diversity < 0.80:
        band -= 0.5
        neg.append("vocabulary is repetitive - use synonyms and paraphrase")
    if academic:
        if a.academic_ratio >= 0.12:
            band += 1.0
            examples = ", ".join(a.academic_words[:4])
            pos.append(f"topic-specific and academic words are used ({examples})")
        elif a.academic_ratio >= 0.07:
            band += 0.5
        elif a.academic_ratio < 0.03:
            band -= 0.5
            neg.append("use more precise, topic-specific vocabulary")
    if a.less_common_ratio >= 0.08:
        band += 0.5
        pos.append("some less common lexical items appear")
    spelling = sum(1 for e in errors if e.category == "spelling")
    per100 = spelling / max(a.word_count, 1) * 100
    if per100 > 2:
        band -= 1.0
        neg.append("frequent spelling errors reduce clarity")
    elif per100 > 1:
        band -= 0.5
        neg.append("check spelling carefully")
    elif spelling == 0 and a.word_count >= 120:
        band += 0.25
    lexis_errors = sum(1 for e in errors if e.subcategory in ("collocation", "word_choice", "word_formation"))
    if lexis_errors >= 5:
        band -= 1.0
        neg.append("several unnatural collocations and word-form errors")
    elif lexis_errors >= 3:
        band -= 0.5
        neg.append("watch collocations (e.g. make a decision, carry out research)")
    informal = sum(1 for e in errors if e.category == "academic_style")
    if academic and informal >= 2:
        band -= 0.5
        neg.append("avoid informal words and contractions in academic writing")
    if len(a.repeated_words) >= 2:
        band -= 0.5
        words_list = ", ".join(f"'{w}'" for w, _ in a.repeated_words[:3])
        neg.append(f"some words are repeated often ({words_list})")
    return _finish(band, pos, neg, "Lexical Resource: estimated from range, precision, collocation and spelling.")


def _grammar(a: EssayAnalysis, errors: list[DetectedError]) -> CriterionResult:
    pos: list[str] = []
    neg: list[str] = []
    band = 5.0
    grammar_errors = [e for e in errors if e.category == "grammar" and not (e.subcategory == "punctuation" and e.severity == "low")]
    per100 = len(grammar_errors) / max(a.word_count, 1) * 100
    if not grammar_errors:
        band += 2.0
        pos.append("no grammatical errors were detected")
    elif per100 < 0.8:
        band += 1.5
        pos.append("grammar is mostly accurate")
    elif per100 < 1.8:
        band += 1.0
    elif per100 < 3.0:
        band += 0.5
    elif per100 >= 5.0:
        band -= 1.0
        neg.append("frequent grammatical errors affect communication")
    if per100 >= 1.8:
        top = Counter(e.subcategory for e in grammar_errors).most_common(1)
        if top:
            neg.append(f"repeated errors in {top[0][0].replace('_', ' ')}")
    if a.complex_ratio >= 0.55:
        band += 1.0
        pos.append("a wide range of complex structures is used")
    elif a.complex_ratio >= 0.35:
        band += 0.5
        pos.append("a mix of simple and complex sentences is used")
    elif a.complex_ratio < 0.15:
        band -= 0.5
        neg.append("use more complex sentences (relative clauses, conditionals, subordination)")
    punctuation = sum(1 for e in errors if e.subcategory == "punctuation")
    if punctuation >= 3:
        band -= 0.25
        neg.append("review punctuation, especially around 'however' and commas")
    if a.word_count < 100:
        band = min(band, 5.5)
        neg.append("the response is too short to show a full range of structures")
    return _finish(band, pos, neg, "Grammatical Range & Accuracy: estimated from error frequency and sentence variety.")


ADVICE_BY_SUBCATEGORY = {
    "article_usage": "Review article rules: a/an for first mention of singular countable nouns, 'the' for specific things, no article for general plurals.",
    "subject_verb_agreement": "Before submitting, underline each subject and check that its verb agrees (people ARE, the number IS).",
    "preposition": "Learn verbs and adjectives together with their prepositions (depend on, responsible for, interested in).",
    "verb_tense": "Check verb forms after auxiliaries and in fixed phrases (did + base verb, look forward to + -ing).",
    "collocation": "Record new words as collocations (make a decision, carry out research) rather than as single words.",
    "spelling": "Keep a personal spelling list - SI has added your misspelled words to your vocabulary reviews.",
    "plural_forms": "Learn common uncountable nouns (information, advice, research) and use 'these' with plurals.",
    "sentence_structure": "Make sure every sentence has a main clause; join 'because/although' clauses to a main clause.",
    "punctuation": "Use a semicolon or full stop before 'however' and a comma after it.",
    "contractions": "Write full forms (do not, it is) in academic writing.",
    "informal_register": "Replace informal words (kids, stuff) with formal equivalents (children, items).",
    "word_formation": "Check word forms: economic vs economical, effect (noun) vs affect (verb).",
}


def heuristic_evaluation(
    analysis: EssayAnalysis,
    errors: list[DetectedError],
    *,
    task_type: str,
    module: str,
    category: str,
) -> HeuristicEvaluation:
    academic = not (module == "general_english" or (module == "general_training" and category == "informal_letter"))
    tr = _task_response(analysis, task_type, module, category)
    cc = _coherence(analysis, task_type, errors)
    lr = _lexical(analysis, module, academic, errors)
    gra = _grammar(analysis, errors)
    criteria = {"task_response": tr, "coherence_cohesion": cc, "lexical_resource": lr, "grammatical_range_accuracy": gra}
    if analysis.word_count < 50:
        for result in criteria.values():
            result.band = min(result.band, 4.0)
    overall = round_band_down(sum(c.band for c in criteria.values()) / 4)

    strengths = [p[0].upper() + p[1:] for c in criteria.values() for p in c.positives][:5]
    weaknesses = [n[0].upper() + n[1:] for c in criteria.values() for n in c.negatives][:6]
    if not strengths:
        strengths = ["You completed the task and produced a full response to work from."]
    advice: list[str] = []
    for sub, _ in Counter(e.subcategory for e in errors).most_common(3):
        if sub in ADVICE_BY_SUBCATEGORY:
            advice.append(ADVICE_BY_SUBCATEGORY[sub])
    weakest = min(criteria.items(), key=lambda kv: kv[1].band)[0]
    advice.extend(
        {
            "task_response": ["Plan before writing: decide your position and two main ideas, each with an example."],
            "coherence_cohesion": ["Give each paragraph one central idea and link sentences with a variety of cohesive devices."],
            "lexical_resource": ["Paraphrase key words from the question and use topic-specific collocations."],
            "grammatical_range_accuracy": ["Combine ideas with relative clauses and conditionals, then proofread for agreement errors."],
        }[weakest]
    )
    return HeuristicEvaluation(
        criteria=criteria,
        overall=clamp_band(overall),
        strengths=strengths,
        weaknesses=weaknesses,
        task_response_issues=tr.negatives,
        cohesion_issues=cc.negatives,
        vocabulary_issues=lr.negatives,
        advice=advice[:5],
    )
