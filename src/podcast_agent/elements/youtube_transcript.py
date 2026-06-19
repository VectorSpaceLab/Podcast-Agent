"""YouTube transcript acquisition."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

from podcast_agent.config import (
    BILIBILI_COOKIES_FILE,
    BILIBILI_COOKIES_FROM_BROWSER,
    BILIBILI_USER_AGENT,
    YOUTUBE_COOKIES_FILE,
)
from podcast_agent.downloaders.yt_dlp import BilibiliYtDlpDownloader, YtDlpDownloader
from podcast_agent.elements.transcript_format import (
    count_vtt_cues,
    require_non_empty_vtt,
    segments_to_vtt,
    srt_to_vtt,
    transcript_to_text,
)
from podcast_agent.elements.transcript_tracks import (
    TranscriptLanguagePreference,
    rank_transcript_tracks,
    transcript_download_candidates,
    transcript_tracks_from_info_for_source,
)
from podcast_agent.errors import AudioTranscriptionError, TranscriptFetchError
from podcast_agent.pipeline.artifacts import save_json
from podcast_agent.transcribers.base import Transcriber
from podcast_agent.transcribers.types import TranscriptionRequest
from podcast_agent.types import AudioInfo, SourceRef, TranscriptInfo, TranscriptTrack


LOGGER = logging.getLogger(__name__)


class TranscriptDownloader(Protocol):
    def extract_info(self, url: str, *, output_dir: Path) -> dict[str, Any]:
        ...

    def download_subtitle(
        self,
        url: str,
        *,
        output_dir: Path,
        language: str,
        track_kind: str,
    ) -> dict[str, Any]:
        ...

    def download_audio(self, url: str, *, output_dir: Path) -> dict[str, Any]:
        ...


class YoutubeTranscriptFetcher:
    def __init__(
        self,
        *,
        elements_dir: Path,
        cookies_file: str | None = None,
        downloader: TranscriptDownloader | None = None,
        transcriber: Transcriber | None = None,
        language_preference: TranscriptLanguagePreference | None = None,
    ) -> None:
        self.elements_dir = elements_dir
        self.raw_dir = elements_dir / "raw"
        self.audio_dir = elements_dir / "audio"
        self.downloader = downloader
        self.cookies_file = cookies_file
        self.transcriber = transcriber
        self.language_preference = language_preference or TranscriptLanguagePreference()

    def fetch(self, source: SourceRef) -> TranscriptInfo:
        self.elements_dir.mkdir(parents=True, exist_ok=True)
        try:
            return self._fetch_from_youtube_subtitles(source)
        except TranscriptFetchError as subtitle_error:
            if self.transcriber is None:
                raise subtitle_error
            return self._fetch_from_audio_transcription(source)

    def _fetch_from_youtube_subtitles(self, source: SourceRef) -> TranscriptInfo:
        downloader = self.downloader or _default_transcript_downloader(source, self.cookies_file)
        info = downloader.extract_info(source.url, output_dir=self.raw_dir)
        ranked_tracks = rank_transcript_tracks(
            transcript_tracks_from_info_for_source(info, source_type=source.source_type),
            self.language_preference,
        )
        preferred_language = self._preferred_language()
        LOGGER.info(
            "youtube_transcript_tracks_listed | source_id=%s | source_type=%s | track_count=%s | preferred_language=%s",
            source.source_id,
            source.source_type,
            len(ranked_tracks),
            preferred_language or "",
        )
        if not ranked_tracks:
            LOGGER.info(
                "youtube_transcript_tracks_unavailable | source_id=%s | source_type=%s | preferred_language=%s",
                source.source_id,
                source.source_type,
                preferred_language or "",
            )
            raise TranscriptFetchError(f"Transcript fetch failed: no subtitles are available for {source.source_id}")

        last_error: Exception | None = None
        candidate_tracks = transcript_download_candidates(ranked_tracks, self.language_preference)
        if not candidate_tracks:
            LOGGER.info(
                "youtube_transcript_tracks_no_acceptable_candidates | source_id=%s | source_type=%s | track_count=%s | preferred_language=%s",
                source.source_id,
                source.source_type,
                len(ranked_tracks),
                preferred_language or "",
            )
            raise TranscriptFetchError(f"Transcript fetch failed: no subtitles are available for {source.source_id}")

        selected_tracks = candidate_tracks[: self.language_preference.max_download_attempts]
        if len(candidate_tracks) > len(selected_tracks):
            LOGGER.info(
                "youtube_transcript_tracks_limited | source_id=%s | source_type=%s | track_count=%s | attempted_track_count=%s",
                source.source_id,
                source.source_type,
                len(candidate_tracks),
                len(selected_tracks),
            )
        for attempt, track in enumerate(selected_tracks, start=1):
            LOGGER.info(
                "youtube_transcript_download_attempt | source_id=%s | source_type=%s | attempt=%s | language=%s | track_kind=%s | track_id=%s",
                source.source_id,
                source.source_type,
                attempt,
                track.language,
                track.track_kind,
                track.id,
            )
            try:
                downloaded_path = self._download_track(source, track)
                vtt_content = self._read_as_vtt(downloaded_path)
                return self._write_transcript_artifacts(
                    source=source,
                    vtt_content=vtt_content,
                    language=track.language,
                    acquisition_method=f"{source.source_type}_subtitle",
                    subtitle_source=f"{source.source_type}_yt_dlp_captions",
                    subtitle_kind=track.track_kind,
                    subtitle_track_id=track.id,
                    source_format=downloaded_path.suffix.lower().lstrip("."),
                    downloaded_subtitle_path=downloaded_path,
                    audio_info=None,
                    transcription_provider=None,
                )
            except Exception as exc:
                last_error = exc
                LOGGER.info(
                    "youtube_transcript_download_attempt_failed | source_id=%s | source_type=%s | attempt=%s | language=%s | track_kind=%s | track_id=%s | error=%s",
                    source.source_id,
                    source.source_type,
                    attempt,
                    track.language,
                    track.track_kind,
                    track.id,
                    exc,
                )
                continue

        LOGGER.info(
            "youtube_transcript_download_failed | source_id=%s | source_type=%s | attempted_track_count=%s | error=%s",
            source.source_id,
            source.source_type,
            len(selected_tracks),
            last_error,
        )
        raise TranscriptFetchError(f"Transcript fetch failed: failed to download subtitles: {last_error}")

    def _download_track(self, source: SourceRef, track: TranscriptTrack) -> Path:
        downloader = self.downloader or _default_transcript_downloader(source, self.cookies_file)
        info = downloader.download_subtitle(
            source.url,
            output_dir=self.raw_dir,
            language=track.language,
            track_kind=track.track_kind,
        )
        requested_path = _requested_subtitle_path(info, track)
        if requested_path is not None:
            return requested_path

        candidates = sorted(self.raw_dir.glob(f"*.{track.language}.*"))
        if candidates:
            return candidates[0]
        raise TranscriptFetchError(f"Transcript fetch failed: downloaded subtitle file not found for {track.language}")

    def _read_as_vtt(self, path: Path) -> str:
        content = path.read_text(encoding="utf-8")
        suffix = path.suffix.lower()
        if suffix == ".vtt":
            require_non_empty_vtt(content)
            return content.rstrip() + "\n"
        if suffix == ".srt":
            vtt_content = srt_to_vtt(content)
            require_non_empty_vtt(vtt_content)
            return vtt_content
        raise TranscriptFetchError(f"Transcript fetch failed: unsupported subtitle format {suffix}")

    def _fetch_from_audio_transcription(self, source: SourceRef) -> TranscriptInfo:
        if self.transcriber is None:
            raise TranscriptFetchError("Transcript fetch failed: audio transcription fallback is not configured")

        downloader = self.downloader or _default_transcript_downloader(source, self.cookies_file)
        audio_info = downloader.download_audio(source.url, output_dir=self.audio_dir)
        audio_path = _requested_audio_path(audio_info, self.audio_dir)
        if audio_path is None:
            raise AudioTranscriptionError("Audio transcription failed: downloaded audio file not found")

        try:
            result = self.transcriber.transcribe(
                TranscriptionRequest(
                    audio_path=audio_path,
                    language_hints=self.language_preference.preferred_languages,
                )
            )
        except Exception as exc:
            raise AudioTranscriptionError(f"Audio transcription failed: {exc}") from exc
        segments = result.segments
        vtt_content = segments_to_vtt(segments)
        audio_artifact = self._write_audio_info(
            source=source,
            audio_path=audio_path,
            audio_info=audio_info,
            transcription_provider=result.provider,
            transcription_language=self._preferred_language(),
            segment_count=len([segment for segment in segments if segment.text.strip()]),
        )
        return self._write_transcript_artifacts(
            source=source,
            vtt_content=vtt_content,
            language=self._preferred_language(),
            acquisition_method="audio_transcription",
            subtitle_source=None,
            subtitle_kind=None,
            subtitle_track_id=None,
            source_format=None,
            downloaded_subtitle_path=None,
            audio_info=audio_artifact,
            transcription_provider=result.provider,
        )

    def _write_transcript_artifacts(
        self,
        *,
        source: SourceRef,
        vtt_content: str,
        language: str | None,
        acquisition_method: str,
        subtitle_source: str | None,
        subtitle_kind: str | None,
        subtitle_track_id: str | None,
        source_format: str | None,
        downloaded_subtitle_path: Path | None,
        audio_info: AudioInfo | None,
        transcription_provider: str | None,
    ) -> TranscriptInfo:
        require_non_empty_vtt(vtt_content)
        text_content = transcript_to_text(vtt_content)
        transcript_path = self.elements_dir / "transcript.vtt"
        text_path = self.elements_dir / "transcript.txt"
        transcript_path.write_text(vtt_content, encoding="utf-8")
        text_path.write_text(text_content, encoding="utf-8")
        info = TranscriptInfo(
            source_type=source.source_type,
            source_id=source.source_id,
            source_url=source.url,
            transcript_path="elements/transcript.vtt",
            text_path="elements/transcript.txt",
            transcript_format="vtt",
            language=language,
            acquisition_method=acquisition_method,
            subtitle_source=subtitle_source,
            subtitle_kind=subtitle_kind,
            subtitle_track_id=subtitle_track_id,
            source_format=source_format,
            downloaded_subtitle_path=_elements_relative_path(downloaded_subtitle_path, self.elements_dir),
            audio_fallback_used=audio_info is not None,
            audio_info_path="elements/audio_info.json" if audio_info is not None else None,
            transcription_provider=transcription_provider,
            segment_count=count_vtt_cues(vtt_content),
        )
        save_json(self.elements_dir / "transcript_info.json", info)
        return info

    def _write_audio_info(
        self,
        *,
        source: SourceRef,
        audio_path: Path,
        audio_info: dict[str, Any],
        transcription_provider: str,
        transcription_language: str | None,
        segment_count: int,
    ) -> AudioInfo:
        artifact = AudioInfo(
            source_type=source.source_type,
            source_id=source.source_id,
            source_url=source.url,
            audio_path=_elements_relative_path(audio_path, self.elements_dir),
            audio_format=audio_path.suffix.lower().lstrip(".") or None,
            duration_seconds=_duration_seconds(audio_info.get("duration")),
            download_method="yt_dlp",
            transcription_provider=transcription_provider,
            transcription_language=transcription_language,
            segment_count=segment_count,
        )
        save_json(self.elements_dir / "audio_info.json", artifact)
        return artifact

    def _preferred_language(self) -> str | None:
        return self.language_preference.preferred_languages[0] if self.language_preference.preferred_languages else None


def _requested_subtitle_path(info: dict[str, Any], track: TranscriptTrack) -> Path | None:
    requested = info.get("requested_subtitles")
    if not isinstance(requested, dict):
        return None
    subtitle = requested.get(track.id) or requested.get(track.language)
    if isinstance(subtitle, dict) and subtitle.get("filepath"):
        path = Path(str(subtitle["filepath"]))
        if path.exists():
            return path
    return None


def _requested_audio_path(info: dict[str, Any], audio_dir: Path) -> Path | None:
    requested = info.get("requested_downloads")
    if isinstance(requested, list):
        for item in requested:
            if isinstance(item, dict) and item.get("filepath"):
                path = Path(str(item["filepath"]))
                if path.exists():
                    return path
                converted = path.with_suffix(".wav")
                if converted.exists():
                    return converted
    audio_candidates = sorted(
        path
        for pattern in ("*.wav", "*.m4a", "*.mp3", "*.webm", "*.opus")
        for path in audio_dir.glob(pattern)
        if path.is_file()
    )
    if audio_candidates:
        return audio_candidates[0]
    return None


def _elements_relative_path(path: Path | None, elements_dir: Path) -> str | None:
    if path is None:
        return None
    try:
        return f"elements/{path.relative_to(elements_dir).as_posix()}"
    except ValueError:
        return str(path)


def _default_transcript_downloader(source: SourceRef, cookies_file: str | None) -> TranscriptDownloader:
    if source.source_type == "bilibili":
        return BilibiliYtDlpDownloader(
            cookies_file=cookies_file or BILIBILI_COOKIES_FILE,
            cookies_from_browser=BILIBILI_COOKIES_FROM_BROWSER,
            user_agent=BILIBILI_USER_AGENT,
        )
    return YtDlpDownloader(cookies_file=cookies_file or YOUTUBE_COOKIES_FILE)


def _duration_seconds(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        return seconds if seconds >= 0 else None
    return None
