"""OpenAI provider using the Chat Completions REST API with JSON mode.

Structured output: JSON mode + the target JSON Schema in the system prompt, then strict
Pydantic validation in LinguaSI (with a repair attempt in the AI client on failure).
"""

from __future__ import annotations

import json
import time

import httpx
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
    extract_json_text,
    json_instruction,
)

_ENDPOINT = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, *, timeout: float, max_retries: int) -> None:
        self._api_key = api_key
        self._max_retries = max_retries
        self._client = httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0))

    def _supports_reasoning_effort(self, model: str) -> bool:
        return model.startswith(("gpt-5", "o1", "o3", "o4"))

    def complete(self, request: AIRequest) -> AIResult:
        system = request.system
        if request.response_model is not None:
            system += json_instruction(request.response_model)
        body: dict = {
            "model": request.model,
            "messages": [{"role": "system", "content": system}] + [{"role": m.role, "content": m.content} for m in request.messages],
            "max_completion_tokens": request.max_tokens,
        }
        if request.response_model is not None:
            body["response_format"] = {"type": "json_object"}
        if request.effort and self._supports_reasoning_effort(request.model):
            body["reasoning_effort"] = {"xhigh": "high", "max": "high"}.get(request.effort, request.effort)

        data = self._post_with_retries(body)
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        if message.get("refusal"):
            raise AIRefusalError("The model declined this request")
        text = message.get("content") or ""
        parsed = None
        if request.response_model is not None:
            if choice.get("finish_reason") == "length":
                raise AIMalformedOutputError("OpenAI output was truncated")
            try:
                parsed = request.response_model.model_validate_json(extract_json_text(text))
            except (pydantic.ValidationError, json.JSONDecodeError, ValueError) as exc:
                raise AIMalformedOutputError("OpenAI output failed validation") from exc
        usage = data.get("usage") or {}
        return AIResult(
            text=text,
            parsed=parsed,
            model=data.get("model", request.model),
            provider=self.name,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            stop_reason=choice.get("finish_reason"),
        )

    def _post_with_retries(self, body: dict) -> dict:
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._client.post(_ENDPOINT, headers=headers, json=body)
            except httpx.TimeoutException as exc:
                if attempt <= self._max_retries:
                    time.sleep(min(2**attempt, 8))
                    continue
                raise AITimeoutError("OpenAI request timed out") from exc
            except httpx.HTTPError as exc:
                if attempt <= self._max_retries:
                    time.sleep(min(2**attempt, 8))
                    continue
                raise AIProviderError("Could not reach the OpenAI API", retryable=True) from exc

            if response.status_code in (401, 403):
                raise AIConfigError("OpenAI API key is invalid or lacks permission")
            if response.status_code == 404:
                raise AIConfigError(f"OpenAI model not found: {body.get('model')}")
            if response.status_code == 429 or response.status_code >= 500:
                if attempt <= self._max_retries:
                    time.sleep(min(2**attempt, 8))
                    continue
                if response.status_code == 429:
                    raise AIRateLimitError("OpenAI rate limit reached")
                raise AIProviderError(f"OpenAI API error {response.status_code}", retryable=True)
            if response.status_code >= 400:
                raise AIProviderError(f"OpenAI rejected the request ({response.status_code})")
            return response.json()
