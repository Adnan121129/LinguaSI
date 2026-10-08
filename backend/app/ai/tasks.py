"""Registry of AI tasks: which agent owns them, which prompt they use, model tier and output budget.

Model selection by task complexity (cost control):
  fast   -> classification, short explanations, hints, follow-up questions, practice items
  strong -> writing/speaking evaluation, content generation and learning-plan generation
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskSpec:
    name: str
    agent: str
    prompt: str
    tier: str  # fast | strong
    max_tokens: int


_TASKS = [
    TaskSpec("writing_evaluate", "writing_examiner", "writing/evaluate", "strong", 12000),
    TaskSpec("writing_hint", "tutor", "writing/hint", "fast", 3000),
    TaskSpec("writing_generate_task", "practice_generator", "writing/generate_task", "fast", 4000),
    TaskSpec("speaking_plan", "speaking_examiner", "speaking/plan", "fast", 3000),
    TaskSpec("speaking_turn", "speaking_examiner", "speaking/next_turn", "fast", 1200),
    TaskSpec("speaking_evaluate", "speaking_examiner", "speaking/evaluate", "strong", 12000),
    TaskSpec("error_classify", "error_analyst", "error_analysis/classify", "fast", 2000),
    TaskSpec("vocab_explain", "vocabulary_engine", "vocabulary/explain", "fast", 1500),
    TaskSpec("reading_generate", "practice_generator", "reading/generate", "strong", 14000),
    TaskSpec("listening_generate", "practice_generator", "listening/generate", "strong", 14000),
    TaskSpec("practice_generate", "practice_generator", "practice/generate", "fast", 4000),
    TaskSpec("tutor_chat", "tutor", "tutor/chat", "fast", 2500),
    TaskSpec("conversation_chat", "tutor", "tutor/conversation", "fast", 1500),
    TaskSpec("plan_daily", "learning_planner", "planner/daily_plan", "fast", 4000),
    TaskSpec("progress_insights", "progress_analyst", "planner/progress_insights", "fast", 2500),
]

TASKS: dict[str, TaskSpec] = {task.name: task for task in _TASKS}
