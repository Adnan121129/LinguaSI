"""Google Gemini provider using the Generative Language REST API with JSON output mode."""

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

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, *, timeout: float, max_retries: int) -> None:
        self._api_key = api_key
        self._max_retries = max_retries
        self._client = httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0))

    def complete(self, request: AIRequest) -> AIResult:
        system = request.system
        if request.response_model is not None:
            system += json_instruction(request.response_model)
        body: dict = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]} for m in request.messages],
            "generationConfig": {"maxOutputTokens": request.max_tokens},
        }
        if request.response_model is not None:
            body["generationConfig"]["responseMimeType"] = "application/json"

        data = self._post_with_retries(request.model, body)
        if (data.get("promptFeedback") or {}).get("blockReason"):
            raise AIRefusalError("The request was blocked by the provider's safety filters")
        candidate = (data.get("candidates") or [{}])[0]
        finish = candidate.get("finishReason")
        if finish in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "RECITATION"):
            raise AIRefusalError("The model declined this request")
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts)
        parsed = None
        if request.response_model is not None:
            if finish == "MAX_TOKENS":
                raise AIMalformedOutputError("Gemini output was truncated")
            try:
                parsed = request.response_model.model_validate_json(extract_json_text(text))
            except (pydantic.ValidationError, json.JSONDecodeError, ValueError) as exc:
                raise AIMalformedOutputError("Gemini output failed validation") from exc
        usage = data.get("usageMetadata") or {}
        return AIResult(
            text=text,
            parsed=parsed,
            model=data.get("modelVersion", request.model),
            provider=self.name,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
            stop_reason=finish,
        )

    def _post_with_retries(self, model: str, body: dict) -> dict:
        url = _ENDPOINT.format(model=model)
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._client.post(url, headers=headers, json=body)
            except httpx.TimeoutException as exc:
                if attempt <= self._max_retries:
                    time.sleep(min(2**attempt, 8))
                    continue
                raise AITimeoutError("Gemini request timed out") from exc
            except httpx.HTTPError as exc:
                if attempt <= self._max_retries:
                    time.sleep(min(2**attempt, 8))
                    continue
                raise AIProviderError("Could not reach the Gemini API", retryable=True) from exc

            if response.status_code in (401, 403):
                raise AIConfigError("Gemini API key is invalid or lacks permission")
            if response.status_code == 404:
                raise AIConfigError(f"Gemini model not found: {model}")
            if response.status_code == 429 or response.status_code >= 500:
                if attempt <= self._max_retries:
                    time.sleep(min(2**attempt, 8))
                    continue
                if response.status_code == 429:
                    raise AIRateLimitError("Gemini rate limit reached")
                raise AIProviderError(f"Gemini API error {response.status_code}", retryable=True)
            if response.status_code >= 400:
                raise AIProviderError(f"Gemini rejected the request ({response.status_code})")
            return response.json()
