"""Mock handlers for the Writing Examiner, writing tutor hints and writing task generation."""

from __future__ import annotations

import random
from collections import Counter

from app.ai.mock import mock_handler
from app.ai.schemas import (
    ChartSeriesAI,
    CriterionAssessment,
    LanguageErrorItem,
    RecommendedExercise,
    WritingEvaluationAI,
    WritingHintAI,
    WritingTaskAI,
    WritingVisualAI,
)
from app.analytics.grammar_rules import detect_errors
from app.analytics.writing_metrics import analyze_essay, heuristic_evaluation
from app.core.taxonomy import label_for, practice_topic_for
from app.services.content import writing_templates

CRITERION_TO_FOCUS = {
    "task_response": ("idea_development", "Argument Builder", "Practise building clear positions and developed paragraphs."),
    "coherence_cohesion": ("linking_words", "Linking Words Workout", "Practise choosing precise linking words for contrast, result and addition."),
    "lexical_resource": ("collocation", "Collocation Booster", "Practise natural word partnerships for academic topics."),
    "grammatical_range_accuracy": ("sentence_structure", "Sentence Builder", "Practise complex sentences that stay accurate."),
}


@mock_handler("writing_evaluate")
def evaluate(ctx: dict) -> WritingEvaluationAI:
    analysis = ctx["analysis"]
    errors = ctx["rule_errors"]
    task = ctx["task"]
    recurring = set(ctx.get("recurring", []))
    h = heuristic_evaluation(analysis, errors, task_type=task["task_type"], module=task["module"], category=task["category"])
    items = []
    for err in errors[:15]:
        note = " This is a recurring pattern in your recent work." if err.subcategory in recurring else ""
        items.append(
            LanguageErrorItem(
                category=err.category,
                subcategory=err.subcategory,
                original=err.original,
                corrected=err.corrected,
                explanation=err.explanation + note,
                severity=err.severity,
            )
        )
    # Follow-up exercise: the most frequent fixable error pattern, otherwise the weakest criterion.
    counts = Counter(e.subcategory for e in errors if practice_topic_for(e.subcategory))
    if counts and counts.most_common(1)[0][1] >= 2:
        focus = counts.most_common(1)[0][0]
        exercise = RecommendedExercise(
            title=f"5-minute {label_for(focus)} Repair",
            focus=focus,
            description=f"You made {counts[focus]} {label_for(focus).lower()} errors in this response. Repair them with a short targeted drill.",
        )
    else:
        weakest = min(h.criteria.items(), key=lambda kv: kv[1].band)[0]
        focus, title, desc = CRITERION_TO_FOCUS[weakest]
        exercise = RecommendedExercise(title=title, focus=focus, description=desc)

    c = h.criteria
    summary = (
        f"AI practice evaluation: estimated band {h.overall:g}. "
        + (f"Your strongest area is {_criterion_name(max(c, key=lambda k: c[k].band))}; " if c else "")
        + f"the area to focus on next is {_criterion_name(min(c, key=lambda k: c[k].band))}. "
        + "This is an AI estimate for practice, not an official IELTS score."
    )
    return WritingEvaluationAI(
        task_response=CriterionAssessment(band=c["task_response"].band, comment=c["task_response"].comment),
        coherence_cohesion=CriterionAssessment(band=c["coherence_cohesion"].band, comment=c["coherence_cohesion"].comment),
        lexical_resource=CriterionAssessment(band=c["lexical_resource"].band, comment=c["lexical_resource"].comment),
        grammatical_range_accuracy=CriterionAssessment(band=c["grammatical_range_accuracy"].band, comment=c["grammatical_range_accuracy"].comment),
        strengths=h.strengths,
        weaknesses=h.weaknesses,
        task_response_issues=h.task_response_issues,
        cohesion_issues=h.cohesion_issues,
        vocabulary_issues=h.vocabulary_issues,
        errors=items,
        advice=h.advice,
        recommended_exercise=exercise,
        summary=summary,
    )


