"""Provider-neutral request/response types and the AI error taxonomy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel


class AIError(Exception):
    category = "provider_error"
    retryable = False

    def __init__(self, message: str = "AI provider error", *, retryable: bool | None = None) -> None:
        super().__init__(message)
        if retryable is not None:
            self.retryable = retryable


class AITimeoutError(AIError):
    category = "timeout"
    retryable = True


class AIRateLimitError(AIError):
    category = "rate_limited"
    retryable = True


class AIProviderError(AIError):
    category = "provider_error"


class AIConfigError(AIError):
    category = "config_error"


class AIMalformedOutputError(AIError):
    category = "malformed_output"


class AIRefusalError(AIError):
    category = "refusal"


@dataclass
class AIMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass
class AIRequest:
    task: str
    system: str
    messages: list[AIMessage]
    model: str
    tier: str
    max_tokens: int
    effort: str | None = None
    response_model: type[BaseModel] | None = None
    mock_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class AIResult:
    text: str
    parsed: BaseModel | None
    model: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    stop_reason: str | None = None


class AIProvider(Protocol):
    name: str

    def complete(self, request: AIRequest) -> AIResult: ...


def json_instruction(response_model: type[BaseModel]) -> str:
    """Instruction appended for providers without native schema-constrained decoding."""
    import json

    schema = json.dumps(response_model.model_json_schema(), separators=(",", ":"))
    return f"\n\nRespond with ONLY a single JSON object (no markdown fences, no commentary) that validates against this JSON Schema:\n{schema}"


def extract_json_text(text: str) -> str:
    """Pull a JSON object out of a model reply that may contain code fences or stray prose."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        return stripped[start : end + 1]
    return stripped
