import pytest

from podcast_agent.errors import UnsupportedSourceError
from podcast_agent.sources.detection import detect_source


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
    ],
)
def test_detect_source_recognizes_youtube_urls(url: str) -> None:
    assert detect_source(url) == "youtube"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.bilibili.com/video/BV1xx411c7mD",
        "https://bilibili.com/video/BV1xx411c7mD",
        "https://m.bilibili.com/video/BV1xx411c7mD",
        "https://b23.tv/abc123",
    ],
)
def test_detect_source_recognizes_bilibili_urls(url: str) -> None:
    assert detect_source(url) == "bilibili"


def test_detect_source_rejects_unknown_domains() -> None:
    with pytest.raises(UnsupportedSourceError):
        detect_source("https://example.com/video")