def _criterion_name(key: str) -> str:
    return {
        "task_response": "Task Response",
        "coherence_cohesion": "Coherence & Cohesion",
        "lexical_resource": "Lexical Resource",
        "grammatical_range_accuracy": "Grammatical Range & Accuracy",
    }[key]


@mock_handler("writing_hint")
def hint(ctx: dict) -> WritingHintAI:
    draft: str = ctx.get("draft", "") or ""
    task = ctx["task"]
    question = (ctx.get("question") or "").strip().lower()
    academic = task["module"] != "general_english"
    errors = detect_errors(draft, academic=academic) if draft.strip() else []
    a = analyze_essay(
        draft,
        task_type=task["task_type"],
        module=task["module"],
        prompt=task["prompt"],
        key_points=task.get("key_points"),
        min_words=task.get("min_words", 250),
        errors=errors,
    )
    is_report = task["task_type"] == "task1" and task["module"] == "academic"
    is_letter = task["task_type"] == "task1" and task["module"] == "general_training"
    observations: list[str] = []
    hints: list[str] = []
    questions: list[str] = []

    if a.word_count < 40:
        observations.append("Your draft is just getting started - a quick plan will make the rest much easier.")
        if is_report:
            hints.append("Start with one sentence that paraphrases what the visual shows, then plan your overview.")
            questions.append("What is the single biggest change or difference you can see in the visual?")
        elif is_letter:
            hints.append("Open with the purpose of your letter in the first sentence.")
            questions.append("Who are you writing to, and how formal should your tone be?")
        else:
            hints.append("Decide your position first, then choose two main reasons that support it.")
            questions.append("If you had to answer the question in one sentence, what would you say?")
    else:
        if is_report and not a.overview:
            observations.append("There is no overview sentence yet.")
            hints.append("Add an overview that summarises the main trends without detailed numbers - 'Overall, ...' is a good start.")
        if is_report and task.get("category") != "process" and a.numbers_count < 3:
            observations.append("Few figures from the visual are mentioned so far.")
            hints.append("Support your key points with specific figures, and compare them rather than listing.")
        if not is_report and not is_letter and task.get("category") in ("opinion", "discussion", "two_part") and not a.position_statement:
            observations.append("Your position is not stated clearly yet.")
            hints.append("Make your opinion explicit in the introduction so every paragraph can support it.")
        if not is_report and not is_letter and not a.examples and a.word_count > 120:
            observations.append("Your ideas are not yet supported with examples.")
            hints.append("After each main point, add a specific example or a consequence.")
        if is_letter and not a.purpose_statement:
            observations.append("The purpose of the letter is not stated near the start.")
            hints.append("State why you are writing in the first paragraph.")
        if a.paragraph_count <= 1 and a.word_count > 80:
            observations.append("Everything is in one paragraph.")
            hints.append("Split your ideas into paragraphs, each with one central idea.")
        if a.overused_linkers:
            word, count = a.overused_linkers[0]
            observations.append(f"You have used '{word}' {count} times.")
            hints.append("Vary your linking words: try 'furthermore', 'in contrast' or 'as a result' where they fit.")
        if a.key_point_coverage < 0.5 and task.get("key_points"):
            questions.append("Look back at the task: have you covered every part of the question?")
    if not questions:
        questions = [
            "Which of your points is the strongest, and have you explained why?" if not is_report else "Which comparison in the data is most striking?",
            "Could a reader predict your conclusion from your introduction?" if not is_report else "Have you grouped similar information together?",
        ]
    if a.word_count and a.word_count < task.get("min_words", 250):
        questions.append(f"You have {a.word_count} words; how will you reach at least {task.get('min_words', 250)}?")

    grammar_notes = []
    for err in errors[:3]:
        grammar_notes.append(f"Check '{err.original}': {err.explanation}")
    recurring = ctx.get("recurring", [])
    if recurring and not grammar_notes:
        grammar_notes.append(f"Keep an eye on {label_for(recurring[0]).lower()} - it has appeared in your recent work.")

    vocab_direction = ctx.get("topic_vocab") or []
    direction = (
        [f"Use topic-specific vocabulary about {task.get('topic', 'the topic')}, for example: {', '.join(vocab_direction[:4])}."] if vocab_direction else []
    )
    if is_report:
        direction.append("Vary verbs of change: rise, climb, decline, fluctuate, level off - with adverbs such as sharply or gradually.")
    else:
        direction.append("Paraphrase the key words in the question instead of copying them.")

    if question:
        if "overview" in question:
            hints.insert(0, "An overview gives the big picture in one or two sentences: the main trend, the highest/lowest, or the overall change.")
        elif "conclusion" in question:
            hints.insert(0, "A conclusion restates your position and main reasons in new words - no new ideas.")
        elif "introduction" in question or "start" in question:
            hints.insert(0, "Paraphrase the question, then add your thesis (position) in one sentence.")
        elif "word" in question or "vocab" in question:
            hints.insert(0, "Think about the people, causes and effects involved in this topic and list 5 precise nouns and verbs before writing.")
        else:
            hints.insert(0, "Good question. Focus on one paragraph at a time: main point, explanation, example.")

    structure = f"Your draft has {a.paragraph_count} paragraph{'s' if a.paragraph_count != 1 else ''} and {a.word_count} words. " + (
        "A strong Task 1 report has an introduction, an overview and two detail paragraphs."
        if is_report
        else "A strong letter has an opening, a paragraph for each bullet point and a suitable closing."
        if is_letter
        else "A strong essay has an introduction with your position, two or three body paragraphs and a conclusion."
    )
    return WritingHintAI(
        observations=observations[:3] or ["Your draft is on track - keep building on your plan."],
        hints=hints[:3] or ["Re-read your last paragraph and check that every sentence supports its main idea."],
        guiding_questions=questions[:3],
        structure_feedback=structure,
        vocabulary_direction=direction[:3],
        grammar_notes=grammar_notes,
        encouragement="Keep going - thinking through these questions is exactly how strong answers are built.",
    )


