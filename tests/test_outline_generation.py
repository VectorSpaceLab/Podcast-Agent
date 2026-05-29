from pathlib import Path

from podcast_agent.insights.outline import generate_outline
from podcast_agent.insights.outline_prompts import build_report_outline_v1_prompt, sanitize_outline_evidence
from podcast_agent.pipeline.artifacts import load_json, save_json


def _write_outline_inputs(output_dir: Path) -> None:
    save_json(output_dir / "input.json", {"url": "https://www.youtube.com/watch?v=xxxx", "question": "这个视频讲了什么？"})
    save_json(output_dir / "source.json", {"source_type": "youtube", "url": "https://www.youtube.com/watch?v=xxxx", "source_id": "xxxx"})
    save_json(
        output_dir / "elements" / "metadata.json",
        {
            "title": "Example Video",
            "description": "Example description",
            "chapters": [{"start": 0.0, "title": "Opening"}],
        },
    )
    save_json(
        output_dir / "insights" / "evidence.json",
        {
            "question": "这个视频讲了什么？",
            "subtitle_path": "elements/transcript.vtt",
            "segments": [
                {
                    "index": 1,
                    "start": "00:00:00.000",
                    "end": "00:00:03.000",
                    "text": "第一条证据。",
                    "subtitles": [{"start": "00:00:00.000", "end": "00:00:03.000", "text": "第一条证据。"}],
                },
                {
                    "index": 2,
                    "start": "00:00:03.000",
                    "end": "00:00:06.000",
                    "text": "第二条证据。",
                    "subtitles": [{"start": "00:00:03.000", "end": "00:00:06.000", "text": "第二条证据。"}],
                },
            ],
        },
    )


def test_sanitize_outline_evidence_removes_subtitles() -> None:
    sanitized = sanitize_outline_evidence(
        {
            "segments": [
                {
                    "index": 1,
                    "start": "00:00:00.000",
                    "end": "00:00:01.000",
                    "text": "hello",
                    "subtitles": [{"text": "hello"}],
                }
            ]
        }
    )

    assert sanitized == [{"index": 1, "start": "00:00:00.000", "end": "00:00:01.000", "text": "hello"}]


def test_build_report_outline_prompt_uses_videochat_shape() -> None:
    prompt = build_report_outline_v1_prompt(
        question="q",
        evidence={"segments": [{"index": 1, "start": "00:00:00.000", "end": "00:00:01.000", "text": "hello"}]},
        source_url="https://www.youtube.com/watch?v=xxxx",
        video_title="Example",
        video_description="Description",
        chapters=[{"start": 0.0, "title": "Opening"}],
    )

    assert "You are a senior feature editor planning an evidence-based report from video evidence." in prompt
    assert "Return the JSON outline now:" in prompt
    assert '"viewpoint_breakdown"' in prompt
    assert '"target_outline_viewpoints": "4-8"' in prompt


def test_generate_outline_writes_videochat_compatible_artifact(tmp_path: Path) -> None:
    _write_outline_inputs(tmp_path)

    def fake_model_writer(prompt: str) -> str:
        assert '"index": 1' in prompt
        assert "subtitles" not in prompt
        return """
        {
          "viewpoint_breakdown": [
            {
              "id": "V1",
              "title": "核心观点",
              "summary": "这是摘要。",
              "importance_score": 5,
              "importance_reason": "它很重要。",
              "evidence_segment_indexes": [1, 2]
            }
          ]
        }
        """

    outline = generate_outline(output_dir=tmp_path, model_writer=fake_model_writer)

    assert outline == load_json(tmp_path / "insights" / "outline.json")
    assert outline["viewpoint_breakdown"][0]["id"] == "V1"
    assert outline["viewpoint_breakdown"][0]["evidence_segment_indexes"] == [1, 2]


def test_generate_outline_writes_empty_outline_for_empty_evidence(tmp_path: Path) -> None:
    _write_outline_inputs(tmp_path)
    save_json(
        tmp_path / "insights" / "evidence.json",
        {"question": "q", "subtitle_path": "elements/transcript.vtt", "segments": []},
    )

    outline = generate_outline(output_dir=tmp_path, model_writer=lambda prompt: "{}")

    assert outline == {"viewpoint_breakdown": []}
    assert load_json(tmp_path / "insights" / "outline.json") == {"viewpoint_breakdown": []}
