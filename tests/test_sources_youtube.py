import pytest

from podcast_agent.errors import InvalidSourceUrlError
from podcast_agent.sources.youtube import YoutubeSourceClient, extract_video_id
from podcast_agent.types import SourceRef


@pytest.mark.parametrize(
    ("url", "video_id"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=10s", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ],
)
def test_extract_video_id_supports_video_url_shapes(url: str, video_id: str) -> None:
    assert extract_video_id(url) == video_id


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch",
        "https://www.youtube.com/watch?v=",
        "https://youtu.be/",
        "https://www.youtube.com/playlist?list=abc",
    ],
)
def test_extract_video_id_rejects_invalid_youtube_urls(url: str) -> None:
    with pytest.raises(InvalidSourceUrlError):
        extract_video_id(url)


def test_youtube_source_client_returns_source_ref() -> None:
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    assert YoutubeSourceClient().resolve(url) == SourceRef(
        source_type="youtube",
        url=url,
        source_id="dQw4w9WgXcQ",
    )
