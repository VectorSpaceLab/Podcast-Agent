"""Common transcription data structures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from podcast_agent.types import TranscriptSegment


@dataclass(frozen=True)
class TranscriptionRequest:
    audio_path: Path
    language_hints: tuple[str, ...] = ()


@dataclass(frozen=True)
class TranscriptionResult:
    provider: str
    segments: list[TranscriptSegment]
