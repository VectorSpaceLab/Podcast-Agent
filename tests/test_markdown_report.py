from pathlib import Path

import pytest

from podcast_agent.errors import ReportRenderError
from podcast_agent.intent import ReportIntent
from podcast_agent.pipeline.artifacts import save_json
from podcast_agent.reports.html import render_html_report, render_pdf_report
from podcast_agent.reports.markdown import render_markdown_report, render_report_markdown


def _write_report_inputs(output_dir: Path) -> None:
    thumbnail_path = output_dir / "elements" / "xxxx.jpg"
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    thumbnail_path.write_bytes(b"fake jpg")
    save_json(output_dir / "input.json", {"url": "https://www.youtube.com/watch?v=xxxx", "question": "这个视频讲了什么？"})
    save_json(output_dir / "source.json", {"source_type": "youtube", "url": "https://www.youtube.com/watch?v=xxxx", "source_id": "xxxx"})
    save_json(
        output_dir / "elements" / "metadata.json",
        {
            "title": "Example Video",
            "author": "Example Channel",
            "source_url": "https://www.youtube.com/watch?v=xxxx",
            "duration_seconds": 125,
            "thumbnail_path": str(thumbnail_path),
        },
    )
    save_json(
        output_dir / "insights" / "evidence.json",
        {
            "segments": [
                {"index": 1, "start": "00:00:10.000", "end": "00:00:40.000", "text": "第一段"},
                {"index": 2, "start": "00:00:50.000", "end": "00:01:20.000", "text": "第二段"},
                {"index": 5, "start": "00:04:10.000", "end": "00:04:30.000", "text": "第五段"},
            ]
        },
    )
    save_json(
        output_dir / "insights" / "outline.json",
        {
            "viewpoint_breakdown": [
                {"id": "V1", "title": "第一个观点", "evidence_segment_indexes": [1, 2]},
                {"id": "V2", "title": "第二个观点", "evidence_segment_indexes": [5]},
            ]
        },
    )
    save_json(
        output_dir / "insights" / "viewpoints.json",
        {
            "viewpoint_breakdown": [
                {"id": "V1", "title": "第一个观点", "evidence_segment_indexes": [1, 2]},
                {"id": "V2", "title": "第二个观点", "evidence_segment_indexes": [5]},
            ],
            "viewpoint_details": [
                {
                    "viewpoint_id": "V1",
                    "sub_theses": [
                        {
                            "title": "子论点一",
                            "explanation": "解释一",
                            "supporting_evidence_segment_indexes": [1, 2],
                            "quotes": [
                                {"text": "引用一", "subtitle_start": "00:00:10.000"},
                                {"text": "引用二", "subtitle_start": "00:00:50.000"},
                            ],
                        }
                    ],
                },
                {
                    "viewpoint_id": "V2",
                    "sub_theses": [
                        {
                            "title": "子论点二",
                            "explanation": "解释二",
                            "supporting_evidence_segment_indexes": [5],
                        }
                    ],
                },
            ],
        },
    )
    save_json(
        output_dir / "insights" / "summary.json",
        {
            "report_type": "summary",
            "report_title": "物理AI转折点",
            "introduction": "导读内容。",
            "core_conclusions": [
                {
                    "title": "核心结论",
                    "rationale": "核心理由。",
                    "source_viewpoint_ids": ["V2"],
                }
            ],
            "viewpoint_order": ["V2", "V1"],
            "one_paragraph_takeaway": "一句总结。",
        },
    )


def test_render_report_markdown_uses_workflow_v2_artifact_order() -> None:
    markdown = render_report_markdown(
        question="问题？",
        metadata={"title": "标题", "author": "作者", "duration_seconds": 65},
        source_url="https://www.youtube.com/watch?v=xxxx",
        evidence={"segments": [{"index": 1, "start": "00:00:05.000"}]},
        outline={"viewpoint_breakdown": [{"id": "V1", "title": "观点", "evidence_segment_indexes": [1]}]},
        details=[
            {
                "viewpoint_id": "V1",
                "sub_theses": [
                    {
                        "title": "子论点",
                        "explanation": "解释",
                        "supporting_evidence_segment_indexes": [1],
                    }
                ],
            }
        ],
        summary={
            "report_title": "AI转折点",
            "introduction": "导读。",
            "core_conclusions": [{"title": "结论", "rationale": "理由。"}],
            "one_paragraph_takeaway": "收束。",
        },
    )

    assert markdown.index("## 导读") < markdown.index("## 核心结论")
    assert markdown.index("## 核心结论") < markdown.index("## 观点拆解")
    assert markdown.index("## 观点拆解") < markdown.index("## 总结")
    assert "### 1. 观点 [`00:05`](https://www.youtube.com/watch?v=xxxx&t=5s)" in markdown
    assert "- **子论点**：解释" in markdown
    assert "- **子论点**：解释 [`00:05`](https://www.youtube.com/watch?v=xxxx&t=5s)" not in markdown
    assert "- 作者：作者" in markdown
    assert "- 时长：1:05" in markdown


