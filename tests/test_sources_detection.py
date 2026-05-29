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


def test_detect_source_rejects_unknown_domains() -> None:
    with pytest.raises(UnsupportedSourceError):
        detect_source("https://example.com/video")
