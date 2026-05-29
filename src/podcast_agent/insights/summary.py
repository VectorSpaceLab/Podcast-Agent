"""Summary generation from viewpoint artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from podcast_agent.insights.evidence import parse_model_json
from podcast_agent.insights.llm import ModelWriter
from podcast_agent.insights.outline import _source_url
from podcast_agent.insights.outline_prompts import ReportIntent
from podcast_agent.insights.summary_prompts import build_report_summary_v1_prompt
from podcast_agent.pipeline.artifacts import load_json, save_json


def generate_summary(
    *,
    output_dir: Path,
    model_writer: ModelWriter,
    report_intent: ReportIntent | None = None,
) -> dict[str, Any]:
    input_payload = _load_mapping(output_dir / "input.json", "input.json")
    question = str(input_payload.get("question") or "").strip()
    source = _load_optional_mapping(output_dir / "source.json")
    metadata = _load_optional_mapping(output_dir / "elements" / "metadata.json")
    viewpoints_payload = _load_mapping(output_dir / "insights" / "viewpoints.json", "insights/viewpoints.json")
    summary_viewpoints = build_summary_viewpoints_payload(viewpoints_payload)
    if not summary_viewpoints["viewpoints"]:
        summary = empty_summary(report_intent.report_language if report_intent else "zh-Hans")
        save_json(output_dir / "insights" / "summary.json", summary)
        return summary

    prompt = build_report_summary_v1_prompt(
        question=question,
        viewpoints=summary_viewpoints,
        chapters=metadata.get("chapters") if isinstance(metadata.get("chapters"), list) else [],
        source_url=_source_url(source, metadata),
        report_intent=report_intent,
    )
    summary = parse_model_json(model_writer(prompt).strip())
    if not summary:
        summary = empty_summary(report_intent.report_language if report_intent else "zh-Hans")
    save_json(output_dir / "insights" / "summary.json", summary)
    return summary


def build_summary_viewpoints_payload(viewpoints_payload: dict[str, Any]) -> dict[str, Any]:
    breakdown = viewpoints_payload.get("viewpoint_breakdown", [])
    details = viewpoints_payload.get("viewpoint_details", [])
    if not isinstance(breakdown, list):
        breakdown = []
    if not isinstance(details, list):
        details = []
    details_by_id: dict[str, dict[str, Any]] = {}
    for detail in details:
        if not isinstance(detail, dict):
            continue
        viewpoint_id = str(detail.get("viewpoint_id", "")).strip()
        if viewpoint_id:
            details_by_id[viewpoint_id] = detail

    condensed: list[dict[str, Any]] = []
    for viewpoint in breakdown:
        if not isinstance(viewpoint, dict):
            continue
        viewpoint_id = str(viewpoint.get("id", "")).strip()
        detail = details_by_id.get(viewpoint_id)
        if detail is None:
            continue
        sub_theses = detail.get("sub_theses", [])
        if not isinstance(sub_theses, list):
            sub_theses = []
        condensed_sub_theses = [
            {
                key: value
                for key, value in {
                    "title": str(sub_thesis.get("title", "")).strip(),
                    "explanation": str(sub_thesis.get("explanation", "")).strip(),
                }.items()
                if value
            }
            for sub_thesis in sub_theses
            if isinstance(sub_thesis, dict) and str(sub_thesis.get("title", "")).strip()
        ]
        condensed.append(
            {
                "id": viewpoint_id,
                "title": str(viewpoint.get("title", "")).strip(),
                "summary": str(viewpoint.get("summary", "")).strip(),
                "importance_score": _sanitize_importance_score(viewpoint.get("importance_score")),
                "importance_reason": str(viewpoint.get("importance_reason", "")).strip(),
                "sub_theses": condensed_sub_theses,
            }
        )
    return {"viewpoints": condensed}


def empty_summary(language: object) -> dict[str, Any]:
    return {
        "report_type": "summary",
        "language": language,
        "introduction": "",
        "core_conclusions": [],
        "viewpoint_order": [],
        "one_paragraph_takeaway": "",
    }


def _sanitize_importance_score(value: Any) -> int | None:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    if 1 <= score <= 5:
        return score
    return None


def _load_mapping(path: Path, name: str) -> dict[str, Any]:
    if not path.is_file():
        from podcast_agent.errors import EvidenceExtractionError

        raise EvidenceExtractionError(f"Summary generation failed: {name} is required.")
    payload = load_json(path)
    if not isinstance(payload, dict):
        from podcast_agent.errors import EvidenceExtractionError

        raise EvidenceExtractionError(f"Summary generation failed: {name} must be a JSON object.")
    return payload


def _load_optional_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}