def test_render_report_markdown_uses_english_locale_for_english_intent() -> None:
    markdown = render_report_markdown(
        question="What changed?",
        metadata={"title": "Demo", "author": "Author"},
        source_url="https://www.youtube.com/watch?v=xxxx",
        evidence={"segments": []},
        outline={"viewpoint_breakdown": []},
        details=[],
        summary={
            "report_title": "AI Inflection",
            "introduction": "Intro.",
            "core_conclusions": [{"title": "Conclusion", "rationale": "Reason."}],
            "one_paragraph_takeaway": "Takeaway.",
        },
        report_intent=ReportIntent(report_language="en", report_length="brief"),
    )

    assert "## Introduction" in markdown
    assert "## Core Conclusions" in markdown
    assert "## Viewpoint Breakdown" in markdown
    assert "## Takeaway" in markdown
    assert "## Source Info" in markdown
    assert markdown.startswith("# AI Inflection")
    assert "- **Conclusion**: Reason." in markdown
    assert "- Author: Author" in markdown


def test_render_report_markdown_normalizes_bilibili_trailing_slash_timestamp_url() -> None:
    markdown = render_report_markdown(
        question="讲了什么？",
        metadata={"title": "Demo", "author": "Author"},
        source_url="https://www.bilibili.com/video/BV1vL4y157R1/",
        evidence={"segments": [{"index": 1, "start": "00:10:01.000"}]},
        outline={"viewpoint_breakdown": [{"id": "V1", "title": "观点", "evidence_segment_indexes": [1]}]},
        details=[
            {
                "viewpoint_id": "V1",
                "sub_theses": [
                    {
                        "title": "子论点",
                        "explanation": "解释",
                        "supporting_evidence_segment_indexes": [1],
                    }
                ],
            }
        ],
        summary={
            "report_title": "标题",
            "introduction": "导读。",
            "core_conclusions": [{"title": "结论", "rationale": "理由。"}],
            "one_paragraph_takeaway": "总结。",
        },
    )

    assert "### 1. 观点 [`10:01`](https://www.bilibili.com/video/BV1vL4y157R1?t=601s)" in markdown
    assert "- **子论点**：解释 [`10:01`](https://www.bilibili.com/video/BV1vL4y157R1?t=601s)" not in markdown


def test_render_report_markdown_uses_one_viewpoint_timestamp_and_keeps_quote_timestamps() -> None:
    markdown = render_report_markdown(
        question="讲了什么？",
        metadata={"title": "Demo", "author": "Author"},
        source_url="https://www.youtube.com/watch?v=xxxx",
        evidence={
            "segments": [
                {"index": 1, "start": "00:00:05.000"},
                {"index": 2, "start": "00:01:30.000"},
            ]
        },
        outline={"viewpoint_breakdown": [{"id": "V1", "title": "观点", "evidence_segment_indexes": ["bad", 1, 2]}]},
        details=[
            {
                "viewpoint_id": "V1",
                "sub_theses": [
                    {
                        "title": "子论点一",
                        "explanation": "解释一",
                        "supporting_evidence_segment_indexes": [1],
                        "quotes": [{"text": "引用一", "subtitle_start": "00:00:08.000"}],
                    },
                    {
                        "title": "子论点二",
                        "explanation": "解释二",
                        "supporting_evidence_segment_indexes": [1],
                        "quotes": [{"text": "引用二", "subtitle_start": "00:01:40.000"}],
                    },
                ],
            }
        ],
        summary={
            "report_title": "标题",
            "introduction": "导读。",
            "core_conclusions": [{"title": "结论", "rationale": "理由。"}],
            "one_paragraph_takeaway": "总结。",
        },
    )

    assert markdown.count("[`00:05`](https://www.youtube.com/watch?v=xxxx&t=5s)") == 1
    assert "### 1. 观点 [`00:05`](https://www.youtube.com/watch?v=xxxx&t=5s)" in markdown
    assert "- **子论点一**：解释一" in markdown
    assert "- **子论点二**：解释二" in markdown
    assert "- **子论点一**：解释一 [`00:05`](https://www.youtube.com/watch?v=xxxx&t=5s)" not in markdown
    assert "- **子论点二**：解释二 [`00:05`](https://www.youtube.com/watch?v=xxxx&t=5s)" not in markdown
    assert "> “引用一” [`00:08`](https://www.youtube.com/watch?v=xxxx&t=8s)" in markdown
    assert "> “引用二” [`01:40`](https://www.youtube.com/watch?v=xxxx&t=100s)" in markdown


