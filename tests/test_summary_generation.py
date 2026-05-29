from pathlib import Path

from podcast_agent.insights.summary import build_summary_viewpoints_payload, empty_summary, generate_summary
from podcast_agent.insights.summary_prompts import build_report_summary_v1_prompt, sanitize_summary_viewpoints
from podcast_agent.pipeline.artifacts import load_json, save_json


def _write_summary_inputs(output_dir: Path) -> None:
    save_json(output_dir / "input.json", {"url": "https://www.youtube.com/watch?v=xxxx", "question": "这个视频讲了什么？"})
    save_json(output_dir / "source.json", {"source_type": "youtube", "url": "https://www.youtube.com/watch?v=xxxx", "source_id": "xxxx"})
    save_json(output_dir / "elements" / "metadata.json", {"chapters": [{"start": 0.0, "title": "Opening"}]})
    save_json(
        output_dir / "insights" / "viewpoints.json",
        {
            "report_type": "viewpoints",
            "viewpoint_breakdown": [
                {"id": "V1", "title": "观点一", "summary": "摘要一", "importance_score": 5, "importance_reason": "重要"},
                {"id": "V2", "title": "观点二", "summary": "摘要二", "importance_score": 4, "importance_reason": "也重要"},
            ],
            "viewpoint_details": [
                {
                    "viewpoint_id": "V1",
                    "sub_theses": [
                        {
                            "title": "子论点一",
                            "explanation": "解释一",
                            "quotes": [{"source_text": "不要进 summary"}],
                        }
                    ],
                },
                {
                    "viewpoint_id": "V2",
                    "sub_theses": [{"title": "子论点二", "explanation": "解释二"}],
                },
            ],
        },
    )


def test_build_summary_viewpoints_payload_removes_quotes() -> None:
    payload = {
        "viewpoint_breakdown": [{"id": "V1", "title": "观点", "summary": "摘要", "importance_score": 5, "importance_reason": "重要"}],
        "viewpoint_details": [{"viewpoint_id": "V1", "sub_theses": [{"title": "子论点", "explanation": "解释", "quotes": [{"source_text": "x"}]}]}],
    }

    condensed = build_summary_viewpoints_payload(payload)

    assert condensed == {
        "viewpoints": [
            {
                "id": "V1",
                "title": "观点",
                "summary": "摘要",
                "importance_score": 5,
                "importance_reason": "重要",
                "sub_theses": [{"title": "子论点", "explanation": "解释"}],
            }
        ]
    }


def test_sanitize_summary_viewpoints_removes_empty_sub_theses() -> None:
    sanitized = sanitize_summary_viewpoints({"viewpoints": [{"id": "V1", "sub_theses": [{"title": ""}, {"title": "t"}]}]})

    assert sanitized["viewpoints"][0]["sub_theses"] == [{"title": "t"}]


def test_build_report_summary_prompt_uses_videochat_shape() -> None:
    prompt = build_report_summary_v1_prompt(
        question="q",
        viewpoints={"viewpoints": [{"id": "V1", "title": "观点", "sub_theses": [{"title": "子论点"}]}]},
        source_url="https://www.youtube.com/watch?v=xxxx",
        chapters=[{"start": 0.0, "title": "Opening"}],
    )

    assert "You are a senior feature editor synthesizing an evidence-based report from completed viewpoint details." in prompt
    assert "Return the summary JSON now:" in prompt
    assert '"core_conclusions"' in prompt
    assert '"target_core_conclusions": "3-5"' in prompt


def test_generate_summary_writes_summary(tmp_path: Path) -> None:
    _write_summary_inputs(tmp_path)

    def fake_model_writer(prompt: str) -> str:
        assert "Condensed Viewpoints" in prompt
        assert "source_text" not in prompt
        return """
        {
          "report_type": "summary",
          "language": "zh-Hans",
          "introduction": "导语。",
          "core_conclusions": [
            {
              "id": "C1",
              "title": "结论",
              "rationale": "理由。",
              "source_viewpoint_ids": ["V1"],
              "synthesis_type": "single_viewpoint"
            }
          ],
          "viewpoint_order": ["V1", "V2"],
          "one_paragraph_takeaway": "收束。"
        }
        """

    summary = generate_summary(output_dir=tmp_path, model_writer=fake_model_writer)

    assert summary == load_json(tmp_path / "insights" / "summary.json")
    assert summary["core_conclusions"][0]["id"] == "C1"
    assert summary["viewpoint_order"] == ["V1", "V2"]


def test_generate_summary_writes_empty_summary_without_details(tmp_path: Path) -> None:
    _write_summary_inputs(tmp_path)
    save_json(tmp_path / "insights" / "viewpoints.json", {"viewpoint_breakdown": [], "viewpoint_details": []})

    summary = generate_summary(output_dir=tmp_path, model_writer=lambda prompt: "{}")

    assert summary == empty_summary("zh-Hans")
    assert load_json(tmp_path / "insights" / "summary.json") == empty_summary("zh-Hans")
