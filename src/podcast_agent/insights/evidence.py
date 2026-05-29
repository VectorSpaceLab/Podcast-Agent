"""Evidence extraction from transcript artifacts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any

from podcast_agent.errors import EvidenceExtractionError
from podcast_agent.insights.evidence_prompts import build_evidence_chunk_prompt
from podcast_agent.insights.llm import ModelWriter
from podcast_agent.pipeline.artifacts import load_json, save_json


@dataclass(frozen=True)
class EvidenceConfig:
    chunk_duration_seconds: int = 600
    chunk_overlap_seconds: int = 30
    max_final_segments: int = 8
    include_outline: bool = True
    chunk_max_workers: int = 4


def extract_evidence(
    *,
    output_dir: Path,
    model_writer: ModelWriter,
    config: EvidenceConfig | None = None,
) -> dict[str, Any]:
    active_config = config or EvidenceConfig()
    input_payload = _load_mapping(output_dir / "input.json", "input.json")
    question = str(input_payload.get("question") or "").strip()
    if not question:
        raise EvidenceExtractionError("Evidence extraction failed: input.json question is required.")

    transcript_path = output_dir / "elements" / "transcript.vtt"
    if not transcript_path.is_file():
        raise EvidenceExtractionError("Evidence extraction failed: elements/transcript.vtt is required.")

    transcript_text = transcript_path.read_text(encoding="utf-8")
    subtitle_segments = parse_subtitle_segments(transcript_text)
    if not subtitle_segments:
        raise EvidenceExtractionError("Evidence extraction failed: transcript.vtt contains no subtitle segments.")

    metadata = _load_optional_mapping(output_dir / "elements" / "metadata.json")
    chapters = _metadata_chapters(metadata)
    chunks = chunk_subtitle_segments_by_chapters(subtitle_segments, chapters)
    if not chunks:
        chunks = chunk_subtitle_segments(
            subtitle_segments,
            chunk_duration_seconds=active_config.chunk_duration_seconds,
            chunk_overlap_seconds=active_config.chunk_overlap_seconds,
        )

    subtitle_lookup = build_subtitle_lookup(subtitle_segments)
    outline_text = _outline_text(metadata) if active_config.include_outline else "- (no outline available)"
    chunk_results: dict[int, list[dict[str, Any]]] = {}
    if len(chunks) > 1 and active_config.chunk_max_workers > 1:
        max_workers = min(len(chunks), active_config.chunk_max_workers)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _extract_chunk_segments,
                    question=question,
                    chunk=chunk,
                    outline_text=outline_text,
                    subtitle_lookup=subtitle_lookup,
                    model_writer=model_writer,
                ): chunk_index
                for chunk_index, chunk in enumerate(chunks, start=1)
            }
            for future in as_completed(futures):
                chunk_results[futures[future]] = future.result()
    else:
        for chunk_index, chunk in enumerate(chunks, start=1):
            chunk_results[chunk_index] = _extract_chunk_segments(
                question=question,
                chunk=chunk,
                outline_text=outline_text,
                subtitle_lookup=subtitle_lookup,
                model_writer=model_writer,
            )

    chunk_candidates = [
        segment
        for chunk_index in sorted(chunk_results)
        for segment in chunk_results[chunk_index]
    ]

    final_segments = reindex_segments(normalize_segments(chunk_candidates))
    if active_config.max_final_segments > 0:
        final_segments = final_segments[: active_config.max_final_segments]
        final_segments = reindex_segments(final_segments)

    evidence = build_evidence_snapshot(
        question=question,
        subtitle_path=Path("elements") / "transcript.vtt",
        segments=final_segments,
        coverage_notes=(
            "No relevant evidence segments were found for the question."
            if not final_segments
            else None
        ),
    )
    save_json(output_dir / "insights" / "evidence.json", evidence)
    return evidence


def _extract_chunk_segments(
    *,
    question: str,
    chunk: dict[str, Any],
    outline_text: str,
    subtitle_lookup: SubtitleLookup,
    model_writer: ModelWriter,
) -> list[dict[str, Any]]:
    prompt = build_evidence_chunk_prompt(
        question=question,
        chunk_text=format_chunk_transcript(chunk),
        outline_text=outline_text,
    )
    response = model_writer(prompt)
    raw_segments = normalize_segments(parse_model_json(response).get("segments"))
    return hydrate_segments_from_subtitles(raw_segments, subtitle_lookup, include_subtitles=True)


def parse_timestamp_value(timestamp: str) -> float:
    value = timestamp.strip().replace(",", ".")
    match = re.match(r"(?:(\d+):)?(\d{2}):(\d{2})(?:\.(\d{1,3}))?", value)
    if not match:
        return 0.0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    milliseconds = int((match.group(4) or "0").ljust(3, "0")[:3])
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0


def format_timestamp_display(timestamp: str) -> str:
    value = timestamp.strip()
    if "," in value:
        value = value.split(",", 1)[0]
    elif "." in value and re.match(r"\d{2}:\d{2}:\d{2}\.\d+", value):
        value = value.split(".", 1)[0]
    return value


def parse_subtitle_segments(subtitle_text: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    current_start = ""
    current_end = ""
    current_text: list[str] = []
    next_index = 1

    def flush() -> None:
        nonlocal current_start, current_end, current_text, next_index
        text = " ".join(part.strip() for part in current_text if part.strip()).strip()
        if current_start and current_end and text:
            segments.append({"index": next_index, "start": current_start, "end": current_end, "text": text})
            next_index += 1
        current_start = ""
        current_end = ""
        current_text = []

    for raw_line in subtitle_text.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            continue
        if line.upper() == "WEBVTT" or line.isdigit():
            continue
        if line.startswith(("NOTE", "STYLE", "REGION")):
            continue
        if "-->" in line:
            flush()
            start, end = line.split("-->", 1)
            current_start = start.strip()
            current_end = end.strip().split()[0]
            continue
        if current_start:
            current_text.append(line)
    flush()
    return segments


def segment_window_bounds(segment: dict[str, Any]) -> tuple[float, float]:
    return parse_timestamp_value(str(segment["start"])), parse_timestamp_value(str(segment["end"]))


def chunk_subtitle_segments(
    segments: list[dict[str, Any]],
    *,
    chunk_duration_seconds: int,
    chunk_overlap_seconds: int,
) -> list[dict[str, Any]]:
    if not segments:
        return []
    if chunk_overlap_seconds >= chunk_duration_seconds:
        chunk_overlap_seconds = max(0, chunk_duration_seconds // 4)
    first_start = segment_window_bounds(segments[0])[0]
    final_end = max(segment_window_bounds(segment)[1] for segment in segments)
    windows: list[dict[str, Any]] = []
    window_start = first_start
    while window_start <= final_end:
        window_end = window_start + chunk_duration_seconds
        chunk_segments = [
            segment
            for segment in segments
            if segment_window_bounds(segment)[0] < window_end
            and segment_window_bounds(segment)[1] > window_start
        ]
        if chunk_segments:
            windows.append({"start": window_start, "end": window_end, "segments": chunk_segments})
        if window_end >= final_end:
            break
        window_start = max(window_start + 1.0, window_end - chunk_overlap_seconds)
    return windows


def chunk_subtitle_segments_by_chapters(
    segments: list[dict[str, Any]],
    chapters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not segments or not chapters:
        return []
    first_start = segment_window_bounds(segments[0])[0]
    final_end = max(segment_window_bounds(segment)[1] for segment in segments)
    active_chapters = [chapter for chapter in chapters if float(chapter["start"]) < final_end]
    if not active_chapters:
        return []
    if float(active_chapters[0]["start"]) > first_start:
        active_chapters = [{"start": first_start, "title": ""}, *active_chapters]

    windows: list[dict[str, Any]] = []
    for index, chapter in enumerate(active_chapters):
        window_start = float(chapter["start"])
        window_end = (
            float(active_chapters[index + 1]["start"])
            if index + 1 < len(active_chapters)
            else final_end
        )
        if window_end <= window_start:
            continue
        chunk_segments = [
            segment
            for segment in segments
            if segment_window_bounds(segment)[0] < window_end
            and segment_window_bounds(segment)[1] > window_start
        ]
        if not chunk_segments:
            continue
        chunk = {"start": window_start, "end": window_end, "segments": chunk_segments}
        chapter_title = str(chapter.get("title") or "").strip()
        if chapter_title:
            chunk["chapter_title"] = chapter_title
        windows.append(chunk)
    return windows


def format_chunk_transcript(chunk: dict[str, Any]) -> str:
    lines = [f"Chunk window: {chunk['start']:.3f}s - {chunk['end']:.3f}s"]
    chapter_title = str(chunk.get("chapter_title") or "").strip()
    if chapter_title:
        lines.append(f"Chapter: {chapter_title}")
    lines.append("Transcript:")
    for index, segment in enumerate(chunk.get("segments", []), start=1):
        start = str(segment.get("start", ""))
        end = str(segment.get("end", ""))
        text = str(segment.get("text", "")).strip()
        lines.append(f"{index}. [{format_timestamp_display(start)} --> {format_timestamp_display(end)}] {text}")
    return "\n".join(lines)


def parse_model_json(output: str) -> dict[str, Any]:
    text = output.strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}


def normalize_segments(raw_segments: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_segments, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw_segment in raw_segments:
        if not isinstance(raw_segment, dict):
            continue
        start = str(raw_segment.get("start", "")).strip()
        end = str(raw_segment.get("end", "")).strip()
        if not start or not end:
            continue
        key = (start, end)
        if key in seen:
            continue
        seen.add(key)
        normalized_segment: dict[str, Any] = {"start": start, "end": end}
        text = str(raw_segment.get("text", "")).strip()
        if text:
            normalized_segment["text"] = text
        subtitles = raw_segment.get("subtitles")
        if isinstance(subtitles, list):
            normalized_segment["subtitles"] = [
                {
                    "start": str(item.get("start", "")).strip(),
                    "end": str(item.get("end", "")).strip(),
                    "text": str(item.get("text", "")).strip(),
                }
                for item in subtitles
                if isinstance(item, dict)
            ]
        normalized.append(normalized_segment)
    normalized.sort(key=lambda segment: (parse_timestamp_value(segment["start"]), parse_timestamp_value(segment["end"])))
    return normalized


SubtitleLookup = tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[int, dict[str, Any]],
]


def normalize_full_timestamp_key(timestamp: str) -> str:
    value = str(timestamp).strip().replace(".", ",")
    match = re.fullmatch(r"(?:(\d+):)?(\d{2}):(\d{2})(?:,(\d{1,3}))?", value)
    if not match:
        return value
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    milliseconds = (match.group(4) or "").ljust(3, "0")[:3]
    if milliseconds:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds}"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def normalize_timestamp_key(timestamp: str) -> str:
    value = str(timestamp).strip()
    return re.sub(r"([,.]\d{1,3})$", "", value)


def build_subtitle_lookup(segments: list[dict[str, Any]]) -> SubtitleLookup:
    exact_start_lookup: dict[str, dict[str, Any]] = {}
    exact_end_lookup: dict[str, dict[str, Any]] = {}
    second_level_start_candidates: dict[str, list[dict[str, Any]]] = {}
    second_level_end_candidates: dict[str, list[dict[str, Any]]] = {}
    segments_by_index: dict[int, dict[str, Any]] = {}
    for segment in segments:
        start = str(segment.get("start", "")).strip()
        end = str(segment.get("end", "")).strip()
        index = int(segment.get("index") or 0)
        if not start or not end:
            continue
        exact_start_lookup[normalize_full_timestamp_key(start)] = segment
        exact_end_lookup[normalize_full_timestamp_key(end)] = segment
        second_level_start_candidates.setdefault(normalize_timestamp_key(start), []).append(segment)
        second_level_end_candidates.setdefault(normalize_timestamp_key(end), []).append(segment)
        if index > 0:
            segments_by_index[index] = segment

    second_level_start_lookup: dict[str, dict[str, Any]] = {}
    second_level_end_lookup: dict[str, dict[str, Any]] = {}
    for key, matches in second_level_start_candidates.items():
        if len(matches) == 1:
            second_level_start_lookup[key] = matches[0]
    for key, matches in second_level_end_candidates.items():
        if len(matches) == 1:
            second_level_end_lookup[key] = matches[0]
    return exact_start_lookup, second_level_start_lookup, exact_end_lookup, second_level_end_lookup, segments_by_index


def hydrate_segments_from_subtitles(
    raw_segments: list[dict[str, Any]],
    subtitle_lookup: SubtitleLookup,
    *,
    include_subtitles: bool = True,
) -> list[dict[str, Any]]:
    exact_start_lookup, second_level_start_lookup, exact_end_lookup, second_level_end_lookup, segments_by_index = subtitle_lookup
    hydrated: list[dict[str, Any]] = []
    for raw_segment in raw_segments:
        start = str(raw_segment.get("start", "")).strip()
        end = str(raw_segment.get("end", "")).strip()
        start_segment = exact_start_lookup.get(normalize_full_timestamp_key(start))
        if start_segment is None:
            start_segment = second_level_start_lookup.get(normalize_timestamp_key(start))
        end_segment = exact_end_lookup.get(normalize_full_timestamp_key(end))
        if end_segment is None:
            end_segment = second_level_end_lookup.get(normalize_timestamp_key(end))
        if start_segment is None or end_segment is None:
            continue
        start_index = int(start_segment.get("index") or 0)
        end_index = int(end_segment.get("index") or 0)
        if start_index <= 0 or end_index <= 0 or start_index > end_index:
            continue
        text_parts: list[str] = []
        subtitle_items: list[dict[str, str]] = []
        for current_index in range(start_index, end_index + 1):
            current_segment = segments_by_index.get(current_index)
            if current_segment is None:
                text_parts = []
                subtitle_items = []
                break
            text = str(current_segment.get("text", "")).strip()
            subtitle_items.append(
                {
                    "start": str(current_segment.get("start", "")).strip(),
                    "end": str(current_segment.get("end", "")).strip(),
                    "text": text,
                }
            )
            if text:
                text_parts.append(text)
        if not text_parts or not subtitle_items:
            continue
        hydrated_segment: dict[str, Any] = {
            "index": start_index,
            "start": str(start_segment.get("start", "")).strip(),
            "end": str(end_segment.get("end", "")).strip(),
            "text": " ".join(text_parts),
        }
        if include_subtitles:
            hydrated_segment["subtitles"] = subtitle_items
        hydrated.append(hydrated_segment)
    return hydrated


def reindex_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reindexed: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        reindexed_segment: dict[str, Any] = {
            "index": index,
            "start": str(segment.get("start", "")).strip(),
            "end": str(segment.get("end", "")).strip(),
            "text": str(segment.get("text", "")).strip(),
        }
        if "subtitles" in segment:
            reindexed_segment["subtitles"] = [
                {
                    "start": str(item.get("start", "")).strip(),
                    "end": str(item.get("end", "")).strip(),
                    "text": str(item.get("text", "")).strip(),
                }
                for item in segment.get("subtitles", [])
                if isinstance(item, dict)
            ]
        reindexed.append(reindexed_segment)
    return reindexed


def build_evidence_snapshot(
    *,
    question: str,
    subtitle_path: Path,
    segments: list[dict[str, Any]],
    coverage_notes: str | None = None,
) -> dict[str, Any]:
    sanitized_segments: list[dict[str, Any]] = []
    for segment in segments:
        sanitized_segment = dict(segment)
        if "index" in sanitized_segment:
            sanitized_segment["index"] = int(sanitized_segment["index"])
        sanitized_segments.append(sanitized_segment)
    evidence: dict[str, Any] = {
        "question": question,
        "subtitle_path": str(subtitle_path),
        "segments": sanitized_segments,
    }
    if coverage_notes:
        evidence["coverage_notes"] = coverage_notes
    return evidence


def _load_mapping(path: Path, name: str) -> dict[str, Any]:
    if not path.is_file():
        raise EvidenceExtractionError(f"Evidence extraction failed: {name} is required.")
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise EvidenceExtractionError(f"Evidence extraction failed: {name} must be a JSON object.")
    return payload


def _load_optional_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def _metadata_chapters(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = metadata.get("chapters")
    if not isinstance(chapters, list):
        return []
    normalized: list[dict[str, Any]] = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        start = chapter.get("start")
        if isinstance(start, bool) or not isinstance(start, (int, float)):
            continue
        normalized.append({"start": float(start), "title": str(chapter.get("title") or "")})
    normalized.sort(key=lambda item: item["start"])
    return normalized


def _outline_text(metadata: dict[str, Any]) -> str:
    chapters = _metadata_chapters(metadata)
    if not chapters:
        return "- (no outline available)"
    lines = []
    for chapter in chapters:
        title = str(chapter.get("title") or "").strip() or "(untitled)"
        lines.append(f"- {format_seconds_for_outline(float(chapter['start']))} {title}")
    return "\n".join(lines)


def format_seconds_for_outline(seconds: float) -> str:
    total = max(0, int(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds_part = total % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds_part:02d}"
    return f"{minutes:02d}:{seconds_part:02d}"
