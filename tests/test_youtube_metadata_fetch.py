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


def test_bilibili_metadata_fetcher_uses_configured_downloader(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeBilibiliDownloader(FakeMetadataDownloader):
        def __init__(self, *, cookies_file=None, cookies_from_browser=None, user_agent=None):
            super().__init__()
            captured["cookies_file"] = cookies_file
            captured["cookies_from_browser"] = cookies_from_browser
            captured["user_agent"] = user_agent

    monkeypatch.setattr(
        "podcast_agent.elements.youtube_metadata.BilibiliYtDlpDownloader",
        FakeBilibiliDownloader,
    )
    monkeypatch.setattr("podcast_agent.elements.youtube_metadata.BILIBILI_COOKIES_FILE", "/tmp/env-bili.txt")
    monkeypatch.setattr("podcast_agent.elements.youtube_metadata.BILIBILI_COOKIES_FROM_BROWSER", "chrome")
    monkeypatch.setattr("podcast_agent.elements.youtube_metadata.BILIBILI_USER_AGENT", "Custom UA")

    source = SourceRef(
        source_type="bilibili",
        url="https://www.bilibili.com/video/BV1xx411c7mD",
        source_id="BV1xx411c7mD",
    )

    YoutubeMetadataFetcher(output_dir=tmp_path).fetch(source)

    assert captured["cookies_file"] == "/tmp/env-bili.txt"
    assert captured["cookies_from_browser"] == "chrome"
    assert captured["user_agent"] == "Custom UA"
