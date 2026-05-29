from pathlib import Path

from podcast_agent.elements.youtube_metadata import YoutubeMetadataFetcher
from podcast_agent.types import SourceRef
from tests.fakes import FakeMetadataDownloader


def test_youtube_metadata_fetcher_uses_downloader(tmp_path: Path) -> None:
    downloader = FakeMetadataDownloader()
    source = SourceRef(
        source_type="youtube",
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        source_id="dQw4w9WgXcQ",
    )

    metadata = YoutubeMetadataFetcher(
        output_dir=tmp_path,
        downloader=downloader,
    ).fetch(source)

    assert metadata.title == "Example Video"
    assert metadata.chapters[0].title == "Opening"
    assert downloader.calls == [(source.url, tmp_path)]