GT_LETTERS = [
    (
        "formal_letter",
        "daily_life",
        "Problem with a hotel stay",
        "You recently stayed in a hotel and had several problems during your visit. Write a letter to the hotel manager.",
        ["explain when and why you stayed at the hotel", "describe the problems you had", "say what you would like the manager to do"],
    ),
    (
        "formal_letter",
        "work",
        "Applying for a part-time job",
        "You have seen an advertisement for a part-time job at a local museum. Write a letter to the manager.",
        ["say which job you are applying for", "describe your relevant experience", "explain when you are available to work"],
    ),
    (
        "semi_formal_letter",
        "daily_life",
        "Organising a community event",
        "Your neighbourhood is planning a summer event. Write a letter to your local councillor.",
        ["describe the event", "explain how it will benefit the community", "ask for help with organising it"],
    ),
    (
        "informal_letter",
        "travel",
        "Thanking a friend",
        "You recently stayed with a friend for a few days. Write a letter to your friend.",
        ["thank them for their hospitality", "describe what you enjoyed most", "invite them to visit you"],
    ),
    (
        "informal_letter",
        "daily_life",
        "Recommending a course",
        "A friend wants to learn a new skill and has asked for your advice. Write a letter to your friend.",
        ["recommend a course you know about", "explain why it would suit them", "suggest how they could fit it into their schedule"],
    ),
]

GENERAL_PROMPTS = [
    (
        "email",
        "daily_life",
        "An email to a friend",
        "Write an email to a friend telling them about a new hobby you have started. Say what it is, why you chose it and how you feel about it.",
        ["the hobby", "why you chose it", "how you feel"],
    ),
    (
        "description",
        "travel",
        "A memorable trip",
        "Describe a memorable trip you have taken. Say where you went, who you were with and what made it special.",
        ["where", "who with", "why special"],
    ),
    (
        "general_opinion",
        "technology",
        "Phones at dinner",
        "Should people use their phones while eating with family or friends? Give your opinion with reasons and examples.",
        ["clear opinion", "reasons", "examples"],
    ),
    (
        "review",
        "daily_life",
        "A restaurant review",
        "Write a short review of a café or restaurant you know. Describe the food, the atmosphere and the service.",
        ["food", "atmosphere", "service"],
    ),
]

