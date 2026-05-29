"""Core data contracts used across the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceRef:
    source_type: str
    url: str
    source_id: str


@dataclass(frozen=True)
class Chapter:
    start: float
    title: str


@dataclass(frozen=True)
class VideoMetadata:
    source_type: str
    source_id: str
    source_url: str
    title: str
    author: str
    webpage_url: str
    duration_seconds: float | None = None
    description: str | None = None
    publish_date: str | None = None
    thumbnail_url: str | None = None
    thumbnail_path: str | None = None
    chapters: list[Chapter] = field(default_factory=list)


@dataclass(frozen=True)
class SubtitleSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptTrack:
    id: str
    language: str
    track_kind: str
    status: str = ""
    name: str = ""
    is_draft: bool = False


@dataclass(frozen=True)
class TranscriptInfo:
    source_type: str
    source_id: str
    source_url: str
    transcript_path: str
    text_path: str
    transcript_format: str
    language: str | None
    acquisition_method: str
    subtitle_source: str | None
    subtitle_kind: str | None
    subtitle_track_id: str | None
    source_format: str | None
    downloaded_subtitle_path: str | None
    audio_fallback_used: bool
    audio_info_path: str | None
    transcription_provider: str | None
    segment_count: int | None


@dataclass(frozen=True)
class AudioInfo:
    source_type: str
    source_id: str
    source_url: str
    audio_path: str | None
    audio_format: str | None
    duration_seconds: float | None
    download_method: str
    transcription_provider: str
    transcription_language: str | None
    segment_count: int | None


@dataclass(frozen=True)
class BaseElements:
    metadata: VideoMetadata
    subtitles: list[SubtitleSegment] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceSegment:
    id: str
    start: float
    end: float
    text: str
    reason: str


@dataclass(frozen=True)
class OutlineItem:
    id: str
    title: str
    description: str


@dataclass(frozen=True)
class ViewpointDetail:
    id: str
    title: str
    summary: str
    evidence_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Summary:
    core_conclusions: list[str] = field(default_factory=list)
    one_paragraph_takeaway: str = ""


@dataclass(frozen=True)
class Insights:
    evidence: list[EvidenceSegment] = field(default_factory=list)
    outline: list[OutlineItem] = field(default_factory=list)
    viewpoints: list[ViewpointDetail] = field(default_factory=list)
    summary: Summary = field(default_factory=Summary)


@dataclass(frozen=True)
class PipelineInput:
    url: str
    question: str
    status: str = "initialized"
