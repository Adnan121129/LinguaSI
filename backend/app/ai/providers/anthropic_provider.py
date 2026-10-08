"""Anthropic Claude provider (official `anthropic` Python SDK).

Structured outputs use `client.messages.parse(output_format=<PydanticModel>)`, which sends the
schema as `output_config.format` so Claude's output is constrained to valid JSON for the schema;
the SDK then validates it into the Pydantic model. Depth/cost is controlled with
`output_config.effort` (low for cheap classification tasks, higher for evaluations).
"""

from __future__ import annotations

import logging

import pydantic

from app.ai.providers.base import (
    AIConfigError,
    AIMalformedOutputError,
    AIProviderError,
    AIRateLimitError,
    AIRefusalError,
    AIRequest,
    AIResult,
    AITimeoutError,
)

logger = logging.getLogger("linguasi.ai.anthropic")

# Server-side refusal fallback (beta). Haiku has no server-side fallback, so it is never sent there.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, *, timeout: float, max_retries: int, server_fallback: bool = True) -> None:
        import anthropic

        self._sdk = anthropic
        self._server_fallback = server_fallback
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=max_retries)

    def _uses_fallback(self, model: str) -> bool:
        return self._server_fallback and not model.startswith("claude-haiku")

    def complete(self, request: AIRequest) -> AIResult:
        sdk = self._sdk
        kwargs: dict = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.effort:
            kwargs["output_config"] = {"effort": request.effort}
        if self._uses_fallback(request.model):
            kwargs["extra_headers"] = {"anthropic-beta": _FALLBACK_BETA}
            kwargs["extra_body"] = {"fallbacks": "default"}

        try:
            if request.response_model is not None:
                response = self.client.messages.parse(output_format=request.response_model, **kwargs)
            else:
                response = self.client.messages.create(**kwargs)
        except pydantic.ValidationError as exc:
            raise AIMalformedOutputError(f"Structured output failed validation: {exc.error_count()} error(s)") from exc
        except sdk.APITimeoutError as exc:
            raise AITimeoutError("Claude request timed out") from exc
        except sdk.RateLimitError as exc:
            raise AIRateLimitError("Claude rate limit reached") from exc
        except (sdk.AuthenticationError, sdk.PermissionDeniedError) as exc:
            raise AIConfigError("Anthropic API key is invalid or lacks permission") from exc
        except sdk.NotFoundError as exc:
            raise AIConfigError(f"Model not found: {request.model}") from exc
        except sdk.BadRequestError as exc:
            raise AIProviderError(f"Claude rejected the request: {exc.message}"[:280]) from exc
        except sdk.APIStatusError as exc:
            raise AIProviderError(f"Claude API error {exc.status_code}", retryable=exc.status_code >= 500) from exc
        except sdk.APIConnectionError as exc:
            raise AIProviderError("Could not reach the Claude API", retryable=True) from exc

        if response.stop_reason == "refusal":
            raise AIRefusalError("The model declined this request")

        text = "".join(block.text for block in response.content if block.type == "text")
        parsed = None
        if request.response_model is not None:
            parsed = next(
                (block.parsed_output for block in response.content if block.type == "text" and getattr(block, "parsed_output", None) is not None),
                None,
            )
            if parsed is None:
                reason = "truncated output" if response.stop_reason == "max_tokens" else "no structured output"
                raise AIMalformedOutputError(f"Claude returned {reason}")

        usage = response.usage
        return AIResult(
            text=text,
            parsed=parsed,
            model=response.model,
            provider=self.name,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            stop_reason=response.stop_reason,
        )
