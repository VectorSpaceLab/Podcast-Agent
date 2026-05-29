from pathlib import Path

from podcast_agent.intent import ReportIntent
from podcast_agent.pipeline.artifacts import save_json
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
                {"id": "V1", "title": "第一个观点"},
                {"id": "V2", "title": "第二个观点"},
            ]
        },
    )
    save_json(
        output_dir / "insights" / "viewpoints.json",
        {
            "viewpoint_breakdown": [
                {"id": "V1", "title": "第一个观点"},
                {"id": "V2", "title": "第二个观点"},
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
        outline={"viewpoint_breakdown": [{"id": "V1", "title": "观点"}]},
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
            "introduction": "导读。",
            "core_conclusions": [{"title": "结论", "rationale": "理由。"}],
            "one_paragraph_takeaway": "收束。",
        },
    )

    assert markdown.index("## 导读") < markdown.index("## 核心结论")
    assert markdown.index("## 核心结论") < markdown.index("## 观点拆解")
    assert markdown.index("## 观点拆解") < markdown.index("## 总结")
    assert "- **子论点**：解释 [`00:05`](https://www.youtube.com/watch?v=xxxx&t=5s)" in markdown
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
    assert "- **Conclusion**: Reason." in markdown
    assert "- Author: Author" in markdown


def test_render_markdown_report_writes_report_file(tmp_path: Path) -> None:
    _write_report_inputs(tmp_path)

    report_path = render_markdown_report(output_dir=tmp_path)
    markdown = report_path.read_text(encoding="utf-8")
    html_path = tmp_path / "reports" / "report.html"
    html = html_path.read_text(encoding="utf-8")

    assert report_path == tmp_path / "reports" / "report.md"
    assert markdown.startswith("# Example Video")
    assert "## 问题" not in markdown
    assert "这个视频讲了什么？" not in markdown
    assert markdown.index("### 1. 第二个观点") < markdown.index("### 2. 第一个观点")
    assert "[`04:10`](https://www.youtube.com/watch?v=xxxx&t=250s)" in markdown
    assert "> “引用一” [`00:10`](https://www.youtube.com/watch?v=xxxx&t=10s)\n\n    > “引用二” [`00:50`](https://www.youtube.com/watch?v=xxxx&t=50s)" in markdown
    assert html_path.is_file()
    assert (tmp_path / "reports" / "cover.jpg").read_bytes() == b"fake jpg"
    assert '<img class="cover-image" src="cover.jpg" alt="Example Video">' in html
    assert '<h2 class="source-heading">来源信息</h2>' in html
    assert "font-size: 12pt" in html


def test_render_markdown_report_skips_missing_cover(tmp_path: Path) -> None:
    _write_report_inputs(tmp_path)
    metadata_path = tmp_path / "elements" / "metadata.json"
    metadata = metadata_path.read_text(encoding="utf-8")
    metadata_path.write_text(metadata.replace(str(tmp_path / "elements" / "xxxx.jpg"), str(tmp_path / "missing.jpg")), encoding="utf-8")

    report_path = render_markdown_report(output_dir=tmp_path)
    html = report_path.with_suffix(".html").read_text(encoding="utf-8")

    assert report_path.with_suffix(".html").is_file()
    assert '<img class="cover-image"' not in html
