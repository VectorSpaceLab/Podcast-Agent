"""Viewpoint detail generation from outline and evidence artifacts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from podcast_agent.errors import EvidenceExtractionError
from podcast_agent.insights.evidence import parse_model_json
from podcast_agent.insights.llm import ModelWriter
from podcast_agent.insights.outline import _source_url
from podcast_agent.insights.outline_prompts import ReportIntent, report_length_profile
from podcast_agent.insights.viewpoint_prompts import (
    build_viewpoint_detail_v1_prompt,
    find_viewpoint,
    get_viewpoints_from_outline,
    select_segments_for_viewpoint,
)
from podcast_agent.pipeline.artifacts import load_json, save_json


REPORT_VIEWPOINT_DETAIL_LIMIT = 8
VIEWPOINT_DETAIL_MAX_WORKERS = 8
REPORT_VIEWPOINT_SELECTION_SORT = "importance_score_desc_filter_then_outline_order"


def generate_viewpoints(
    *,
    output_dir: Path,
    model_writer: ModelWriter,
    report_intent: ReportIntent | None = None,
) -> dict[str, Any]:
    input_payload = _load_mapping(output_dir / "input.json", "input.json")
    question = str(input_payload.get("question") or "").strip()
    if not question:
        raise EvidenceExtractionError("Viewpoint generation failed: input.json question is required.")

    source = _load_optional_mapping(output_dir / "source.json")
    metadata = _load_optional_mapping(output_dir / "elements" / "metadata.json")
    evidence = _load_mapping(output_dir / "insights" / "evidence.json", "insights/evidence.json")
    outline = _load_mapping(output_dir / "insights" / "outline.json", "insights/outline.json")

    detail_limit = report_length_profile(report_intent.report_length).max_viewpoints if report_intent else REPORT_VIEWPOINT_DETAIL_LIMIT
    selected_viewpoints = select_viewpoints_for_detail(outline, limit=detail_limit)
    source_url = _source_url(source, metadata)
    video_title = str(metadata.get("title") or "")
    video_description = str(metadata.get("description") or "")
    viewpoint_ids = [
        str(viewpoint.get("id") or "").strip()
        for viewpoint in selected_viewpoints
        if isinstance(viewpoint, dict) and str(viewpoint.get("id") or "").strip()
    ]
    details_by_id: dict[str, dict[str, Any]] = {}
    if len(viewpoint_ids) > 1:
        max_workers = min(len(viewpoint_ids), VIEWPOINT_DETAIL_MAX_WORKERS)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _generate_and_save_viewpoint_detail,
                    output_dir=output_dir,
                    question=question,
                    outline=outline,
                    evidence=evidence,
                    viewpoint_id=viewpoint_id,
                    source_url=source_url,
                    video_title=video_title,
                    video_description=video_description,
                    model_writer=model_writer,
                    report_intent=report_intent,
                ): viewpoint_id
                for viewpoint_id in viewpoint_ids
            }
            for future in as_completed(futures):
                viewpoint_id, detail = future.result()
                details_by_id[viewpoint_id] = detail
    else:
        for viewpoint_id in viewpoint_ids:
            resolved_viewpoint_id, detail = _generate_and_save_viewpoint_detail(
                output_dir=output_dir,
                question=question,
                outline=outline,
                evidence=evidence,
                viewpoint_id=viewpoint_id,
                source_url=source_url,
                video_title=video_title,
                video_description=video_description,
                model_writer=model_writer,
                report_intent=report_intent,
            )
            details_by_id[resolved_viewpoint_id] = detail

    missing_viewpoint_ids = [viewpoint_id for viewpoint_id in viewpoint_ids if viewpoint_id not in details_by_id]
    if missing_viewpoint_ids:
        missing = ", ".join(missing_viewpoint_ids)
        raise EvidenceExtractionError(f"Viewpoint generation failed for selected viewpoints: {missing}.")

    details = [details_by_id[viewpoint_id] for viewpoint_id in viewpoint_ids]

    payload = build_viewpoints_payload(outline=outline, details=details, selection_policy={"max_viewpoints": detail_limit, "sort": REPORT_VIEWPOINT_SELECTION_SORT})
    save_json(output_dir / "insights" / "viewpoints.json", payload)
    return payload


def _generate_and_save_viewpoint_detail(
    *,
    output_dir: Path,
    question: str,
    outline: dict[str, Any],
    evidence: dict[str, Any],
    viewpoint_id: str,
    source_url: str | None,
    video_title: str,
    video_description: str,
    model_writer: ModelWriter,
    report_intent: ReportIntent | None,
) -> tuple[str, dict[str, Any]]:
    viewpoint = find_viewpoint(outline, viewpoint_id)
    if not select_segments_for_viewpoint(evidence=evidence, viewpoint=viewpoint):
        raise EvidenceExtractionError(f"Viewpoint generation failed: no evidence segments matched {viewpoint_id}.")
    detail = generate_viewpoint_detail(
        question=question,
        outline=outline,
        evidence=evidence,
        viewpoint_id=viewpoint_id,
        source_url=source_url,
        video_title=video_title,
        video_description=video_description,
        model_writer=model_writer,
        report_intent=report_intent,
    )
    save_json(output_dir / "insights" / f"viewpoint_{viewpoint_id}.json", detail)
    return viewpoint_id, detail


def generate_viewpoint_detail(
    *,
    question: str,
    outline: dict[str, Any],
    evidence: dict[str, Any],
    viewpoint_id: str,
    source_url: str | None,
    video_title: str,
    video_description: str,
    model_writer: ModelWriter,
    report_intent: ReportIntent | None = None,
) -> dict[str, Any]:
    prompt = build_viewpoint_detail_v1_prompt(
        question=question,
        video_title=video_title,
        video_description=video_description,
        outline=outline,
        evidence=evidence,
        viewpoint_id=viewpoint_id,
        source_url=source_url,
        report_intent=report_intent,
    )
    response = model_writer(prompt).strip()
    if not response:
        raise EvidenceExtractionError(f"Viewpoint generation failed: model returned empty content for {viewpoint_id}.")
    detail = parse_model_json(response)
    if not isinstance(detail.get("sub_theses"), list):
        raise EvidenceExtractionError(f"Viewpoint generation failed: model output missing sub_theses list for {viewpoint_id}.")
    return merge_viewpoint_detail_metadata(outline=outline, viewpoint_id=viewpoint_id, detail_payload=detail)


def merge_viewpoint_detail_metadata(
    *,
    outline: dict[str, Any],
    viewpoint_id: str,
    detail_payload: dict[str, Any],
) -> dict[str, Any]:
    viewpoint = find_viewpoint(outline, viewpoint_id)
    merged = dict(detail_payload)
    merged["viewpoint_id"] = viewpoint_id
    merged["viewpoint_title"] = str(viewpoint.get("title", "")).strip()
    merged["viewpoint_summary"] = str(viewpoint.get("summary", "")).strip()
    indexes = viewpoint.get("evidence_segment_indexes", [])
    merged["source_evidence_segment_indexes"] = indexes if isinstance(indexes, list) else []
    return merged


def select_viewpoints_for_detail(outline: dict[str, Any], *, limit: int = REPORT_VIEWPOINT_DETAIL_LIMIT) -> list[dict[str, Any]]:
    viewpoints = get_viewpoints_from_outline(outline)
    indexed_viewpoints = [
        (index, viewpoint)
        for index, viewpoint in enumerate(viewpoints)
        if isinstance(viewpoint, dict) and str(viewpoint.get("id", "")).strip()
    ]
    sorted_viewpoints = sorted(
        indexed_viewpoints,
        key=lambda item: (-importance_score(item[1].get("importance_score")), item[0]),
    )
    selected_by_importance = sorted_viewpoints[:limit]
    selected_in_outline_order = sorted(selected_by_importance, key=lambda item: item[0])
    return [viewpoint for _, viewpoint in selected_in_outline_order]


def build_viewpoints_payload(
    *,
    outline: dict[str, Any],
    details: list[dict[str, Any]],
    selection_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected_ids = [
        str(detail.get("viewpoint_id", "")).strip()
        for detail in details
        if isinstance(detail, dict) and str(detail.get("viewpoint_id", "")).strip()
    ]
    all_viewpoints = get_viewpoints_from_outline(outline)
    all_ids = [
        str(viewpoint.get("id", "")).strip()
        for viewpoint in all_viewpoints
        if isinstance(viewpoint, dict) and str(viewpoint.get("id", "")).strip()
    ]
    return {
        "report_type": "viewpoints",
        "selection_policy": selection_policy or {
            "max_viewpoints": REPORT_VIEWPOINT_DETAIL_LIMIT,
            "sort": REPORT_VIEWPOINT_SELECTION_SORT,
        },
        "selected_viewpoint_ids": selected_ids,
        "omitted_viewpoint_ids": [viewpoint_id for viewpoint_id in all_ids if viewpoint_id not in selected_ids],
        "viewpoint_breakdown": all_viewpoints,
        "viewpoint_details": details,
    }


def importance_score(value: Any) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 0
    return score if 1 <= score <= 5 else 0


def _load_mapping(path: Path, name: str) -> dict[str, Any]:
    if not path.is_file():
        raise EvidenceExtractionError(f"Viewpoint generation failed: {name} is required.")
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise EvidenceExtractionError(f"Viewpoint generation failed: {name} must be a JSON object.")
    return payload


def _load_optional_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}