PROCESS_TEMPLATES = [
    (
        "environment",
        "How rainwater is collected and reused",
        [
            "Rain falls on the roof of a house",
            "Water flows through gutters into a filter",
            "Leaves and dirt are removed by the filter",
            "Clean water is stored in an underground tank",
            "A pump moves water to the house",
            "Water is used for toilets and gardens",
        ],
    ),
    (
        "environment",
        "How paper is recycled",
        [
            "Used paper is collected from homes and offices",
            "Paper is sorted by type and quality",
            "Paper is mixed with water to form pulp",
            "Ink is removed from the pulp",
            "Pulp is pressed and rolled into sheets",
            "Sheets are dried and cut into rolls",
        ],
    ),
    (
        "economy",
        "How chocolate is produced",
        [
            "Cocoa pods are harvested from trees",
            "Beans are removed and left to ferment",
            "Beans are dried in the sun",
            "Dried beans are roasted",
            "Roasted beans are ground into cocoa paste",
            "Paste is mixed with sugar and milk",
            "Mixture is poured into moulds and cooled",
        ],
    ),
]

CHART_FOR_CATEGORY = {"line_graph": "line", "bar_chart": "bar", "pie_chart": "pie", "table": "table"}


@mock_handler("writing_generate_task")
def generate_task(ctx: dict) -> WritingTaskAI:
    rng = random.Random(ctx.get("seed", 0))
    module = ctx.get("module", "academic")
    task_type = ctx.get("task_type", "task2")
    topic = ctx.get("topic")
    avoid = set(ctx.get("avoid_topics") or [])
    templates = writing_templates()

    if module == "general_english":
        options = [g for g in GENERAL_PROMPTS if g[1] not in avoid] or GENERAL_PROMPTS
        cat, top, title, prompt, kp = rng.choice(options)
        return WritingTaskAI(title=title, topic=top, category=cat, prompt=prompt, instructions="Write at least 120 words.", key_points=kp)

    if task_type == "task1" and module == "general_training":
        options = [g for g in GT_LETTERS if (not ctx.get("category") or g[0] == ctx["category"])] or GT_LETTERS
        cat, top, title, situation, bullets = rng.choice(options)
        prompt = situation + "\n\nIn your letter:\n" + "\n".join(f"- {b}" for b in bullets)
        return WritingTaskAI(
            title=title,
            topic=top,
            category=cat,
            prompt=prompt,
            instructions="Write at least 150 words. You do NOT need to write any addresses. Begin your letter as appropriate.",
            key_points=bullets,
        )

    if task_type == "task1":
        category = ctx.get("category") or rng.choice(["line_graph", "bar_chart", "pie_chart", "table", "process"])
        if category == "process":
            top, title, steps = rng.choice(PROCESS_TEMPLATES)
            return WritingTaskAI(
                title=title,
                topic=top,
                category="process",
                prompt=f"The diagram below shows {title[0].lower() + title[1:]}.",
                instructions="Summarise the information by selecting and reporting the main features. Write at least 150 words.",
                key_points=["overview of the number of stages", "describe every stage in order", "use the passive voice and sequencers"],
                visual=WritingVisualAI(chart_type="process", title=title, steps=steps),
            )
        chart_type = CHART_FOR_CATEGORY.get(category, "line")
        candidates = [m for m in templates["task1_metrics"] if m["chart_type"] == chart_type] or templates["task1_metrics"]
        spec = rng.choice(candidates)
        title = spec["title"]
        for placeholder in ("activity", "item"):
            if placeholder in spec:
                title = title.replace("{" + placeholder + "}", rng.choice(spec[placeholder]))
        visual = _make_chart(spec, chart_type, title, rng)
        names = ", ".join(s.name for s in visual.series)
        prompt_lead = {"line": "The line graph", "bar": "The bar chart", "pie": "The pie charts", "table": "The table"}[chart_type]
        return WritingTaskAI(
            title=title,
            topic=spec["topic"],
            category=category,
            prompt=f"{prompt_lead} below shows {title[0].lower() + title[1:]} ({names}).",
            instructions="Summarise the information by selecting and reporting the main features, and make comparisons where relevant. Write at least 150 words.",
            key_points=[
                "a clear overview of the main trends or differences",
                "the highest and lowest values",
                "accurate figures supporting key points",
                "comparisons between groups",
            ],
            visual=visual,
        )

    category = ctx.get("category") or rng.choice(list(templates["task2_forms"]))
    topics = templates["topics"]
    topic_key = topic if topic in topics else rng.choice([t for t in topics if t not in avoid] or list(topics))
    bank = topics[topic_key]
    form = rng.choice(templates["task2_forms"].get(category, templates["task2_forms"]["opinion"]))
    idx = rng.randrange(len(bank["claims"]))
    prompt = form.format(
        claim=bank["claims"][idx],
        counter=bank["counters"][idx % len(bank["counters"])],
        trend=rng.choice(bank["trends"]),
        problem=rng.choice(bank["problems"]),
    )
    key_points = {
        "opinion": [
            "a clear position stated in the introduction",
            "two well-developed supporting reasons",
            "relevant examples",
            "a conclusion that restates the position",
        ],
        "discussion": ["a balanced discussion of the first view", "a balanced discussion of the second view", "your own opinion clearly stated", "examples"],
        "advantages_disadvantages": ["main advantages", "main disadvantages", "a clear judgement on which outweighs", "examples"],
        "problem_solution": ["main causes", "practical solutions linked to the causes", "examples"],
        "two_part": ["a full answer to the first question", "a full answer to the second question", "examples"],
    }.get(category, ["clear position", "developed ideas", "examples"])
    return WritingTaskAI(
        title=f"{topic_key.title()}: {category.replace('_', ' ')} essay",
        topic=topic_key,
        category=category,
        prompt=prompt,
        instructions="Give reasons for your answer and include any relevant examples from your own knowledge or experience. Write at least 250 words.",
        key_points=key_points,
    )


