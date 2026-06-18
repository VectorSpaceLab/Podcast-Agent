"""Transcript track discovery and ranking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from podcast_agent.types import TranscriptTrack

DEFAULT_TRANSCRIPT_LANGUAGES = ("zh-Hans", "zh", "en", "en-US")
MAX_TRANSCRIPT_DOWNLOAD_ATTEMPTS = 3


@dataclass(frozen=True)
class TranscriptLanguagePreference:
    preferred_languages: tuple[str, ...] = DEFAULT_TRANSCRIPT_LANGUAGES
    prefer_manual: bool = True
    allow_automatic: bool = True
    max_download_attempts: int = MAX_TRANSCRIPT_DOWNLOAD_ATTEMPTS

    def __post_init__(self) -> None:
        languages = tuple(
            language.strip()
            for language in self.preferred_languages
            if isinstance(language, str) and language.strip()
        )
        object.__setattr__(self, "preferred_languages", languages)
        if self.max_download_attempts <= 0:
            raise ValueError("max_download_attempts must be greater than 0")


def transcript_tracks_from_info(info: dict[str, Any]) -> list[TranscriptTrack]:
    return transcript_tracks_from_info_for_source(info, source_type=None)


def transcript_tracks_from_info_for_source(
    info: dict[str, Any],
    *,
    source_type: str | None,
) -> list[TranscriptTrack]:
    tracks: list[TranscriptTrack] = []
    for collection_key, kind in (("subtitles", "manual"), ("automatic_captions", "automatic")):
        collection = info.get(collection_key)
        if not isinstance(collection, dict):
            continue
        for language, subtitles in collection.items():
            if source_type == "bilibili" and _is_bilibili_danmaku_track(language, subtitles):
                continue
            if isinstance(subtitles, list) and not subtitles:
                continue
            tracks.append(
                TranscriptTrack(
                    id=str(language),
                    language=str(language),
                    status="serving",
                    track_kind=kind,
                )
            )
    return tracks


def rank_transcript_tracks(
    tracks: list[TranscriptTrack],
    preference: TranscriptLanguagePreference | None = None,
) -> list[TranscriptTrack]:
    preference = preference or TranscriptLanguagePreference()
    available = [
        track
        for track in tracks
        if track.status in {"", "serving"}
        and not track.is_draft
        and (preference.allow_automatic or track.track_kind != "automatic")
    ]
    return sorted(available, key=lambda track: _track_sort_key(track, preference))


def _track_sort_key(
    track: TranscriptTrack,
    preference: TranscriptLanguagePreference,
) -> tuple[int, int, str, str]:
    preferred_language = preference.preferred_languages[0] if preference.preferred_languages else None
    return (
        _kind_rank(track, preferred_language, preference),
        _language_variant_rank(track.language, preferred_language),
        track.language,
        track.id,
    )


def _kind_rank(
    track: TranscriptTrack,
    preferred_language: str | None,
    preference: TranscriptLanguagePreference,
) -> int:
    matches = _is_language_match(track.language, preferred_language)
    if preference.prefer_manual:
        if matches and track.track_kind == "manual":
            return 0
        if matches and track.track_kind == "automatic":
            return 1
        if track.track_kind == "manual":
            return 2
        if track.track_kind == "automatic":
            return 3
    else:
        if matches and track.track_kind == "automatic":
            return 0
        if matches and track.track_kind == "manual":
            return 1
        if track.track_kind == "automatic":
            return 2
        if track.track_kind == "manual":
            return 3
    return 4


def _language_variant_rank(language: str, preferred_language: str | None) -> int:
    normalized = language.strip()
    if preferred_language and normalized == preferred_language:
        return 0
    return 1 if _is_language_match(normalized, preferred_language) else 100


def _is_language_match(language: str, preferred_language: str | None) -> bool:
    if not preferred_language:
        return False
    return _normalize_language_code(language)[:2] == _normalize_language_code(preferred_language)[:2]


def _normalize_language_code(language: str) -> str:
    normalized = language.strip()
    if normalized.startswith("ai-") and len(normalized) > 3:
        return normalized[3:]
    return normalized


def _is_bilibili_danmaku_track(language: Any, subtitles: Any) -> bool:
    if str(language).strip() == "danmaku":
        return True
    if not isinstance(subtitles, list):
        return False
    return any(isinstance(item, dict) and str(item.get("ext") or "").lower() == "xml" for item in subtitles)
