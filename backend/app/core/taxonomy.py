"""Mistake taxonomy shared by every module (writing, speaking, vocabulary, reading, listening).

Two levels: a broad *category* (what the learner sees grouped on charts) and a precise
*subcategory* (what SI Core reasons about and what practice content is keyed by).
"""

from __future__ import annotations

from dataclasses import dataclass

CATEGORY_LABELS: dict[str, str] = {
    "grammar": "Grammar",
    "vocabulary": "Vocabulary",
    "spelling": "Spelling",
    "cohesion": "Cohesion",
    "coherence": "Coherence",
    "task_response": "Task Response",
    "academic_style": "Academic Style",
    "fluency": "Fluency",
    "comprehension": "Comprehension",
}


@dataclass(frozen=True)
class Subcategory:
    key: str
    category: str
    label: str
    skill: str  # the learner skill this mistake mainly reflects
    practice_topic: str | None = None  # grammar-bank topic used for repair practice


_SUBCATEGORIES = [
    # Grammar
    Subcategory("subject_verb_agreement", "grammar", "Subject–verb agreement", "grammar", "subject_verb_agreement"),
    Subcategory("article_usage", "grammar", "Article usage", "grammar", "article_usage"),
    Subcategory("preposition", "grammar", "Prepositions", "grammar", "preposition"),
    Subcategory("verb_tense", "grammar", "Verb tense", "grammar", "verb_tense"),
    Subcategory("sentence_structure", "grammar", "Sentence structure", "grammar", "sentence_structure"),
    Subcategory("plural_forms", "grammar", "Plurals & countability", "grammar", "plural_forms"),
    Subcategory("word_order", "grammar", "Word order", "grammar", "word_order"),
    Subcategory("comparatives", "grammar", "Comparatives", "grammar", "comparatives"),
    Subcategory("modal_verbs", "grammar", "Modal verbs", "grammar", "modal_verbs"),
    Subcategory("conditionals", "grammar", "Conditionals", "grammar", "conditionals"),
    Subcategory("passive_voice", "grammar", "Passive voice", "grammar", "passive_voice"),
    Subcategory("relative_clauses", "grammar", "Relative clauses", "grammar", "relative_clauses"),
    Subcategory("punctuation", "grammar", "Punctuation", "grammar", "punctuation"),
    # Vocabulary
    Subcategory("collocation", "vocabulary", "Collocation", "vocabulary", "collocation"),
    Subcategory("word_choice", "vocabulary", "Word choice", "vocabulary", "collocation"),
    Subcategory("word_formation", "vocabulary", "Word formation", "vocabulary", "word_formation"),
    Subcategory("repetition", "vocabulary", "Repetitive vocabulary", "vocabulary", None),
    Subcategory("vocabulary_recall", "vocabulary", "Word meaning recall", "vocabulary", None),
    # Spelling & mechanics
    Subcategory("spelling", "spelling", "Spelling", "vocabulary", None),
    Subcategory("capitalization", "spelling", "Capitalisation", "grammar", "punctuation"),
    # Academic style
    Subcategory("informal_register", "academic_style", "Informal register", "writing", "academic_style"),
    Subcategory("contractions", "academic_style", "Contractions", "writing", "academic_style"),
    # Cohesion & coherence
    Subcategory("linking_words", "cohesion", "Linking words", "writing", "linking_words"),
    Subcategory("referencing", "cohesion", "Referencing", "writing", "linking_words"),
    Subcategory("paragraphing", "coherence", "Paragraphing", "writing", None),
    Subcategory("logical_flow", "coherence", "Logical flow", "writing", None),
    # Task response
    Subcategory("position_clarity", "task_response", "Clear position", "writing", "argument_building"),
    Subcategory("idea_development", "task_response", "Idea development", "writing", "argument_building"),
    Subcategory("relevance", "task_response", "Relevance to the task", "writing", "argument_building"),
    Subcategory("overview", "task_response", "Overview (Task 1)", "writing", None),
    Subcategory("data_accuracy", "task_response", "Data accuracy (Task 1)", "writing", None),
    Subcategory("word_count", "task_response", "Word count", "writing", None),
    Subcategory("letter_purpose", "task_response", "Letter purpose & tone", "writing", None),
    # Speaking fluency
    Subcategory("filler_words", "fluency", "Filler words", "speaking", None),
    Subcategory("hesitation", "fluency", "Hesitation & pauses", "speaking", None),
    Subcategory("short_answers", "fluency", "Underdeveloped answers", "speaking", None),
    # Reading / listening comprehension (by question type)
    Subcategory("true_false_not_given", "comprehension", "True / False / Not Given", "reading"),
    Subcategory("yes_no_not_given", "comprehension", "Yes / No / Not Given", "reading"),
    Subcategory("matching_headings", "comprehension", "Matching headings", "reading"),
    Subcategory("matching_information", "comprehension", "Matching information", "reading"),
    Subcategory("multiple_choice", "comprehension", "Multiple choice", "reading"),
    Subcategory("sentence_completion", "comprehension", "Sentence completion", "reading"),
    Subcategory("summary_completion", "comprehension", "Summary completion", "reading"),
    Subcategory("short_answer", "comprehension", "Short answer", "reading"),
    Subcategory("form_completion", "comprehension", "Form completion", "listening"),
    Subcategory("note_completion", "comprehension", "Note completion", "listening"),
    Subcategory("listening_detail", "comprehension", "Listening for detail", "listening"),
]

