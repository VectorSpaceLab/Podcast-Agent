"""Transcription provider protocols."""

from __future__ import annotations

from typing import Protocol

from podcast_agent.transcribers.types import TranscriptionRequest, TranscriptionResult


class Transcriber(Protocol):
    provider_name: str

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        ...
