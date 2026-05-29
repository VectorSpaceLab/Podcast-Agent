from pathlib import Path

from podcast_agent.insights.evidence import (
    EvidenceConfig,
    chunk_subtitle_segments,
    extract_evidence,
    parse_subtitle_segments,
)
from podcast_agent.pipeline.artifacts import load_json, save_json


def _write_evidence_inputs(output_dir: Path) -> None:
    save_json(output_dir / "input.json", {"url": "https://www.youtube.com/watch?v=xxxx", "question": "这个视频讲了什么？"})
    save_json(
        output_dir / "elements" / "metadata.json",
        {
            "title": "Example",
            "chapters": [
                {"start": 0.0, "title": "Opening"},
            ],
        },
    )
    (output_dir / "elements").mkdir(parents=True, exist_ok=True)
    (output_dir / "elements" / "transcript.vtt").write_text(
        "\n".join(
            [
                "WEBVTT",
                "",
                "00:00:00.000 --> 00:00:03.000",
                "第一句介绍主题。",
                "",
                "00:00:03.000 --> 00:00:06.000",
                "第二句解释原因。",
                "",
                "00:00:06.000 --> 00:00:09.000",
                "第三句是无关内容。",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_parse_subtitle_segments_reads_vtt() -> None:
    segments = parse_subtitle_segments(
        "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhello\n\n00:00:01.000 --> 00:00:02.000\nworld\n"
    )

    assert segments == [
        {"index": 1, "start": "00:00:00.000", "end": "00:00:01.000", "text": "hello"},
        {"index": 2, "start": "00:00:01.000", "end": "00:00:02.000", "text": "world"},
    ]


def test_chunk_subtitle_segments_uses_overlap() -> None:
    segments = [
        {"index": 1, "start": "00:00:00.000", "end": "00:00:04.000", "text": "a"},
        {"index": 2, "start": "00:00:04.000", "end": "00:00:08.000", "text": "b"},
        {"index": 3, "start": "00:00:08.000", "end": "00:00:12.000", "text": "c"},
    ]

    chunks = chunk_subtitle_segments(segments, chunk_duration_seconds=6, chunk_overlap_seconds=2)

    assert len(chunks) == 3
    assert chunks[0]["segments"][0]["text"] == "a"
    assert chunks[1]["segments"][0]["text"] == "b"


def test_extract_evidence_writes_videochat_compatible_artifact(tmp_path: Path) -> None:
    _write_evidence_inputs(tmp_path)

    def fake_model_writer(prompt: str) -> str:
        assert "You are an evidence extraction editor" in prompt
        return '{"segments": [{"start": "00:00:00.000", "end": "00:00:06.000"}]}'

    evidence = extract_evidence(
        output_dir=tmp_path,
        model_writer=fake_model_writer,
        config=EvidenceConfig(max_final_segments=8),
    )

    assert evidence == load_json(tmp_path / "insights" / "evidence.json")
    assert evidence["question"] == "这个视频讲了什么？"
    assert evidence["subtitle_path"] == "elements/transcript.vtt"
    assert evidence["segments"] == [
        {
            "index": 1,
            "start": "00:00:00.000",
            "end": "00:00:06.000",
            "text": "第一句介绍主题。 第二句解释原因。",
            "subtitles": [
                {"start": "00:00:00.000", "end": "00:00:03.000", "text": "第一句介绍主题。"},
                {"start": "00:00:03.000", "end": "00:00:06.000", "text": "第二句解释原因。"},
            ],
        }
    ]


def test_extract_evidence_writes_empty_artifact_when_no_segments(tmp_path: Path) -> None:
    _write_evidence_inputs(tmp_path)

    evidence = extract_evidence(
        output_dir=tmp_path,
        model_writer=lambda prompt: '{"segments": []}',
    )

    assert evidence["segments"] == []
    assert evidence["coverage_notes"] == "No relevant evidence segments were found for the question."
