"""Deterministic mock AI provider (AI_MOCK_MODE=true).

The mock does not pretend to be an LLM. Each AI task has a handler that produces a valid,
useful structured result from LinguaSI's own analytics engines and curated content bank:

  * writing/speaking evaluation  -> rubric-inspired heuristics over measured features
  * hints and tutoring           -> rule-based diagnosis + grammar knowledge base
  * task/plan generation         -> templates and the curated content bank
  * planning and insights        -> templated narratives over real learner data

The handlers receive structured `mock_context` (not the rendered prompt), so their output is
reproducible for tests and demos while the rest of the pipeline (validation, storage, SI Core
updates) is identical to real-provider mode.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from app.ai.providers.base import AIProviderError, AIRequest, AIResult

MockHandler = Callable[[dict[str, Any]], BaseModel | str]
_HANDLERS: dict[str, MockHandler] = {}


def mock_handler(task: str) -> Callable[[MockHandler], MockHandler]:
    def register(fn: MockHandler) -> MockHandler:
        _HANDLERS[task] = fn
        return fn

    return register


class MockProvider:
    name = "mock"

    def complete(self, request: AIRequest) -> AIResult:
        _ensure_handlers_loaded()
        handler = _HANDLERS.get(request.task)
        if handler is None:
            raise AIProviderError(f"No mock handler for task '{request.task}'")
        output = handler(request.mock_context)
        if isinstance(output, BaseModel):
            if request.response_model is not None and not isinstance(output, request.response_model):
                output = request.response_model.model_validate(output.model_dump())
            return AIResult(text=output.model_dump_json(), parsed=output, model=request.model, provider=self.name)
        return AIResult(text=str(output), parsed=None, model=request.model, provider=self.name)


_loaded = False


def _ensure_handlers_loaded() -> None:
    global _loaded
    if not _loaded:
        from app.ai.mock import content, planner, speaking, tutor, writing  # noqa: F401  (registers handlers)

        _loaded = True
