from pathlib import Path

from podcast_agent.insights.viewpoint import (
    build_viewpoints_payload,
    generate_viewpoint_detail,
    generate_viewpoints,
    select_viewpoints_for_detail,
)
from podcast_agent.errors import EvidenceExtractionError
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
    assert "The quote text field is reader-facing and MUST always be written in the target report language." in prompt
    assert "When source_text is not in the target report language, translate it faithfully into the target report language in text." in prompt
    assert "Never copy non-target-language subtitle text into text" in prompt
    assert "source_text MUST preserve the verbatim original subtitle evidence and MUST NOT be translated" in prompt
    assert "If source_text is in English and the target report language is Chinese, text MUST be Chinese." in prompt
    assert "If source_text is in Chinese and the target report language is English, text MUST be English." in prompt
    assert "<faithful reader-facing translation/rendering in the target report language, never non-target-language source wording>" in prompt
    assert "<verbatim original subtitle text used as evidence, unchanged and untranslated>" in prompt


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


def test_generate_viewpoint_detail_retries_empty_response() -> None:
    outline = {
        "viewpoint_breakdown": [
            {"id": "V1", "title": "观点", "summary": "摘要", "evidence_segment_indexes": [1]}
        ]
    }
    evidence = {
        "segments": [
            {
                "index": 1,
                "start": "00:00:00.000",
                "end": "00:00:01.000",
                "subtitles": [{"start": "00:00:00.000", "end": "00:00:01.000", "text": "hello"}],
            }
        ]
    }
    calls = []

    def fake_model_writer(prompt: str) -> str:
        calls.append(prompt)
        if len(calls) == 1:
            return ""
        assert "The previous response was invalid." in prompt
        assert "Reason: empty_response." in prompt
        return '{"sub_theses": []}'

    detail = generate_viewpoint_detail(
        question="q",
        outline=outline,
        evidence=evidence,
        viewpoint_id="V1",
        source_url=None,
        video_title="",
        video_description="",
        model_writer=fake_model_writer,
    )

    assert len(calls) == 2
    assert detail["viewpoint_id"] == "V1"
    assert detail["sub_theses"] == []


def test_generate_viewpoint_detail_retries_invalid_json() -> None:
    outline = {
        "viewpoint_breakdown": [
            {"id": "V1", "title": "观点", "summary": "摘要", "evidence_segment_indexes": [1]}
        ]
    }
    evidence = {
        "segments": [
            {
                "index": 1,
                "start": "00:00:00.000",
                "end": "00:00:01.000",
                "subtitles": [{"start": "00:00:00.000", "end": "00:00:01.000", "text": "hello"}],
            }
        ]
    }
    calls = []

    def fake_model_writer(prompt: str) -> str:
        calls.append(prompt)
        if len(calls) == 1:
            return "not json"
        assert "Reason: invalid_json." in prompt
        return '{"sub_theses": []}'

    detail = generate_viewpoint_detail(
        question="q",
        outline=outline,
        evidence=evidence,
        viewpoint_id="V1",
        source_url=None,
        video_title="",
        video_description="",
        model_writer=fake_model_writer,
    )

    assert len(calls) == 2
    assert detail["viewpoint_id"] == "V1"


def test_generate_viewpoint_detail_raises_after_retry_exhaustion() -> None:
    outline = {
        "viewpoint_breakdown": [
            {"id": "V1", "title": "观点", "summary": "摘要", "evidence_segment_indexes": [1]}
        ]
    }
    evidence = {
        "segments": [
            {
                "index": 1,
                "start": "00:00:00.000",
                "end": "00:00:01.000",
                "subtitles": [{"start": "00:00:00.000", "end": "00:00:01.000", "text": "hello"}],
            }
        ]
    }
    calls = []

    def fake_model_writer(prompt: str) -> str:
        calls.append(prompt)
        return ""

    try:
        generate_viewpoint_detail(
            question="q",
            outline=outline,
            evidence=evidence,
            viewpoint_id="V1",
            source_url=None,
            video_title="",
            video_description="",
            model_writer=fake_model_writer,
        )
    except EvidenceExtractionError as exc:
        assert "after 3 attempts" in str(exc)
        assert "empty_response" in str(exc)
    else:
        raise AssertionError("expected EvidenceExtractionError")

    assert len(calls) == 3


def test_build_viewpoints_payload_records_omitted_ids() -> None:
    payload = build_viewpoints_payload(
        outline={"viewpoint_breakdown": [{"id": "V1"}, {"id": "V2"}]},
        details=[{"viewpoint_id": "V2"}],
    )

    assert payload["selected_viewpoint_ids"] == ["V2"]
    assert payload["omitted_viewpoint_ids"] == ["V1"]
