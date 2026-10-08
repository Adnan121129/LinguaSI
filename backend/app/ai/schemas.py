"""Pydantic schemas for structured AI outputs.

These models are deliberately lenient (few numeric constraints) so valid-but-imperfect model
output is not rejected; LinguaSI clamps, snaps and validates values in the business logic
(e.g. bands are snapped onto the 0.5 grid, quoted evidence must exist in the source text).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high"]


# --- Shared ------------------------------------------------------------------------------------


class CriterionAssessment(BaseModel):
    band: float = Field(description="AI estimated band for this criterion, 0-9 in steps of 0.5")
    comment: str = Field(description="One or two sentences explaining the band with reference to the learner's text")


class LanguageErrorItem(BaseModel):
    category: str = Field(description="Top-level category from the taxonomy, e.g. grammar, vocabulary, spelling")
    subcategory: str = Field(description="Precise subcategory key from the taxonomy, e.g. subject_verb_agreement")
    original: str = Field(description="The exact erroneous text copied verbatim from the learner's response")
    corrected: str = Field(description="The corrected version of that exact text")
    explanation: str = Field(description="Short learner-friendly explanation of the rule")
    severity: Severity = "medium"


class RecommendedExercise(BaseModel):
    title: str
    focus: str = Field(description="Taxonomy subcategory the exercise targets")
    description: str


# --- Writing -----------------------------------------------------------------------------------


class WritingEvaluationAI(BaseModel):
    task_response: CriterionAssessment = Field(description="Task Response (Task 2) or Task Achievement (Task 1)")
    coherence_cohesion: CriterionAssessment
    lexical_resource: CriterionAssessment
    grammatical_range_accuracy: CriterionAssessment
    strengths: list[str]
    weaknesses: list[str]
    task_response_issues: list[str]
    cohesion_issues: list[str]
    vocabulary_issues: list[str]
    errors: list[LanguageErrorItem]
    advice: list[str]
    recommended_exercise: RecommendedExercise
    summary: str


class WritingHintAI(BaseModel):
    observations: list[str] = Field(description="Weaknesses noticed in the current draft (no rewritten answer)")
    hints: list[str]
    guiding_questions: list[str]
    structure_feedback: str
    vocabulary_direction: list[str] = Field(description="Directions such as topic areas or collocation types to use")
    grammar_notes: list[str]
    encouragement: str


class ChartSeriesAI(BaseModel):
    name: str
    values: list[float]


class WritingVisualAI(BaseModel):
    chart_type: Literal["line", "bar", "pie", "table", "process"]
    title: str
    unit: str = ""
    x_label: str = ""
    y_label: str = ""
    categories: list[str] = []
    series: list[ChartSeriesAI] = []
    steps: list[str] = []


class WritingTaskAI(BaseModel):
    title: str
    topic: str
    category: str
    prompt: str
    instructions: str
    key_points: list[str]
    visual: WritingVisualAI | None = None


# --- Speaking ----------------------------------------------------------------------------------


class Part1FrameAI(BaseModel):
    topic: str
    questions: list[str]


class CueCardAI(BaseModel):
    title: str
    prompt: str
    bullets: list[str]
    rounding_off: str


class SpeakingPlanAI(BaseModel):
    topic: str
    part1: list[Part1FrameAI]
    cue_card: CueCardAI
    part3: list[str]


class SpeakingTurnAI(BaseModel):
    action: Literal["followup", "next"]
    acknowledgement: str = Field(description="A short, neutral examiner phrase such as 'Thank you.'")
    followup_question: str | None = None


class SpeakingEvaluationAI(BaseModel):
    fluency_coherence: CriterionAssessment
    lexical_resource: CriterionAssessment
    grammatical_range_accuracy: CriterionAssessment
    pronunciation: CriterionAssessment | None = Field(default=None, description="Only when audio-derived indicators are provided; otherwise null")
    errors: list[LanguageErrorItem]
    grammar_patterns: list[str]
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]
    relevance_notes: str
    development_notes: str
    summary: str


# --- Reading / listening -----------------------------------------------------------------------


class ParagraphAI(BaseModel):
    label: str
    text: str


class ComprehensionQuestionAI(BaseModel):
    qtype: str
    prompt: str
    options: list[str] = []
    answer: str
    accepted_answers: list[str] = []
    explanation: str
    evidence: str = Field(description="Exact quote from the source text that justifies the answer")
    evidence_paragraph: str | None = None
    word_limit: int | None = None


class ReadingPassageAI(BaseModel):
    title: str
    topic: str
    paragraphs: list[ParagraphAI]
    headings: list[str] = []
    questions: list[ComprehensionQuestionAI]


class SpeakerAI(BaseModel):
    id: str
    name: str
    role: str
    gender: Literal["female", "male"]
    accent: str = "british"


class SegmentAI(BaseModel):
    speaker: str
    text: str


class ListeningScriptAI(BaseModel):
    title: str
    topic: str
    scenario: Literal["conversation", "monologue", "discussion", "lecture"]
    context: str
    speakers: list[SpeakerAI]
    segments: list[SegmentAI]
    questions: list[ComprehensionQuestionAI]


# --- Practice, vocabulary, tutor, planning -----------------------------------------------------


class PracticeItemAI(BaseModel):
    qtype: Literal["multiple_choice", "gap_fill", "error_correction", "transformation"]
    prompt: str
    options: list[str] = []
    answer: str
    accepted_answers: list[str] = []
    explanation: str


class PracticeSetAI(BaseModel):
    title: str
    items: list[PracticeItemAI]


class VocabularyExplanationAI(BaseModel):
    explanation: str
    examples: list[str]
    common_mistake: str
    usage_tip: str


class ErrorClassificationItemAI(BaseModel):
    index: int
    category: str
    subcategory: str


class ErrorClassificationAI(BaseModel):
    items: list[ErrorClassificationItemAI]


class TaskNoteAI(BaseModel):
    task_id: str
    why: str


class DailyPlanAI(BaseModel):
    title: str
    summary: str
    focus: str
    task_notes: list[TaskNoteAI] = []


class ProgressInsightsAI(BaseModel):
    headline: str
    improvements: list[str]
    regressions: list[str]
    recurring_weaknesses: list[str]
    skill_gaps: list[str]
    next_focus: str
