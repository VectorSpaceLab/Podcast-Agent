"""Compose Xiaohongshu note artifacts from podcast-agent insights."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from podcast_agent.errors import XhsReportError
from podcast_agent.insights.evidence import parse_model_json
from podcast_agent.insights.llm import ModelWriter
from podcast_agent.pipeline.artifacts import load_json, save_json
from podcast_agent.reports.xhs.prompts import build_xhs_composition_prompt


@dataclass(frozen=True)
class XhsComposeResult:
    note_path: Path
    post_meta_path: Path


def compose_xhs_report(
    *,
    output_dir: Path,
    model_writer: ModelWriter,
    angle: str | None = None,
) -> XhsComposeResult:
    """Create reports/xhs/note.md and reports/xhs/post_meta.json from existing artifacts."""
    metadata = _load_required_mapping(
        output_dir / "elements" / "metadata.json",
        "elements/metadata.json",
    )
    summary = _load_required_mapping(
        output_dir / "insights" / "summary.json",
        "insights/summary.json",
    )
    viewpoints = _load_required_mapping(
        output_dir / "insights" / "viewpoints.json",
        "insights/viewpoints.json",
    )

    prompt = build_xhs_composition_prompt(
        metadata=metadata,
        summary=summary,
        viewpoints=viewpoints,
        angle=angle,
    )
    payload = parse_model_json(model_writer(prompt).strip())
    composition = _normalize_composition(payload)

    xhs_dir = output_dir / "reports" / "xhs"
    xhs_dir.mkdir(parents=True, exist_ok=True)
    post_meta = {
        "title": composition["post_title"],
        "description": composition["post_description"],
        "tags": composition["tags"],
        "source_url": _source_url(metadata),
        "source_title": str(metadata.get("title") or "").strip(),
    }
    note = render_xhs_note_markdown(composition=composition, metadata=metadata)

    post_meta_path = xhs_dir / "post_meta.json"
    note_path = xhs_dir / "note.md"
    save_json(post_meta_path, post_meta)
    note_path.write_text(note.strip() + "\n", encoding="utf-8")
    return XhsComposeResult(note_path=note_path, post_meta_path=post_meta_path)


def render_xhs_note_markdown(*, composition: dict[str, Any], metadata: dict[str, Any]) -> str:
    """Render validated XHS composition JSON into note.md."""
    source = str(metadata.get("author") or metadata.get("uploader") or "").strip()
    source_title = str(metadata.get("title") or "").strip()
    source_label = " / ".join(part for part in [source, source_title] if part)
    frontmatter = [
        "---",
        f'title: "{_escape_yaml_string(composition["article_title"])}"',
        f'source: "{_escape_yaml_string(source_label)}"',
        f'url: "{_escape_yaml_string(_source_url(metadata))}"',
        'intro_image: "./cover.png"',
        "---",
        "",
    ]
    lines = frontmatter
    lines.extend([composition["cover_intro"], "", "---", ""])
    for index, section in enumerate(composition["sections"], start=1):
        heading = _strip_heading_number(str(section["heading"]).strip())
        lines.extend([f"## {index}. {heading}", ""])
        for paragraph in section["paragraphs"]:
            lines.extend([str(paragraph).strip(), ""])
        for quote in section["quotes"]:
            lines.extend([f"> {str(quote).strip()}", ""])
    closing = str(composition.get("closing") or "").strip()
    if closing:
        lines.extend([closing, ""])
    return "\n".join(lines)


def _normalize_composition(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        raise XhsReportError("XHS report generation failed: LLM output must be valid JSON.")
    required = ["post_title", "post_description", "cover_intro", "article_title", "sections"]
    missing = [field for field in required if not str(payload.get(field) or "").strip()]
    if missing:
        raise XhsReportError(f"XHS report generation failed: LLM output missing required fields: {', '.join(missing)}.")

    tags = payload.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    clean_tags = [str(tag).strip().lstrip("#") for tag in tags if str(tag).strip()]
    if not clean_tags:
        clean_tags = ["播客", "科技", "商业", "AI", "创业"]

    sections = payload.get("sections", [])
    if not isinstance(sections, list):
        sections = []
    clean_sections: list[dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        heading = str(section.get("heading") or "").strip()
        paragraphs = _clean_string_list(section.get("paragraphs"))
        quotes = _clean_string_list(section.get("quotes"))
        if heading and paragraphs:
            clean_sections.append({"heading": heading, "paragraphs": paragraphs, "quotes": quotes})
    if not clean_sections:
        raise XhsReportError("XHS report generation failed: LLM output sections must contain headings and paragraphs.")

    return {
        "post_title": _truncate_chars(str(payload["post_title"]).strip(), 20),
        "post_description": str(payload["post_description"]).strip(),
        "tags": clean_tags[:10],
        "cover_intro": str(payload["cover_intro"]).strip(),
        "article_title": str(payload["article_title"]).strip(),
        "sections": clean_sections,
        "closing": str(payload.get("closing") or "").strip(),
    }


def _clean_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _truncate_chars(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit]


def _strip_heading_number(value: str) -> str:
    return re.sub(r"^\s*\d+\s*[.．、]\s*", "", value).strip()


def _load_required_mapping(path: Path, name: str) -> dict[str, Any]:
    if not path.is_file():
        hint = "Run `podcast-agent full ...` first, or run the insights commands before xhs-report."
        if name == "elements/metadata.json":
            hint = "Run `podcast-agent run ...` or `podcast-agent full ...` first."
        raise XhsReportError(f"XHS report generation failed: {name} is required. {hint}")
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise XhsReportError(f"XHS report generation failed: {name} must be a JSON object.")
    return payload


def _source_url(metadata: dict[str, Any]) -> str:
    return str(metadata.get("webpage_url") or metadata.get("source_url") or metadata.get("url") or "").strip()


def _escape_yaml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
