from pathlib import Path

from podcast_agent.pipeline.artifacts import load_json
from podcast_agent.pipeline.runner import run_pipeline
from tests.fakes import FakeMetadataDownloader, FakeTranscriptDownloader


def test_run_pipeline_saves_source_json(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo"

    context = run_pipeline(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        question="这个视频讲了什么？",
        output_dir=output_dir,
        metadata_downloader=FakeMetadataDownloader(),
        transcript_downloader=FakeTranscriptDownloader(),
    )

    assert context.source_path.is_file()
    assert load_json(context.source_path) == {
        "source_type": "youtube",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "source_id": "dQw4w9WgXcQ",
    }
