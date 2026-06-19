"""Followup question handling for API tasks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from podcast_agent.api.adapters import compat_segment, find_subtitle_path, load_source_metadata, resolve_source_url
from podcast_agent.insights.evidence import (
    EvidenceConfig,
    build_subtitle_lookup,
    chunk_subtitle_segments,
    chunk_subtitle_segments_by_chapters,
    format_chunk_transcript,
    hydrate_segments_from_subtitles,
    normalize_segments,
    parse_model_json,
    parse_subtitle_segments,
    reindex_segments,
)
from podcast_agent.insights.evidence_prompts import build_evidence_chunk_prompt
from podcast_agent.insights.llm import ModelWriter, build_default_model_writer
from podcast_agent.pipeline.artifacts import save_json


@dataclass(frozen=True)
class FollowupResult:
    question: str
    segments: list[dict[str, str]]
    sufficient: bool
    reason: str


@dataclass(frozen=True)
class SufficiencyResult:
    sufficient: bool
    reason: str


def run_followup_for_task(
    *,
    task_dir: Path,
    task_id: str,
    question: str,
    model_writer: ModelWriter | None = None,
    config: EvidenceConfig | None = None,
) -> FollowupResult:
    subtitle_path = find_subtitle_path(task_dir)
    if subtitle_path is None:
        raise FileNotFoundError("Task has no subtitle file")

    followup_dir = task_dir / "follow_up" / _new_run_id()
    followup_dir.mkdir(parents=True, exist_ok=True)
    source_url = resolve_source_url(task_dir)
    save_json(
        followup_dir / "question.json",
        {
            "task_id": task_id,
            "question": question,
            "source_url": source_url,
            "created_at": _utc_now(),
        },
    )

    recorder = ModelRecorder(model_writer or build_default_model_writer(), followup_dir / "llm.json")
    segments = search_followup_evidence(
        question=question,
        subtitle_path=subtitle_path,
        model_writer=recorder.writer("extract_evidence"),
        metadata=load_source_metadata(task_dir),
        config=config,
    )
    compat_segments = [compat_segment(segment) for segment in segments]
    sufficiency = judge_evidence_sufficiency(
        question=question,
        segments=compat_segments,
        source_url=source_url,
        source_metadata=load_source_metadata(task_dir),
        model_writer=recorder.writer("followup_sufficiency"),
    )

    save_json(followup_dir / "segments.json", {"task_id": task_id, "question": question, "segments": compat_segments})
    save_json(
        followup_dir / "sufficiency.json",
        {
            "task_id": task_id,
            "question": question,
            "sufficient": sufficiency.sufficient,
            "reason": sufficiency.reason,
        },
    )
    recorder.flush()
    return FollowupResult(
        question=question,
        segments=compat_segments,
        sufficient=sufficiency.sufficient,
        reason=sufficiency.reason,
    )


def search_followup_evidence(
    *,
    question: str,
    subtitle_path: Path,
    model_writer: ModelWriter,
    metadata: dict[str, Any] | None = None,
    config: EvidenceConfig | None = None,
) -> list[dict[str, Any]]:
    active_config = config or EvidenceConfig(max_final_segments=0)
    transcript_text = subtitle_path.read_text(encoding="utf-8")
    subtitle_segments = parse_subtitle_segments(transcript_text)
    if not subtitle_segments:
        return []

    active_metadata = metadata or {}
    chapters = _metadata_chapters(active_metadata)
    chunks = chunk_subtitle_segments_by_chapters(subtitle_segments, chapters)
    if not chunks:
        chunks = chunk_subtitle_segments(
            subtitle_segments,
            chunk_duration_seconds=active_config.chunk_duration_seconds,
            chunk_overlap_seconds=active_config.chunk_overlap_seconds,
        )

    subtitle_lookup = build_subtitle_lookup(subtitle_segments)
    outline_text = _outline_text(active_metadata) if active_config.include_outline else "- (no outline available)"
    chunk_candidates: list[dict[str, Any]] = []
    for chunk in chunks:
        prompt = build_evidence_chunk_prompt(
            question=question,
            chunk_text=format_chunk_transcript(chunk),
            outline_text=outline_text,
        )
        response = model_writer(prompt)
        raw_segments = normalize_segments(parse_model_json(response).get("segments"))
        chunk_candidates.extend(hydrate_segments_from_subtitles(raw_segments, subtitle_lookup, include_subtitles=False))

    final_segments = reindex_segments(normalize_segments(chunk_candidates))
    if active_config.max_final_segments > 0:
        final_segments = final_segments[: active_config.max_final_segments]
        final_segments = reindex_segments(final_segments)
    return final_segments


SUFFICIENCY_PROMPT_TEMPLATE = """You are a rigorous video evidence reviewer. Evaluate whether these evidence segments are sufficient to answer the question.

