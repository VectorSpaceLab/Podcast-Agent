"""Outline / viewpoint planning from evidence artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from podcast_agent.errors import EvidenceExtractionError
from podcast_agent.insights.evidence import parse_model_json
from podcast_agent.insights.llm import ModelWriter
from podcast_agent.insights.outline_prompts import ReportIntent, build_report_outline_v1_prompt
from podcast_agent.pipeline.artifacts import load_json, save_json


def generate_outline(
    *,
    output_dir: Path,
    model_writer: ModelWriter,
    report_intent: ReportIntent | None = None,
) -> dict[str, Any]:
    input_payload = _load_mapping(output_dir / "input.json", "input.json")
    question = str(input_payload.get("question") or "").strip()
    if not question:
        raise EvidenceExtractionError("Outline generation failed: input.json question is required.")

    source = _load_optional_mapping(output_dir / "source.json")
    metadata = _load_optional_mapping(output_dir / "elements" / "metadata.json")
    evidence = _load_mapping(output_dir / "insights" / "evidence.json", "insights/evidence.json")
    segments = evidence.get("segments")
    if not isinstance(segments, list):
        raise EvidenceExtractionError("Outline generation failed: evidence.json segments must be a list.")
    if not segments:
        outline = {"viewpoint_breakdown": []}
        save_json(output_dir / "insights" / "outline.json", outline)
        return outline

    prompt = build_report_outline_v1_prompt(
        question=question,
        evidence=evidence,
        source_url=_source_url(source, metadata),
        video_title=str(metadata.get("title") or ""),
        video_description=str(metadata.get("description") or ""),
        chapters=metadata.get("chapters") if isinstance(metadata.get("chapters"), list) else [],
        report_intent=report_intent,
    )
    response = model_writer(prompt).strip()
    if not response:
        raise EvidenceExtractionError("Outline generation failed: model returned empty content.")
    outline = parse_model_json(response)
    if not isinstance(outline.get("viewpoint_breakdown"), list):
        raise EvidenceExtractionError("Outline generation failed: model output missing viewpoint_breakdown list.")
    save_json(output_dir / "insights" / "outline.json", outline)
    return outline


def _source_url(source: dict[str, Any], metadata: dict[str, Any]) -> str | None:
    return str(source.get("url") or metadata.get("source_url") or metadata.get("webpage_url") or "").strip() or None


def _load_mapping(path: Path, name: str) -> dict[str, Any]:
    if not path.is_file():
        raise EvidenceExtractionError(f"Outline generation failed: {name} is required.")
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise EvidenceExtractionError(f"Outline generation failed: {name} must be a JSON object.")
    return payload


def _load_optional_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}
