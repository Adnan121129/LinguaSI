"""Speech-to-text and text-to-speech provider abstractions.

STT
  * openai - OpenAI transcription API (STT_PROVIDER=openai, needs OPENAI_API_KEY)
  * mock   - no server-side transcription; clients send a transcript produced by the browser's
             speech recognition or typed by the learner. The UI says which source was used.

TTS
  * openai - OpenAI speech API, one audio file per script segment (TTS_PROVIDER=openai)
  * mock   - no server audio; clients read scripts aloud with the device's speech synthesis
             (Web Speech API in browsers, expo-speech on mobile), using the speaker metadata.

Other cloud providers (Google, Azure, Deepgram, ElevenLabs...) can be added by implementing
the same two small interfaces.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger("linguasi.speech")


class SpeechUnavailableError(Exception):
    """Raised when speech processing is not configured or the provider failed."""


@dataclass
class Transcription:
    text: str
    confidence: float | None
    duration_seconds: float | None
    provider: str


class STTProvider(Protocol):
    name: str

    def transcribe(self, audio: bytes, mime: str, *, filename: str = "answer.webm") -> Transcription: ...


class TTSProvider(Protocol):
    name: str

    def synthesize(self, text: str, *, voice: str, speed: float = 1.0, instructions: str | None = None) -> tuple[bytes, str]: ...


class MockSTT:
    name = "mock"

    def transcribe(self, audio: bytes, mime: str, *, filename: str = "answer.webm") -> Transcription:
        raise SpeechUnavailableError("Server speech-to-text is not configured. Use your browser's live transcription or type your answer.")


class OpenAISTT:
    name = "openai"
    endpoint = "https://api.openai.com/v1/audio/transcriptions"
    # Prompting Whisper with disfluent text makes it keep fillers such as "um" in the transcript,
    # which LinguaSI needs for honest fluency metrics.
    filler_prompt = "Umm, let me think... like, hmm. Okay, so, uh, here's what I'm, you know, thinking."

    def __init__(self, api_key: str, model: str, timeout: float) -> None:
        self.api_key = api_key
        self.model = model
        self.client = httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0))

    def transcribe(self, audio: bytes, mime: str, *, filename: str = "answer.webm") -> Transcription:
        verbose = self.model.startswith("whisper")
        data = {"model": self.model, "language": "en", "response_format": "verbose_json" if verbose else "json"}
        if verbose:
            data["prompt"] = self.filler_prompt
        try:
            response = self.client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                data=data,
                files={"file": (filename, audio, mime or "application/octet-stream")},
            )
        except httpx.HTTPError as exc:
            raise SpeechUnavailableError("The transcription service could not be reached.") from exc
        if response.status_code >= 400:
            logger.warning("OpenAI transcription failed with status %s", response.status_code)
            raise SpeechUnavailableError("The transcription service could not process this recording.")
        payload = response.json()
        confidence = None
        segments = payload.get("segments") or []
        if segments:
            probs = [math.exp(s.get("avg_logprob", -1.0)) for s in segments if "avg_logprob" in s]
            if probs:
                confidence = round(max(0.0, min(1.0, sum(probs) / len(probs))), 3)
        return Transcription(
            text=(payload.get("text") or "").strip(),
            confidence=confidence,
            duration_seconds=payload.get("duration"),
            provider=self.name,
        )


class MockTTS:
    name = "mock"

    def synthesize(self, text: str, *, voice: str, speed: float = 1.0, instructions: str | None = None) -> tuple[bytes, str]:
        raise SpeechUnavailableError("Server text-to-speech is not configured; the device voice is used instead.")


class OpenAITTS:
    name = "openai"
    endpoint = "https://api.openai.com/v1/audio/speech"

    def __init__(self, api_key: str, model: str, timeout: float) -> None:
        self.api_key = api_key
        self.model = model
        self.client = httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0))

    def synthesize(self, text: str, *, voice: str, speed: float = 1.0, instructions: str | None = None) -> tuple[bytes, str]:
        body: dict = {"model": self.model, "input": text, "voice": voice, "response_format": "mp3"}
        if self.model.startswith("tts-1"):
            body["speed"] = max(0.5, min(1.5, speed))
        elif instructions:
            body["instructions"] = instructions
        try:
            response = self.client.post(self.endpoint, headers={"Authorization": f"Bearer {self.api_key}"}, json=body)
        except httpx.HTTPError as exc:
            raise SpeechUnavailableError("The speech service could not be reached.") from exc
        if response.status_code >= 400:
            logger.warning("OpenAI TTS failed with status %s", response.status_code)
            raise SpeechUnavailableError("The speech service could not generate audio.")
        return response.content, "audio/mpeg"


VOICES = {"female": ["nova", "shimmer", "coral"], "male": ["onyx", "echo", "ash"]}


def voice_for(speaker: dict, index: int) -> str:
    options = VOICES.get(speaker.get("gender", "female"), VOICES["female"])
    return options[index % len(options)]


def get_stt() -> STTProvider:
    if settings.effective_stt_provider == "openai":
        return OpenAISTT(settings.openai_api_key or "", settings.openai_stt_model, settings.ai_timeout_seconds)
    return MockSTT()


def get_tts() -> TTSProvider:
    if settings.effective_tts_provider == "openai":
        return OpenAITTS(settings.openai_api_key or "", settings.openai_tts_model, settings.ai_timeout_seconds)
    return MockTTS()
