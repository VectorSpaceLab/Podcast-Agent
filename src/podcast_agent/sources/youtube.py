"""YouTube source URL parsing."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from podcast_agent.errors import InvalidSourceUrlError
from podcast_agent.types import SourceRef


def _validate_video_id(video_id: str, url: str) -> str:
    video_id = video_id.strip()
    if not video_id or "/" in video_id:
        raise InvalidSourceUrlError(f"Invalid YouTube video URL: {url}")
    return video_id


def extract_video_id(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if host == "youtu.be":
        if path_parts:
            return _validate_video_id(path_parts[0], url)
        raise InvalidSourceUrlError(f"Invalid YouTube video URL: {url}")

    if host == "youtube.com" or host.endswith(".youtube.com"):
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
            return _validate_video_id(video_id, url)

        if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed"}:
            return _validate_video_id(path_parts[1], url)

    raise InvalidSourceUrlError(f"Invalid YouTube video URL: {url}")


class YoutubeSourceClient:
    source_type = "youtube"

    def resolve(self, url: str) -> SourceRef:
        return SourceRef(
            source_type=self.source_type,
            url=url,
            source_id=extract_video_id(url),
        )
