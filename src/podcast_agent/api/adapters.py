"""Adapters from Podcast-Agent artifacts to VideoChat-compatible API fields."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def find_report_path(task_dir: Path) -> Path | None:
    candidates = [
        task_dir / "reports" / "report.md",
        task_dir / "report" / "report.md",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    reports = sorted(task_dir.rglob("report.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def read_report_markdown(task_dir: Path) -> tuple[Path, str] | None:
    report_path = find_report_path(task_dir)
    if report_path is None:
        return None
    return report_path, report_path.read_text(encoding="utf-8")


def find_subtitle_path(task_dir: Path) -> Path | None:
    candidates = [
        task_dir / "elements" / "transcript.vtt",
        task_dir / "elements" / "transcript.srt",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    for directory in (task_dir / "input", task_dir / "report"):
        if not directory.exists():
            continue
        for pattern in ("*.srt", "*.vtt"):
            matches = sorted(directory.glob(pattern))
            if matches:
                return matches[0]

    matches = sorted([*task_dir.rglob("*.vtt"), *task_dir.rglob("*.srt")])
    return matches[0] if matches else None


def load_source_metadata(task_dir: Path) -> dict[str, Any]:
    candidates = [
        task_dir / "elements" / "metadata.json",
        task_dir / "input" / "SOURCE_METADATA.json",
        task_dir / "report" / "SOURCE_METADATA.json",
    ]
    for candidate in candidates:
        payload = _load_optional_mapping(candidate)
        if payload:
            return payload
    matches = sorted(task_dir.rglob("SOURCE_METADATA.json"))
    for match in matches:
        payload = _load_optional_mapping(match)
        if payload:
            return payload
    return {}


def resolve_source_url(task_dir: Path) -> str | None:
    metadata = load_source_metadata(task_dir)
    for key in ("source_url", "webpage_url", "url"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value

    for path in (task_dir / "source.json", task_dir / "input.json"):
        payload = _load_optional_mapping(path)
        for key in ("source_url", "webpage_url", "url"):
            value = str(payload.get(key) or "").strip()
            if value:
                return value
    return None


def compat_timestamp(timestamp: object) -> str:
    return str(timestamp or "").strip().replace(".", ",")


def compat_segment(segment: dict[str, Any]) -> dict[str, str]:
    return {
        "start": compat_timestamp(segment.get("start")),
        "end": compat_timestamp(segment.get("end")),
        "text": str(segment.get("text") or "").strip(),
    }


def _load_optional_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