def _make_chart(spec: dict, chart_type: str, title: str, rng: random.Random) -> WritingVisualAI:
    names = spec["series_names"]
    if chart_type == "line":
        years = [str(y) for y in range(2000 + rng.choice([0, 4]), 2025, 5)]
        series = []
        lo, hi = spec.get("start", [10, 40])
        g_lo, g_hi = spec.get("growth", [1, 6])
        for name in names:
            value = rng.randint(lo, hi)
            growth = rng.uniform(g_lo, g_hi) * rng.choice([1, 1, 1, -0.4])
            values = []
            for _ in years:
                values.append(max(1, min(99, round(value))))
                value += growth + rng.uniform(-2, 2)
            series.append(ChartSeriesAI(name=name, values=values))
        return WritingVisualAI(
            chart_type="line", title=title, unit=spec.get("unit", ""), x_label="Year", y_label=spec.get("unit", ""), categories=years, series=series
        )
    if chart_type == "pie":
        cats = spec["categories"]
        series = []
        for name in names:
            weights = [rng.uniform(0.5, 3.0) for _ in cats]
            total = sum(weights)
            values = [round(w / total * 100) for w in weights]
            values[0] += 100 - sum(values)
            series.append(ChartSeriesAI(name=name, values=values))
        return WritingVisualAI(chart_type="pie", title=title, unit="%", categories=cats, series=series)
    lo, hi = spec.get("range", [10, 60])
    cats = spec["categories"]
    decimals = 1 if hi < 20 else 0
    series = [ChartSeriesAI(name=n, values=[round(rng.uniform(lo, hi), decimals) for _ in cats]) for n in names]
    return WritingVisualAI(
        chart_type=chart_type, title=title, unit=spec.get("unit", ""), x_label="", y_label=spec.get("unit", ""), categories=cats, series=series
    )
