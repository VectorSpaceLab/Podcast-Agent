from pathlib import Path

import pytest

from podcast_agent.errors import XhsReportError
from podcast_agent.reports.xhs.parser import parse_xhs_note


def test_parse_xhs_note_extracts_intro_and_body_blocks(tmp_path: Path) -> None:
    note_path = tmp_path / "note.md"
    note_path.write_text(
        """---
title: "标题"
source: "来源"
url: "https://example.com"
intro_image: "./cover.png"
---

封面导语。

---

## 1. 观点

正文第一段。

> 引用一句。
""",
        encoding="utf-8",
    )

    note = parse_xhs_note(note_path)

    assert note["frontmatter"]["title"] == "标题"
    assert note["intro"] == "封面导语。"
    assert note["base_dir"] == tmp_path
    assert note["body_blocks"] == [
        {"kind": "heading", "text": "1. 观点"},
        {"kind": "paragraph", "text": "正文第一段。"},
        {"kind": "quote", "text": "引用一句。"},
    ]


def test_parse_xhs_note_requires_intro_body_separator(tmp_path: Path) -> None:
    note_path = tmp_path / "note.md"
    note_path.write_text("---\ntitle: \"标题\"\n---\n\n只有导语。\n", encoding="utf-8")

    with pytest.raises(XhsReportError, match="intro and body separated"):
        parse_xhs_note(note_path)
