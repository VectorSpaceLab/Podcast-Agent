"""Source client protocols."""

from __future__ import annotations

from typing import Protocol

from podcast_agent.types import SourceRef


class SourceClient(Protocol):
    source_type: str

    def resolve(self, url: str) -> SourceRef:
        ...
