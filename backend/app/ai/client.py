"""The single entry point every SI agent uses to talk to an AI model.

Responsibilities:
  * render the centralised prompt for a task and pick the model by task tier
  * route to the configured provider (Anthropic / OpenAI / Gemini) or the deterministic mock
  * validate structured output and make one repair attempt on malformed output
  * log provider, model, latency, success/failure, token usage and error category
"""

from __future__ import annotations

import logging
import time
from typing import Any, TypeVar

from pydantic import BaseModel

from app.ai import prompts
from app.ai.providers.base import AIError, AIMalformedOutputError, AIMessage, AIProvider, AIRequest, AIResult
from app.ai.tasks import TASKS
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import AIInteractionLog

logger = logging.getLogger("linguasi.ai")

M = TypeVar("M", bound=BaseModel)


def build_provider() -> AIProvider:
    provider = settings.effective_ai_provider
    if provider == "anthropic":
        from app.ai.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            settings.anthropic_api_key or "",
            timeout=settings.ai_timeout_seconds,
            max_retries=settings.ai_max_retries,
            server_fallback=settings.anthropic_server_fallback,
        )
    if provider == "openai":
        from app.ai.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(settings.openai_api_key or "", timeout=settings.ai_timeout_seconds, max_retries=settings.ai_max_retries)
    if provider == "gemini":
        from app.ai.providers.gemini_provider import GeminiProvider

        return GeminiProvider(settings.gemini_api_key or "", timeout=settings.ai_timeout_seconds, max_retries=settings.ai_max_retries)
    from app.ai.mock import MockProvider

    return MockProvider()


class AIClient:
    def __init__(self) -> None:
        self._provider: AIProvider | None = None

    @property
    def provider(self) -> AIProvider:
        if self._provider is None:
            self._provider = build_provider()
        return self._provider

    def set_provider(self, provider: AIProvider | None) -> None:
        """Swap the provider (used by tests to simulate failures, and after settings changes)."""
        self._provider = provider

    @property
    def is_mock(self) -> bool:
        return self.provider.name == "mock"

    @property
    def provider_name(self) -> str:
        return self.provider.name

    def model_for(self, task: str) -> str:
        return settings.model_for_tier(TASKS[task].tier) if not self.is_mock else f"mock-{TASKS[task].tier}"

    def generate(
        self,
        task: str,
        variables: dict[str, Any],
        *,
        response_model: type[M] | None = None,
        user_id: int | None = None,
        history: list[AIMessage] | None = None,
        mock_context: dict[str, Any] | None = None,
    ) -> AIResult:
        """Run an AI task. Raises an AIError subclass when the task cannot be completed."""
        spec = TASKS[task]
        system, user_message = prompts.render(spec.prompt, variables)
        messages = _normalise_history(list(history or []) + [AIMessage("user", user_message)])
        model = self.model_for(task)
        effort = settings.ai_effort_fast if spec.tier == "fast" else settings.ai_effort_strong
        request = AIRequest(
            task=task,
            system=system,
            messages=messages,
            model=model,
            tier=spec.tier,
            max_tokens=spec.max_tokens,
            effort=effort,
            response_model=response_model,
            mock_context=mock_context if mock_context is not None else variables,
        )

        attempts = 0
        started = time.perf_counter()
        while True:
            attempts += 1
            try:
                result = self.provider.complete(request)
            except AIMalformedOutputError as exc:
                if attempts <= settings.ai_repair_attempts and response_model is not None:
                    logger.warning("Malformed output for task=%s (attempt %s); requesting repair", task, attempts)
                    request.messages = _normalise_history(
                        request.messages
                        + [
                            AIMessage(
                                "user",
                                "Your previous reply could not be used because it did not match the required JSON "
                                f"structure ({exc}). Reply again with only the complete JSON object.",
                            )
                        ]
                    )
                    continue
                self._log(spec, model, user_id, started, attempts, error=exc)
                raise
            except AIError as exc:
                self._log(spec, model, user_id, started, attempts, error=exc)
                raise
            except Exception as exc:  # unexpected provider bug: normalise into an AIError
                self._log(spec, model, user_id, started, attempts, error=exc)
                raise AIError(f"Unexpected AI failure: {type(exc).__name__}") from exc
            self._log(spec, result.model or model, user_id, started, attempts, result=result, request=request)
            return result

    def generate_model(self, task: str, variables: dict[str, Any], response_model: type[M], **kwargs: Any) -> tuple[M, AIResult]:
        result = self.generate(task, variables, response_model=response_model, **kwargs)
        if result.parsed is None:
            raise AIMalformedOutputError(f"{task}: provider returned no structured output")
        return result.parsed, result  # type: ignore[return-value]

    def _log(
        self,
        spec,
        model: str,
        user_id: int | None,
        started: float,
        attempts: int,
        *,
        result: AIResult | None = None,
        error: Exception | None = None,
        request: AIRequest | None = None,
    ) -> None:
        latency_ms = int((time.perf_counter() - started) * 1000)
        category = getattr(error, "category", "unexpected") if error else None
        if error:
            logger.warning(
                "AI task failed task=%s provider=%s model=%s category=%s latency=%sms",
                spec.name,
                self.provider_name,
                model,
                category,
                latency_ms,
            )
        debug_payload = None
        if settings.ai_log_content and request is not None and result is not None:
            debug_payload = {
                "system_chars": len(request.system),
                "prompt_preview": request.messages[-1].content[:2000],
                "response_preview": (result.text or "")[:2000],
            }
        try:
            db = SessionLocal()
            try:
                db.add(
                    AIInteractionLog(
                        user_id=user_id,
                        agent=spec.agent,
                        task=spec.name,
                        provider=self.provider_name,
                        model=(model or "")[:60],
                        tier=spec.tier,
                        latency_ms=latency_ms,
                        success=error is None,
                        error_category=category,
                        error_message=str(error)[:300] if error else None,
                        input_tokens=result.input_tokens if result else None,
                        output_tokens=result.output_tokens if result else None,
                        attempts=attempts,
                        is_mock=self.is_mock,
                        debug_payload=debug_payload,
                    )
                )
                db.commit()
            finally:
                db.close()
        except Exception:  # observability must never break the learner's request
            logger.warning("Could not write AI interaction log", exc_info=True)


def _normalise_history(messages: list[AIMessage]) -> list[AIMessage]:
    """Providers expect the conversation to start with the user and to alternate roles."""
    if messages and messages[0].role == "assistant":
        messages = [AIMessage("user", "(The conversation begins.)")] + messages
    merged: list[AIMessage] = []
    for message in messages:
        if merged and merged[-1].role == message.role:
            merged[-1] = AIMessage(message.role, f"{merged[-1].content}\n\n{message.content}")
        else:
            merged.append(message)
    return merged


ai_client = AIClient()
