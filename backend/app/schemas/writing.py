from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ActivityOutcome, ORMModel


class WritingTaskOut(ORMModel):
    id: int
    task_type: str
    module: str
    category: str
    topic: str
    title: str
    prompt: str
    instructions: str
    visual: dict | None
    min_words: int
    time_limit_minutes: int
    difficulty: int
    source: str


class GenerateTaskRequest(BaseModel):
    module: str = Field(pattern="^(academic|general_training|general_english)$")
    task_type: str = Field(pattern="^(task1|task2|general)$")
    category: str | None = Field(default=None, max_length=40)
    topic: str | None = Field(default=None, max_length=60)
    difficulty: int | None = Field(default=None, ge=1, le=5)


class GenerateTaskResponse(BaseModel):
    task: WritingTaskOut
    notice: str | None = None


class StartSubmissionRequest(BaseModel):
    task_id: int
    mode: str = Field(default="tutor", pattern="^(tutor|exam)$")


class AutosaveRequest(BaseModel):
    content: str = Field(max_length=20000)
    time_spent_seconds: int = Field(default=0, ge=0, le=36000)


class AutosaveResponse(BaseModel):
    saved_at: datetime
    word_count: int


class HintRequest(BaseModel):
    question: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, max_length=20000)


class HintResponse(BaseModel):
    observations: list[str]
    hints: list[str]
    guiding_questions: list[str]
    structure_feedback: str
    vocabulary_direction: list[str]
    grammar_notes: list[str]
    encouragement: str
    hints_used: int


class EvaluateRequest(BaseModel):
    submission_id: int
    content: str | None = Field(default=None, max_length=20000)
    time_spent_seconds: int | None = Field(default=None, ge=0, le=36000)


class CriterionOut(BaseModel):
    key: str
    label: str
    band: float
    comment: str


class WritingErrorOut(ORMModel):
    id: int
    category: str
    subcategory: str
    original: str
    corrected: str
    explanation: str
    severity: str
    start_offset: int | None
    end_offset: int | None
    repeated: bool
    mistake_id: int | None
    source: str


class WritingEvaluationOut(BaseModel):
    id: int
    label: str = "AI Estimated Band"
    overall_band: float
    criteria: list[CriterionOut]
    strengths: list[str]
    weaknesses: list[str]
    task_response_issues: list[str]
    cohesion_issues: list[str]
    vocabulary_issues: list[str]
    advice: list[str]
    summary: str
    recommended_exercise: dict
    metrics: dict
    errors: list[WritingErrorOut]
    provider: str
    model: str
    is_mock: bool
    created_at: datetime
    disclaimer: str = "AI practice evaluation - not an official IELTS score."


class PreviousAttempt(BaseModel):
    submission_id: int
    overall_band: float
    criteria: dict[str, float]
    evaluated_at: datetime | None
    same_task: bool


class SubmissionOut(BaseModel):
    id: int
    task: WritingTaskOut
    mode: str
    content: str
    word_count: int
    time_spent_seconds: int
    status: str
    hints_used: int
    tutor_notes: list[dict]
    failure_reason: str | None
    autosaved_at: datetime | None
    submitted_at: datetime | None
    evaluated_at: datetime | None
    created_at: datetime
    key_points: list[str] | None = None
    evaluation: WritingEvaluationOut | None = None
    previous: PreviousAttempt | None = None


class EvaluateResponse(BaseModel):
    submission: SubmissionOut
    outcome: ActivityOutcome


class SubmissionSummary(BaseModel):
    id: int
    task_id: int
    task_title: str
    task_type: str
    module: str
    category: str
    mode: str
    status: str
    word_count: int
    overall_band: float | None
    created_at: datetime
    evaluated_at: datetime | None
