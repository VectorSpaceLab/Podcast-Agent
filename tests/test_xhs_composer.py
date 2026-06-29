import json
from pathlib import Path

import pytest

from podcast_agent.errors import XhsReportError
from podcast_agent.pipeline.artifacts import load_json, save_json
from podcast_agent.reports.xhs.composer import compose_xhs_report, render_xhs_note_markdown


def _write_xhs_inputs(output_dir: Path) -> None:
    save_json(
        output_dir / "elements" / "metadata.json",
        {
            "title": "Example Podcast",
            "author": "Example Host",
            "webpage_url": "https://www.youtube.com/watch?v=xxxx",
            "duration_seconds": 5172,
            "description": "A long conversation about AI.",
        },
    )
    save_json(
        output_dir / "insights" / "viewpoints.json",
        {
            "viewpoint_breakdown": [{"id": "V1", "title": "物理 AI", "summary": "从软件走向实体。"}],
            "viewpoint_details": [
                {
                    "viewpoint_id": "V1",
                    "sub_theses": [
                        {
                            "title": "数据闭环",
                            "explanation": "真实世界反馈会重塑产品。",
                            "quotes": [{"text": "真正难的是闭环。", "subtitle_start": "00:12:34.000"}],
                        }
                    ],
                }
            ],
        },
    )


def _model_response() -> str:
    return """
    {
      "post_title": "物理AI关键一战超过二十字会被截断",
      "post_description": "这期播客信息量很大，适合关心 AI 落地的人。",
      "tags": ["AI", "科技", "商业", "创业", "播客"],
      "cover_intro": "这期真正值得看的是：AI 正在从屏幕走向现实世界。",
      "article_title": "物理 AI 为什么重要",
      "sections": [
        {
          "heading": "AI 的战场变了",
          "paragraphs": ["过去比的是模型能力，现在更重要的是现实反馈。", "谁能更快闭环，谁就更接近产品化。"],
          "quotes": ["真正难的是闭环。"]
        }
      ],
      "closing": "这不是一个概念热词，而是一轮产业能力重排。"
    }
    """


def test_compose_xhs_report_writes_note_and_post_meta(tmp_path: Path) -> None:
    _write_xhs_inputs(tmp_path)

    captured_prompt: dict[str, str] = {}

    def fake_writer(prompt: str) -> str:
        captured_prompt["value"] = prompt
        return _model_response()

    result = compose_xhs_report(output_dir=tmp_path, model_writer=fake_writer)
    note = result.note_path.read_text(encoding="utf-8")
    post_meta = load_json(result.post_meta_path)

    assert result.note_path == tmp_path / "reports" / "xhs" / "note.md"
    assert result.post_meta_path == tmp_path / "reports" / "xhs" / "post_meta.json"
    assert len(post_meta["title"]) <= 20
    assert post_meta["source_url"] == "https://www.youtube.com/watch?v=xxxx"
    assert post_meta["tags"] == ["AI", "科技", "商业", "创业", "播客"]
    assert note.startswith("---\n")
    assert 'author: "Example Host"' in note
    assert 'source_title: "Example Podcast"' in note
    assert 'url: "https://www.youtube.com/watch?v=xxxx"' in note
    assert 'source: "Example Host / Example Podcast"' in note
    assert 'intro_image: "./cover.png"' in note
    assert "\n---\n\n## 1. AI 的战场变了" in note
    assert "> 真正难的是闭环。" in note
    assert "## 结尾" not in note
    assert "这不是一个概念热词，而是一轮产业能力重排。" in note

    input_payload = json.loads(captured_prompt["value"].split("输入材料：", 1)[1].strip())
    assert set(input_payload) == {"metadata", "viewpoints", "viewpoint_count", "angle"}
    assert "summary" not in input_payload
    assert "viewpoint_breakdown" in input_payload["viewpoints"]
    assert "viewpoint_details" in input_payload["viewpoints"]
    assert input_payload["viewpoint_count"] == len(input_payload["viewpoints"]["viewpoint_breakdown"])


def test_compose_xhs_report_fails_for_missing_required_artifacts(tmp_path: Path) -> None:
    with pytest.raises(XhsReportError, match="elements/metadata.json is required"):
        compose_xhs_report(output_dir=tmp_path, model_writer=lambda _prompt: "{}")


def test_compose_xhs_report_does_not_require_summary_json(tmp_path: Path) -> None:
    save_json(
        tmp_path / "elements" / "metadata.json",
        {
            "title": "Example Podcast",
            "author": "Example Host",
            "webpage_url": "https://www.youtube.com/watch?v=xxxx",
        },
    )
    save_json(
        tmp_path / "insights" / "viewpoints.json",
        {
            "viewpoint_breakdown": [{"id": "V1", "title": "物理 AI", "summary": "从软件走向实体。"}],
            "viewpoint_details": [],
        },
    )

    result = compose_xhs_report(output_dir=tmp_path, model_writer=lambda _prompt: _model_response())

    assert result.note_path.is_file()
    assert result.post_meta_path.is_file()


def test_render_xhs_note_markdown_escapes_frontmatter_quotes() -> None:
    markdown = render_xhs_note_markdown(
        composition={
            "post_title": "标题",
            "post_description": "描述",
            "tags": ["AI"],
            "cover_intro": "导语",
            "article_title": '他说"物理AI"',
            "sections": [{"heading": "观点", "paragraphs": ["正文"], "quotes": []}],
            "closing": "",
        },
        metadata={"title": 'Source "Title"', "author": "Host", "webpage_url": "https://example.com"},
    )

    assert 'title: "他说\\"物理AI\\""' in markdown
    assert 'author: "Host"' in markdown
    assert 'source_title: "Source \\"Title\\""' in markdown
    assert 'url: "https://example.com"' in markdown
    assert 'source: "Host / Source \\"Title\\""' in markdown


def test_render_xhs_note_markdown_strips_existing_section_numbers() -> None:
    markdown = render_xhs_note_markdown(
        composition={
            "article_title": "标题",
            "cover_intro": "导语",
            "sections": [
                {
                    "heading": "1. GPT-4 的缺陷，把 OpenAI 逼向了强化学习",
                    "paragraphs": ["正文"],
                    "quotes": [],
                }
            ],
            "post_title": "标题",
            "post_description": "描述",
            "tags": ["AI"],
        },
        metadata={"author": "Host", "title": "Source Title", "source_url": "https://example.com"},
    )

    assert "## 1. GPT-4 的缺陷，把 OpenAI 逼向了强化学习" in markdown
    assert "## 1. 1. GPT-4" not in markdown
