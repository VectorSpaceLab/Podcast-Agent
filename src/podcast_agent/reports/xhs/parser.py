"""Parse Xiaohongshu note markdown into renderable blocks."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from podcast_agent.errors import XhsReportError

__all__ = ["parse_markdown_blocks", "parse_xhs_note"]


def parse_xhs_note(note_path: Path) -> dict[str, Any]:
    if not note_path.is_file():
        raise XhsReportError("XHS image rendering failed: note.md is required.")
    text = note_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise XhsReportError("XHS image rendering failed: note.md must start with frontmatter.")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise XhsReportError("XHS image rendering failed: note.md frontmatter is incomplete.")
    frontmatter_text = parts[1].strip()
    rest = parts[2].strip()
    frontmatter = _parse_frontmatter(frontmatter_text)
    intro, separator, body = rest.partition("\n---")
    if not separator or not intro.strip() or not body.strip():
        raise XhsReportError("XHS image rendering failed: note.md must contain intro and body separated by `---`.")
    return {
        "frontmatter": frontmatter,
        "intro": intro.strip(),
        "base_dir": note_path.parent,
        "body_blocks": parse_markdown_blocks(body.strip()),
    }


def parse_markdown_blocks(markdown: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    current: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append(_markdown_block("\n".join(current)))
                current = []
            continue
        if stripped.startswith("## "):
            if current:
                blocks.append(_markdown_block("\n".join(current)))
                current = []
            blocks.append({"kind": "heading", "text": stripped[3:].strip()})
            continue
        current.append(stripped)
    if current:
        blocks.append(_markdown_block("\n".join(current)))
    return blocks


def _markdown_block(text: str) -> dict[str, str]:
    stripped = text.strip()
    if stripped.startswith(">"):
        return {"kind": "quote", "text": stripped.lstrip("> ").strip()}
    return {"kind": "paragraph", "text": re.sub(r"\s+", " ", stripped)}


def _parse_frontmatter(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"')
    return result
