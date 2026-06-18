"""Source client registry."""

from __future__ import annotations

from podcast_agent.errors import UnsupportedSourceError
from podcast_agent.sources.base import SourceClient
from podcast_agent.sources.bilibili import BilibiliSourceClient
from podcast_agent.sources.detection import detect_source
from podcast_agent.sources.youtube import YoutubeSourceClient
from podcast_agent.types import SourceRef

_SOURCE_CLIENTS: dict[str, SourceClient] = {
    "bilibili": BilibiliSourceClient(),
    "youtube": YoutubeSourceClient(),
}


def get_source_client(source_type: str) -> SourceClient:
    try:
        return _SOURCE_CLIENTS[source_type]
    except KeyError as exc:
        raise UnsupportedSourceError(f"Unsupported source type: {source_type}") from exc


def resolve_source(url: str) -> SourceRef:
    source_type = detect_source(url)
    client = get_source_client(source_type)
    return client.resolve(url)