def test_render_report_markdown_skips_viewpoint_timestamp_without_valid_evidence_index() -> None:
    markdown = render_report_markdown(
        question="讲了什么？",
        metadata={"title": "Demo", "author": "Author"},
        source_url="https://www.youtube.com/watch?v=xxxx",
        evidence={"segments": [{"index": 1, "start": "00:00:05.000"}]},
        outline={"viewpoint_breakdown": [{"id": "V1", "title": "观点", "evidence_segment_indexes": ["bad", 2]}]},
        details=[
            {
                "viewpoint_id": "V1",
                "sub_theses": [
                    {
                        "title": "子论点",
                        "explanation": "解释",
                        "supporting_evidence_segment_indexes": [1],
                    }
                ],
            }
        ],
        summary={
            "report_title": "标题",
            "introduction": "导读。",
            "core_conclusions": [{"title": "结论", "rationale": "理由。"}],
            "one_paragraph_takeaway": "总结。",
        },
    )

    assert "### 1. 观点" in markdown
    assert "### 1. 观点 [`00:05`](https://www.youtube.com/watch?v=xxxx&t=5s)" not in markdown
    assert "- **子论点**：解释 [`00:05`](https://www.youtube.com/watch?v=xxxx&t=5s)" not in markdown


def test_render_markdown_report_writes_report_file(tmp_path: Path) -> None:
    _write_report_inputs(tmp_path)

    report_path = render_markdown_report(output_dir=tmp_path)
    markdown = report_path.read_text(encoding="utf-8")
    html_path = tmp_path / "reports" / "report.html"
    html = html_path.read_text(encoding="utf-8")

    assert report_path == tmp_path / "reports" / "report.md"
    assert markdown.startswith("# 物理AI转折点")
    assert "## 问题" not in markdown
    assert "这个视频讲了什么？" not in markdown
    assert markdown.index("### 1. 第二个观点 [`04:10`](https://www.youtube.com/watch?v=xxxx&t=250s)") < markdown.index(
        "### 2. 第一个观点 [`00:10`](https://www.youtube.com/watch?v=xxxx&t=10s)"
    )
    assert "[`04:10`](https://www.youtube.com/watch?v=xxxx&t=250s)" in markdown
    assert "- **子论点二**：解释二 [`04:10`](https://www.youtube.com/watch?v=xxxx&t=250s)" not in markdown
    assert "- **子论点一**：解释一 [`00:10`](https://www.youtube.com/watch?v=xxxx&t=10s)" not in markdown
    assert "> “引用一” [`00:10`](https://www.youtube.com/watch?v=xxxx&t=10s)\n\n    > “引用二” [`00:50`](https://www.youtube.com/watch?v=xxxx&t=50s)" in markdown
    assert html_path.is_file()
    assert (tmp_path / "reports" / "cover.jpg").read_bytes() == b"fake jpg"
    assert '<img class="cover-image" src="cover.jpg" alt="物理AI转折点">' in html
    assert '<h2 class="source-heading">来源信息</h2>' in html
    assert "font-size: 12pt" in html
    assert '@font-face' in html
    assert 'font-family: "LXGW WenKai"' in html
    assert "LXGWWenKai-Regular.ttf" in html
    assert "@media print" in html


def test_render_markdown_report_skips_missing_cover(tmp_path: Path) -> None:
    _write_report_inputs(tmp_path)
    metadata_path = tmp_path / "elements" / "metadata.json"
    metadata = metadata_path.read_text(encoding="utf-8")
    metadata_path.write_text(metadata.replace(str(tmp_path / "elements" / "xxxx.jpg"), str(tmp_path / "missing.jpg")), encoding="utf-8")

    report_path = render_markdown_report(output_dir=tmp_path)
    html = report_path.with_suffix(".html").read_text(encoding="utf-8")

    assert report_path.with_suffix(".html").is_file()
    assert '<img class="cover-image"' not in html


def test_render_html_report_uses_lxgw_wenkai_font(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    report_dir.mkdir(parents=True)
    markdown_path = report_dir / "report.md"
    markdown_path.write_text("# 标题\n\n正文。\n", encoding="utf-8")

    html_path = render_html_report(output_dir=tmp_path, markdown_path=markdown_path)
    html = html_path.read_text(encoding="utf-8")

    assert '@font-face' in html
    assert 'font-family: "LXGW WenKai"' in html
    assert "LXGWWenKai-Regular.ttf" in html
    assert "@page" in html
    assert "@media print" in html


def test_render_pdf_report_requires_html_report(tmp_path: Path) -> None:
    with pytest.raises(ReportRenderError, match="reports/report.html is required"):
        render_pdf_report(output_dir=tmp_path)
