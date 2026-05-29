from pathlib import Path

from podcast_agent.insights.viewpoint import (
    build_viewpoints_payload,
    generate_viewpoints,
    select_viewpoints_for_detail,
)
from podcast_agent.insights.viewpoint_prompts import build_viewpoint_detail_v1_prompt, select_segments_for_viewpoint
from podcast_agent.pipeline.artifacts import load_json, save_json


def _write_viewpoint_inputs(output_dir: Path) -> None:
    save_json(output_dir / "input.json", {"url": "https://www.youtube.com/watch?v=xxxx", "question": "这个视频讲了什么？"})
    save_json(output_dir / "source.json", {"source_type": "youtube", "url": "https://www.youtube.com/watch?v=xxxx", "source_id": "xxxx"})
    save_json(output_dir / "elements" / "metadata.json", {"title": "Example", "description": "Description"})
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
    save_json(
        output_dir / "insights" / "outline.json",
        {
            "viewpoint_breakdown": [
                {
                    "id": "V1",
                    "title": "第一观点",
                    "summary": "第一摘要。",
                    "importance_score": 4,
                    "importance_reason": "重要。",
                    "evidence_segment_indexes": [1],
                },
                {
                    "id": "V2",
                    "title": "第二观点",
                    "summary": "第二摘要。",
                    "importance_score": 5,
                    "importance_reason": "更重要。",
                    "evidence_segment_indexes": [2],
                },
            ]
        },
    )


def test_select_viewpoints_for_detail_sorts_by_score_then_returns_outline_order() -> None:
    outline = {
        "viewpoint_breakdown": [
            {"id": "V1", "importance_score": 4},
            {"id": "V2", "importance_score": 5},
            {"id": "V3", "importance_score": 3},
        ]
    }

    selected = select_viewpoints_for_detail(outline, limit=2)

    assert [item["id"] for item in selected] == ["V1", "V2"]


def test_select_segments_for_viewpoint_uses_evidence_indexes() -> None:
    evidence = {
        "segments": [
            {"index": 1, "start": "s1", "end": "e1", "subtitles": [{"start": "s1", "end": "e1", "text": "a"}]},
            {"index": 2, "start": "s2", "end": "e2", "subtitles": [{"start": "s2", "end": "e2", "text": "b"}]},
        ]
    }

    selected = select_segments_for_viewpoint(evidence=evidence, viewpoint={"evidence_segment_indexes": [2]})

    assert selected == [{"segment_start": "s2", "segment_end": "e2", "subtitle_lines": ["s2 --> e2 b"]}]


def test_build_viewpoint_detail_prompt_uses_videochat_shape() -> None:
    _write_viewpoint_inputs(Path("/tmp/nonexistent-viewpoint-fixture"))
    outline = {
        "viewpoint_breakdown": [
            {"id": "V1", "title": "观点", "summary": "摘要", "importance_score": 5, "evidence_segment_indexes": [1]}
        ]
    }
    evidence = {
        "segments": [
            {"index": 1, "start": "00:00:00.000", "end": "00:00:01.000", "subtitles": [{"start": "00:00:00.000", "end": "00:00:01.000", "text": "hello"}]}
        ]
    }

    prompt = build_viewpoint_detail_v1_prompt(question="q", outline=outline, evidence=evidence, viewpoint_id="V1")

    assert "You are a senior feature editor writing an evidence-based report from a video podcast." in prompt
    assert "Return the viewpoint detail JSON now:" in prompt
    assert '"sub_theses"' in prompt
    assert "00:00:00.000 --> 00:00:01.000 hello" in prompt


def test_generate_viewpoints_writes_details_and_payload(tmp_path: Path) -> None:
    _write_viewpoint_inputs(tmp_path)

    def fake_model_writer(prompt: str) -> str:
        assert "Selected Viewpoint From Outline" in prompt
        if '"id": "V1"' in prompt:
            viewpoint_id = "V1"
            segment_start = "00:00:00.000"
            source_text = "第一条证据。"
        else:
            viewpoint_id = "V2"
            segment_start = "00:00:03.000"
            source_text = "第二条证据。"
        return f"""
        {{
          "sub_theses": [
            {{
              "id": "{viewpoint_id}-S1",
              "title": "子论点",
              "explanation": "解释。",
              "segment_start": "{segment_start}",
              "supporting_evidence_segment_indexes": [1],
              "quotes": [
                {{
                  "text": "{source_text}",
                  "source_text": "{source_text}",
                  "subtitle_start": "{segment_start}",
                  "subtitle_end": "{segment_start}"
                }}
              ]
            }}
          ]
        }}
        """

    payload = generate_viewpoints(output_dir=tmp_path, model_writer=fake_model_writer)

    assert payload == load_json(tmp_path / "insights" / "viewpoints.json")
    assert payload["report_type"] == "viewpoints"
    assert payload["selected_viewpoint_ids"] == ["V1", "V2"]
    assert payload["omitted_viewpoint_ids"] == []
    assert (tmp_path / "insights" / "viewpoint_V1.json").is_file()
    assert (tmp_path / "insights" / "viewpoint_V2.json").is_file()
    assert payload["viewpoint_details"][0]["viewpoint_title"] == "第一观点"


def test_build_viewpoints_payload_records_omitted_ids() -> None:
    payload = build_viewpoints_payload(
        outline={"viewpoint_breakdown": [{"id": "V1"}, {"id": "V2"}]},
        details=[{"viewpoint_id": "V2"}],
    )

    assert payload["selected_viewpoint_ids"] == ["V2"]
    assert payload["omitted_viewpoint_ids"] == ["V1"]