Video URL: {source_url}

Video metadata:
{source_metadata}

Question: {question}

Evidence segments:
{evidence_text}

Decision criteria:
- sufficient=true: the evidence directly covers the core facts needed to answer the question.
- sufficient=false: the evidence misses key facts, is only partially relevant, or cannot support a reliable answer.
- The reason must briefly explain why the evidence is sufficient or insufficient.
- Do not answer the question. Only judge whether the evidence is sufficient.

Return only a JSON object. Do not use Markdown. Do not add any extra explanation:
{{"sufficient": true, "reason": "The evidence covers the core facts needed to answer the question."}}

Return the JSON now:"""


def judge_evidence_sufficiency(
    *,
    question: str,
    segments: list[dict[str, str]],
    source_url: str | None,
    source_metadata: dict[str, Any] | None,
    model_writer: ModelWriter,
) -> SufficiencyResult:
    if not segments:
        return SufficiencyResult(False, "No relevant evidence segments were found for the question.")
    prompt = SUFFICIENCY_PROMPT_TEMPLATE.format(
        source_url=source_url or "(not available)",
        source_metadata=json.dumps(source_metadata or {}, ensure_ascii=False, indent=2) if source_metadata else "(not available)",
        question=question,
        evidence_text=_format_evidence_for_prompt(segments),
    )
    return _parse_sufficiency_response(model_writer(prompt))


def _format_evidence_for_prompt(segments: list[dict[str, str]]) -> str:
    lines = []
    for index, segment in enumerate(segments, start=1):
        start = segment.get("start", "")
        end = segment.get("end", "")
        text = segment.get("text", "")
        lines.append(f"{index}. [{start} --> {end}] {text}")
    return "\n".join(lines)


def _parse_sufficiency_response(output: str) -> SufficiencyResult:
    payload: Any = {}
    text = output.strip()
    try:
        parsed = json.loads(text)
        payload = parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                parsed = json.loads(match.group(0))
                payload = parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                payload = {}
    reason = str(payload.get("reason") or "").strip() if isinstance(payload, dict) else ""
    if not reason:
        reason = "The model did not return a valid sufficiency reason."
    return SufficiencyResult(sufficient=bool(payload.get("sufficient")) if isinstance(payload, dict) else False, reason=reason)


class ModelRecorder:
    def __init__(self, model_writer: ModelWriter, llm_path: Path) -> None:
        self.model_writer = model_writer
        self.llm_path = llm_path
        self.records: list[dict[str, Any]] = []

    def writer(self, operation: str) -> Callable[[str], str]:
        def call(prompt: str) -> str:
            started = perf_counter()
            output = self.model_writer(prompt)
            elapsed_ms = int((perf_counter() - started) * 1000)
            self.records.append(
                {
                    "operation": operation,
                    "prompt_chars": len(prompt),
                    "response_chars": len(output),
                    "elapsed_ms": elapsed_ms,
                    "elapsed": elapsed_ms / 1000.0,
                    "usage": {},
                }
            )
            return output

        return call

    def flush(self) -> None:
        save_json(self.llm_path, self.records)


def _metadata_chapters(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = metadata.get("chapters")
    if not isinstance(chapters, list):
        return []
    normalized = []
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
    return "\n".join(f"- {chapter['start']:.0f}s: {chapter['title']}" for chapter in chapters)


def _new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
