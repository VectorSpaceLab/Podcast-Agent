"""Markdown report rendering from structured insight artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from podcast_agent.errors import EvidenceExtractionError
from podcast_agent.intent import ReportIntent, load_report_intent, normalize_report_language
from podcast_agent.pipeline.artifacts import load_json
from podcast_agent.reports.html import render_html_report


def render_markdown_report(*, output_dir: Path, report_intent: ReportIntent | None = None) -> Path:
    """Render reports/report.md from existing pipeline artifacts."""
    input_payload = _load_mapping(output_dir / "input.json", "input.json")
    source = _load_optional_mapping(output_dir / "source.json")
    metadata = _load_optional_mapping(output_dir / "elements" / "metadata.json")
    evidence = _load_mapping(output_dir / "insights" / "evidence.json", "insights/evidence.json")
    outline = _load_mapping(output_dir / "insights" / "outline.json", "insights/outline.json")
    viewpoints = _load_mapping(output_dir / "insights" / "viewpoints.json", "insights/viewpoints.json")
    summary = _load_mapping(output_dir / "insights" / "summary.json", "insights/summary.json")

    details = viewpoints.get("viewpoint_details", [])
    if not isinstance(details, list):
        details = []
    active_intent = report_intent or load_report_intent(output_dir / "insights" / "intent.json")
    markdown = render_report_markdown(
        question=str(input_payload.get("question") or "").strip(),
        summary=summary,
        outline=outline,
        details=[detail for detail in details if isinstance(detail, dict)],
        evidence=evidence,
        source_url=_source_url(source, metadata, input_payload),
        metadata=metadata,
        report_intent=active_intent,
    )
    report_path = output_dir / "reports" / "report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown.strip() + "\n", encoding="utf-8")
    render_html_report(output_dir=output_dir, markdown_path=report_path, metadata=metadata)
    return report_path


def render_report_markdown(
    *,
    question: str,
    summary: dict[str, Any],
    outline: dict[str, Any],
    details: list[dict[str, Any]],
    evidence: dict[str, Any],
    source_url: str | None = None,
    metadata: dict[str, Any] | None = None,
    report_intent: ReportIntent | None = None,
) -> str:
    """Render final Markdown using the workflow-v2 artifact sequence."""
    metadata = metadata or {}
    segment_index_map = _build_segment_index_map(evidence)
    locale = _render_locale(report_intent)
    lines: list[str] = []
    title = str(metadata.get("title") or locale["fallback_title"]).strip()
    lines.extend([f"# {title}", ""])
    lines.extend(_render_introduction(summary, locale))
    lines.extend(_render_core_conclusions(summary, locale))
    lines.extend(_render_viewpoint_sections(summary, outline, details, segment_index_map, source_url, locale))
    lines.extend(_render_takeaway(summary, locale))
    lines.extend(_render_source_info(metadata, source_url, locale))
    return "\n".join(lines).strip()


def _render_locale(report_intent: ReportIntent | None) -> dict[str, Any]:
    language = normalize_report_language(report_intent.report_language) if report_intent else "zh-Hans"
    if language.startswith("en"):
        return {
            "fallback_title": "Video Report",
            "titles": {
                "introduction": "Introduction",
                "core_conclusions": "Core Conclusions",
                "viewpoint_breakdown": "Viewpoint Breakdown",
                "takeaway": "Takeaway",
                "source_info": "Source Info",
            },
            "colon": ": ",
            "viewpoint_fallback": "Viewpoint {index}",
            "source_labels": {
                "title": "Title",
                "author": "Author",
                "url": "URL",
                "duration": "Duration",
            },
        }
    return {
        "fallback_title": "视频报告",
        "titles": {
            "introduction": "导读",
            "core_conclusions": "核心结论",
            "viewpoint_breakdown": "观点拆解",
            "takeaway": "总结",
            "source_info": "来源信息",
        },
        "colon": "：",
        "viewpoint_fallback": "观点 {index}",
        "source_labels": {
            "title": "标题",
            "author": "作者",
            "url": "链接",
            "duration": "时长",
        },
    }


def _render_introduction(summary: dict[str, Any], locale: dict[str, Any]) -> list[str]:
    introduction = str(summary.get("introduction", "")).strip()
    if not introduction:
        return []
    return [f"## {locale['titles']['introduction']}", "", introduction, ""]


def _render_core_conclusions(summary: dict[str, Any], locale: dict[str, Any]) -> list[str]:
    lines = [f"## {locale['titles']['core_conclusions']}", ""]
    conclusions = summary.get("core_conclusions", [])
    if not isinstance(conclusions, list):
        return lines
    for item in conclusions:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        rationale = str(item.get("rationale", "")).strip()
        if not title:
            continue
        lines.append(f"- **{title}**{locale['colon']}{rationale}" if rationale else f"- **{title}**")
    lines.append("")
    return lines


def _render_viewpoint_sections(
    summary: dict[str, Any],
    outline: dict[str, Any],
    details: list[dict[str, Any]],
    segment_index_map: dict[int, dict[str, Any]],
    source_url: str | None,
    locale: dict[str, Any],
) -> list[str]:
    lines = [f"## {locale['titles']['viewpoint_breakdown']}", ""]
    viewpoints = outline.get("viewpoint_breakdown", [])
    if not isinstance(viewpoints, list):
        return lines

    details_by_id = {
        str(detail.get("viewpoint_id", "")).strip(): detail
        for detail in details
        if str(detail.get("viewpoint_id", "")).strip()
    }
    rendered_idx = 0
    for viewpoint in _ordered_viewpoints_for_render(summary, viewpoints, details_by_id):
        viewpoint_id = str(viewpoint.get("id", "")).strip()
        detail = details_by_id.get(viewpoint_id, {})
        sub_theses = detail.get("sub_theses", []) if isinstance(detail, dict) else []
        if not isinstance(sub_theses, list):
            sub_theses = []
        if not any(isinstance(item, dict) and str(item.get("title", "")).strip() for item in sub_theses):
            continue

        rendered_idx += 1
        title = str(viewpoint.get("title", "")).strip() or locale["viewpoint_fallback"].format(index=rendered_idx)
        lines.extend([f"### {rendered_idx}. {title}", ""])
        for sub_thesis in sub_theses:
            if not isinstance(sub_thesis, dict):
                continue
            thesis_title = str(sub_thesis.get("title", "")).strip()
            if not thesis_title:
                continue
            explanation = str(sub_thesis.get("explanation", "")).strip()
            timestamps = _merge_sub_thesis_timestamps(
                sub_thesis.get("supporting_evidence_segment_indexes", []),
                segment_index_map,
                source_url,
            )
            bullet = f"- **{thesis_title}**"
            if explanation:
                bullet += f"{locale['colon']}{explanation}"
            if timestamps:
                bullet += " " + " ".join(timestamps)
            lines.append(bullet)
            quote_lines = _render_quotes(sub_thesis.get("quotes", []), source_url)
            lines.extend(quote_lines)
            lines.append("")
    if lines and lines[-1] == "":
        return lines
    return [*lines, ""]


def _render_quotes(quotes: list[Any], source_url: str | None) -> list[str]:
    lines: list[str] = []
    for quote in quotes:
        if not isinstance(quote, dict):
            continue
        text = str(quote.get("text") or quote.get("source_text") or "").strip()
        if not text:
            continue
        timestamp = _format_timestamp_link(str(quote.get("subtitle_start", "")).strip(), source_url)
        lines.append(f"    > “{text}” {timestamp}" if timestamp else f"    > “{text}”")
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _render_takeaway(summary: dict[str, Any], locale: dict[str, Any]) -> list[str]:
    takeaway = str(summary.get("one_paragraph_takeaway") or summary.get("one_sentence_takeaway") or "").strip()
    if not takeaway:
        return []
    return [f"## {locale['titles']['takeaway']}", "", takeaway, ""]


def _render_source_info(metadata: dict[str, Any], source_url: str | None, locale: dict[str, Any]) -> list[str]:
    lines = [f"## {locale['titles']['source_info']}", ""]
    source_title = str(metadata.get("title") or "").strip()
    author = str(metadata.get("author") or metadata.get("uploader") or "").strip()
    duration = _format_duration(metadata.get("duration_seconds"))
    labels = locale["source_labels"]
    if source_title:
        lines.append(f"- {labels['title']}{locale['colon']}{source_title}")
    if author:
        lines.append(f"- {labels['author']}{locale['colon']}{author}")
    if source_url:
        lines.append(f"- {labels['url']}{locale['colon']}{source_url}")
    if duration:
        lines.append(f"- {labels['duration']}{locale['colon']}{duration}")
    return lines


def _ordered_viewpoints_for_render(
    summary: dict[str, Any],
    viewpoints: list[Any],
    details_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    valid_viewpoints = [
        viewpoint
        for viewpoint in viewpoints
        if isinstance(viewpoint, dict) and str(viewpoint.get("id", "")).strip() in details_by_id
    ]
    viewpoints_by_id = {str(viewpoint.get("id", "")).strip(): viewpoint for viewpoint in valid_viewpoints}
    ordered_ids = _summary_viewpoint_order(summary) or _core_conclusion_viewpoint_order(summary)
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for viewpoint_id in ordered_ids:
        viewpoint = viewpoints_by_id.get(viewpoint_id)
        if viewpoint is None or viewpoint_id in seen:
            continue
        ordered.append(viewpoint)
        seen.add(viewpoint_id)
    for viewpoint in valid_viewpoints:
        viewpoint_id = str(viewpoint.get("id", "")).strip()
        if viewpoint_id and viewpoint_id not in seen:
            ordered.append(viewpoint)
            seen.add(viewpoint_id)
    return ordered


def _summary_viewpoint_order(summary: dict[str, Any]) -> list[str]:
    raw_order = summary.get("viewpoint_order", [])
    if not isinstance(raw_order, list):
        return []
    ordered_ids: list[str] = []
    for item in raw_order:
        viewpoint_id = str(item).strip()
        if viewpoint_id and viewpoint_id not in ordered_ids:
            ordered_ids.append(viewpoint_id)
    return ordered_ids


def _core_conclusion_viewpoint_order(summary: dict[str, Any]) -> list[str]:
    conclusions = summary.get("core_conclusions", [])
    if not isinstance(conclusions, list):
        return []
    ordered_ids: list[str] = []
    for conclusion in conclusions:
        if not isinstance(conclusion, dict):
            continue
        raw_ids = conclusion.get("source_viewpoint_ids", conclusion.get("synthesized_viewpoint_ids", []))
        if not isinstance(raw_ids, list):
            continue
        for item in raw_ids:
            viewpoint_id = str(item).strip()
            if viewpoint_id and viewpoint_id not in ordered_ids:
                ordered_ids.append(viewpoint_id)
    return ordered_ids


def _build_segment_index_map(evidence: dict[str, Any]) -> dict[int, dict[str, Any]]:
    segments = evidence.get("segments", [])
    if not isinstance(segments, list):
        return {}
    index_map: dict[int, dict[str, Any]] = {}
    for position, segment in enumerate(segments):
        if not isinstance(segment, dict):
            continue
        try:
            index = int(segment.get("index", position))
        except (TypeError, ValueError):
            index = position
        index_map[index] = segment
    return index_map


def _merge_sub_thesis_timestamps(
    supporting_indexes: Any,
    segment_index_map: dict[int, dict[str, Any]],
    source_url: str | None,
) -> list[str]:
    if not isinstance(supporting_indexes, list):
        return []
    normalized_indexes: list[int] = []
    for item in supporting_indexes:
        try:
            index = int(item)
        except (TypeError, ValueError):
            continue
        if index in segment_index_map and index not in normalized_indexes:
            normalized_indexes.append(index)
    if not normalized_indexes:
        return []

    groups: list[list[int]] = []
    current_group: list[int] = []
    last_index: int | None = None
    last_seconds: int | None = None
    for index in normalized_indexes:
        seconds = _time_to_seconds(str(segment_index_map.get(index, {}).get("start", "")))
        should_merge = bool(
            current_group
            and (
                (last_index is not None and index == last_index + 1)
                or (last_seconds is not None and seconds is not None and seconds - last_seconds <= 120)
            )
        )
        if not current_group or should_merge:
            current_group.append(index)
        else:
            groups.append(current_group)
            current_group = [index]
        last_index = index
        last_seconds = seconds
    if current_group:
        groups.append(current_group)

    timestamps: list[str] = []
    for group in groups:
        timestamp = _format_timestamp_link(str(segment_index_map.get(group[0], {}).get("start", "")), source_url)
        if timestamp and timestamp not in timestamps:
            timestamps.append(timestamp)
    return timestamps


def _format_timestamp_link(time_str: str | None, source_url: str | None) -> str | None:
    seconds = _time_to_seconds(time_str)
    if seconds is None:
        return None
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    label = f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"
    if source_url and source_url.strip():
        return f"[`{label}`]({_url_with_timestamp(source_url.strip(), seconds)})"
    return f"[`{label}`]"


def _time_to_seconds(time_str: str | None) -> int | None:
    if not time_str or not isinstance(time_str, str):
        return None
    parts = time_str.strip().replace(",", ".").split(":")
    try:
        if len(parts) == 3:
            return int(int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2]))
        if len(parts) == 2:
            return int(int(parts[0]) * 60 + float(parts[1]))
    except ValueError:
        return None
    return None


def _url_with_timestamp(source_url: str, seconds: int) -> str:
    parsed = urlparse(source_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["t"] = [f"{seconds}s"]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def _format_duration(value: Any) -> str:
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        return ""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _source_url(*payloads: dict[str, Any]) -> str | None:
    for payload in payloads:
        for key in ("source_url", "webpage_url", "url"):
            value = str(payload.get(key) or "").strip()
            if value:
                return value
    return None


def _load_mapping(path: Path, name: str) -> dict[str, Any]:
    if not path.is_file():
        raise EvidenceExtractionError(f"Markdown report rendering failed: {name} is required.")
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise EvidenceExtractionError(f"Markdown report rendering failed: {name} must be a JSON object.")
    return payload


def _load_optional_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}
