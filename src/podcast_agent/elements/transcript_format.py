"""Transcript format helpers."""

from __future__ import annotations

import re

from podcast_agent.errors import TranscriptFetchError
from podcast_agent.types import TranscriptSegment

_SRT_TIME_RE = re.compile(
    r"(?P<hours>\d{2}):(?P<minutes>\d{2}):(?P<seconds>\d{2}),"
    r"(?P<milliseconds>\d{3})"
)
_TIME_LINE_RE = re.compile(r".+-->\s*.+")


def srt_to_vtt(content: str) -> str:
    lines: list[str] = ["WEBVTT", ""]
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.isdigit():
            continue
        if "-->" in line:
            lines.append(_SRT_TIME_RE.sub(_replace_srt_timestamp, line))
            continue
        lines.append(raw_line)
    return "\n".join(lines).rstrip() + "\n"


def transcript_to_text(content: str) -> str:
    lines: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "WEBVTT":
            continue
        if line.isdigit():
            continue
        if "-->" in line:
            continue
        if line.startswith(("NOTE", "STYLE", "REGION")):
            continue
        lines.append(line)
    text = "\n".join(lines).strip()
    if not text:
        raise TranscriptFetchError("Transcript fetch failed: transcript text is empty")
    return text + "\n"


def segments_to_vtt(segments: list[TranscriptSegment]) -> str:
    cues = ["WEBVTT", ""]
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        start = max(0.0, float(segment.start))
        end = max(start + 0.001, float(segment.end))
        cues.extend(
            [
                f"{format_vtt_timestamp(start)} --> {format_vtt_timestamp(end)}",
                text,
                "",
            ]
        )
    content = "\n".join(cues).rstrip() + "\n"
    require_non_empty_vtt(content)
    return content


def format_vtt_timestamp(seconds: float) -> str:
    milliseconds_total = max(0, int(round(seconds * 1000)))
    milliseconds = milliseconds_total % 1000
    seconds_total = milliseconds_total // 1000
    seconds_part = seconds_total % 60
    minutes_total = seconds_total // 60
    minutes_part = minutes_total % 60
    hours = minutes_total // 60
    return f"{hours:02d}:{minutes_part:02d}:{seconds_part:02d}.{milliseconds:03d}"


def require_non_empty_vtt(content: str) -> None:
    if not content.strip().startswith("WEBVTT"):
        raise TranscriptFetchError("Transcript fetch failed: transcript.vtt must start with WEBVTT")
    transcript_to_text(content)


def count_vtt_cues(content: str) -> int:
    return sum(1 for line in content.splitlines() if _TIME_LINE_RE.match(line.strip()))


def _replace_srt_timestamp(match: re.Match[str]) -> str:
    return (
        f"{match.group('hours')}:{match.group('minutes')}:"
        f"{match.group('seconds')}.{match.group('milliseconds')}"
    )
