from pathlib import Path

from podcast_agent.api.adapters import find_report_path, find_subtitle_path, load_source_metadata, resolve_source_url


def test_api_adapters_find_current_artifacts(tmp_path: Path) -> None:
    report_path = tmp_path / "reports" / "report.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text("# Demo\n", encoding="utf-8")
    subtitle_path = tmp_path / "elements" / "transcript.vtt"
    subtitle_path.parent.mkdir(parents=True)
    subtitle_path.write_text("WEBVTT\n", encoding="utf-8")
    (tmp_path / "elements" / "metadata.json").write_text(
        '{"source_url": "https://example.com/video", "title": "Demo"}\n',
        encoding="utf-8",
    )

    assert find_report_path(tmp_path) == report_path
    assert find_subtitle_path(tmp_path) == subtitle_path
    assert load_source_metadata(tmp_path)["title"] == "Demo"
    assert resolve_source_url(tmp_path) == "https://example.com/video"


def test_api_adapters_support_old_videochat_paths(tmp_path: Path) -> None:
    report_path = tmp_path / "report" / "report.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text("# Demo\n", encoding="utf-8")
    subtitle_path = tmp_path / "input" / "demo.srt"
    subtitle_path.parent.mkdir(parents=True)
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")
    (tmp_path / "input" / "SOURCE_METADATA.json").write_text(
        '{"webpage_url": "https://example.com/old"}\n',
        encoding="utf-8",
    )

    assert find_report_path(tmp_path) == report_path
    assert find_subtitle_path(tmp_path) == subtitle_path
    assert resolve_source_url(tmp_path) == "https://example.com/old"

