"""Source type detection from URLs."""

from __future__ import annotations

from urllib.parse import urlparse

from podcast_agent.errors import UnsupportedSourceError


def _normalized_host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def detect_source(url: str) -> str:
    host = _normalized_host(url)

    if host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com"):
        return "youtube"

    raise UnsupportedSourceError(f"Unsupported source URL: {url}")
