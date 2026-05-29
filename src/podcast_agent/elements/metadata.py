"""Video metadata normalization."""

from __future__ import annotations

import re
from typing import Any

from podcast_agent.errors import MetadataFetchError
from podcast_agent.types import Chapter, SourceRef, VideoMetadata


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def parse_timestamp(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        return seconds if seconds >= 0 else None
    if not isinstance(value, str):
        return None

    text = value.strip().replace(",", ".")
    if not text:
        return None
    try:
        seconds = float(text)
    except ValueError:
        seconds = None
    if seconds is not None:
        return seconds if seconds >= 0 else None

    match = re.fullmatch(r"(?:(\d+):)?(\d{2}):(\d{2})(?:\.(\d{1,3}))?", text)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    milliseconds = int((match.group(4) or "0").ljust(3, "0")[:3])
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0


def _chapter_start(item: dict[str, Any]) -> float | None:
    for key in ("start_time", "start", "time", "timestamp"):
        if key in item:
            timestamp = parse_timestamp(item.get(key))
            if timestamp is not None:
                return timestamp
    return None


def normalize_chapters(raw_chapters: Any) -> list[Chapter]:
    if not isinstance(raw_chapters, list):
        return []

    chapters: list[Chapter] = []
    seen_starts: set[float] = set()
    for item in raw_chapters:
        if not isinstance(item, dict):
            continue
        start = _chapter_start(item)
        if start is None:
            continue
        normalized_start = round(start, 3)
        if normalized_start in seen_starts:
            continue
        seen_starts.add(normalized_start)
        title = _as_text(item.get("title") or item.get("name") or item.get("label"))
        chapters.append(Chapter(start=normalized_start, title=title))

    return sorted(chapters, key=lambda chapter: chapter.start)


def _duration_seconds(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        return seconds if seconds >= 0 else None
    return None


def normalize_metadata(source: SourceRef, info: dict[str, Any]) -> VideoMetadata:
    title = _as_text(info.get("title"))
    author = _as_text(info.get("uploader") or info.get("channel"))
    webpage_url = _as_text(info.get("webpage_url") or info.get("original_url") or source.url)

    missing = [
        field
        for field, value in (
            ("title", title),
            ("author", author),
            ("webpage_url", webpage_url),
        )
        if not value
    ]
    if missing:
        raise MetadataFetchError(f"Metadata fetch failed: missing {', '.join(missing)}")

    return VideoMetadata(
        source_type=source.source_type,
        source_id=_as_text(info.get("id")) or source.source_id,
        source_url=source.url,
        title=title,
        author=author,
        webpage_url=webpage_url,
        duration_seconds=_duration_seconds(info.get("duration")),
        description=_as_text(info.get("description")) or None,
        publish_date=_as_text(info.get("upload_date")) or None,
        thumbnail_url=_as_text(info.get("thumbnail")) or None,
        thumbnail_path=_as_text(info.get("local_thumbnail_path")) or None,
        chapters=normalize_chapters(info.get("chapters")),
    )
