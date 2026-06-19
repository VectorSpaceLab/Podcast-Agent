from pathlib import Path

from podcast_agent.api.followup import run_followup_for_task


def test_followup_returns_segments_and_sufficiency(tmp_path: Path) -> None:
    elements_dir = tmp_path / "elements"
    elements_dir.mkdir(parents=True)
    (elements_dir / "transcript.vtt").write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhello world\n\n00:00:01.000 --> 00:00:02.000\nmore detail\n",
        encoding="utf-8",
    )
    (elements_dir / "metadata.json").write_text('{"source_url": "https://example.com/video"}\n', encoding="utf-8")
    calls = []

    def fake_model_writer(prompt: str) -> str:
        calls.append(prompt)
        if "Return only a JSON object" in prompt:
            return '{"sufficient": true, "reason": "Enough evidence."}'
        return '{"segments": [{"start": "00:00:00.000", "end": "00:00:01.000"}]}'

    result = run_followup_for_task(task_dir=tmp_path, task_id="task-1", question="q", model_writer=fake_model_writer)

    assert result.segments == [{"start": "00:00:00,000", "end": "00:00:01,000", "text": "hello world"}]
    assert result.sufficient is True
    assert result.reason == "Enough evidence."
    followup_dirs = list((tmp_path / "follow_up").iterdir())
    assert len(followup_dirs) == 1
    assert (followup_dirs[0] / "question.json").is_file()
    assert (followup_dirs[0] / "segments.json").is_file()
    assert (followup_dirs[0] / "sufficiency.json").is_file()
    assert (followup_dirs[0] / "llm.json").is_file()
    assert not (followup_dirs[0] / "answer.md").exists()


def test_followup_missing_subtitle_raises_file_not_found(tmp_path: Path) -> None:
    try:
        run_followup_for_task(task_dir=tmp_path, task_id="task-1", question="q", model_writer=lambda _prompt: "{}")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected FileNotFoundError")