SUBCATEGORIES: dict[str, Subcategory] = {sub.key: sub for sub in _SUBCATEGORIES}

# Aliases the AI (or older data) may produce, mapped onto canonical subcategories.
ALIASES: dict[str, str] = {
    "sva": "subject_verb_agreement",
    "agreement": "subject_verb_agreement",
    "subject_verb": "subject_verb_agreement",
    "articles": "article_usage",
    "article": "article_usage",
    "prepositions": "preposition",
    "tense": "verb_tense",
    "tenses": "verb_tense",
    "verb_form": "verb_tense",
    "run_on": "sentence_structure",
    "fragment": "sentence_structure",
    "sentence_fragment": "sentence_structure",
    "plurals": "plural_forms",
    "countability": "plural_forms",
    "uncountable_nouns": "plural_forms",
    "collocations": "collocation",
    "lexical_choice": "word_choice",
    "vocabulary_choice": "word_choice",
    "wrong_word": "word_choice",
    "word_form": "word_formation",
    "spelling_error": "spelling",
    "capitalisation": "capitalization",
    "informal": "informal_register",
    "register": "informal_register",
    "academic_style": "informal_register",
    "contraction": "contractions",
    "linkers": "linking_words",
    "cohesive_devices": "linking_words",
    "connectors": "linking_words",
    "reference": "referencing",
    "pronoun_reference": "referencing",
    "paragraph": "paragraphing",
    "coherence": "logical_flow",
    "position": "position_clarity",
    "development": "idea_development",
    "underdeveloped_ideas": "idea_development",
    "off_topic": "relevance",
    "fillers": "filler_words",
    "pauses": "hesitation",
    "tfng": "true_false_not_given",
    "ynng": "yes_no_not_given",
}


def normalize_subcategory(value: str | None, category: str | None = None) -> str:
    key = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if key in SUBCATEGORIES:
        return key
    if key in ALIASES:
        return ALIASES[key]
    cat = (category or "").strip().lower().replace(" ", "_").replace("-", "_")
    if cat in SUBCATEGORIES:
        return cat
    if cat in ALIASES:
        return ALIASES[cat]
    fallback = {
        "grammar": "sentence_structure",
        "vocabulary": "word_choice",
        "spelling": "spelling",
        "cohesion": "linking_words",
        "coherence": "logical_flow",
        "task_response": "idea_development",
        "academic_style": "informal_register",
        "fluency": "hesitation",
    }
    return fallback.get(cat, "sentence_structure")


def category_for(subcategory: str) -> str:
    sub = SUBCATEGORIES.get(subcategory)
    return sub.category if sub else "grammar"


def label_for(subcategory: str) -> str:
    sub = SUBCATEGORIES.get(subcategory)
    return sub.label if sub else subcategory.replace("_", " ").title()


def skill_for(subcategory: str, source: str | None = None) -> str:
    sub = SUBCATEGORIES.get(subcategory)
    if sub and sub.category == "comprehension" and source in ("reading", "listening"):
        return source
    return sub.skill if sub else "grammar"


def practice_topic_for(subcategory: str) -> str | None:
    sub = SUBCATEGORIES.get(subcategory)
    return sub.practice_topic if sub else None


SEVERITIES = ("low", "medium", "high")
