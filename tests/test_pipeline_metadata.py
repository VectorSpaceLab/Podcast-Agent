from pathlib import Path

from podcast_agent.pipeline.artifacts import load_json
from podcast_agent.pipeline.runner import run_pipeline
from tests.fakes import FakeMetadataDownloader, FakeTranscriptDownloader


def test_run_pipeline_saves_metadata_json(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo"

    context = run_pipeline(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        question="这个视频讲了什么？",
        output_dir=output_dir,
        metadata_downloader=FakeMetadataDownloader(),
        transcript_downloader=FakeTranscriptDownloader(),
    )

    assert (context.elements_dir / "metadata.json").is_file()
    assert (context.elements_dir / "transcript.vtt").is_file()
    assert (context.elements_dir / "transcript.txt").is_file()
    assert (context.elements_dir / "transcript_info.json").is_file()
    assert load_json(context.elements_dir / "metadata.json") == {
        "source_type": "youtube",
        "source_id": "dQw4w9WgXcQ",
        "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "Example Video",
        "author": "Example Channel",
        "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "duration_seconds": 212.0,
        "description": "Example description",
        "publish_date": "20091025",
        "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
        "thumbnail_path": "/tmp/output/elements/dQw4w9WgXcQ.jpg",
        "chapters": [
            {"start": 0.0, "title": "Opening"},
            {"start": 60.0, "title": "Middle"},
            {"start": 120.5, "title": "Ending"},
        ],
    }
