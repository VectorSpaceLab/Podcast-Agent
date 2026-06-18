import pytest

from podcast_agent.errors import InvalidSourceUrlError
from podcast_agent.sources.bilibili import BilibiliSourceClient, extract_bilibili_id
from podcast_agent.types import SourceRef


@pytest.mark.parametrize(
    ("url", "source_id"),
    [
        ("https://www.bilibili.com/video/BV1xx411c7mD", "BV1xx411c7mD"),
        ("https://m.bilibili.com/video/BV1xx411c7mD?p=2", "BV1xx411c7mD"),
        ("https://b23.tv/abc123", "abc123"),
    ],
)
def test_extract_bilibili_id_supports_url_shapes(url: str, source_id: str) -> None:
    assert extract_bilibili_id(url) == source_id


@pytest.mark.parametrize(
    "url",
    [
        "https://www.bilibili.com/video/",
        "https://www.bilibili.com/",
        "https://example.com/video/BV1xx411c7mD",
        "https://b23.tv/",
    ],
)
def test_extract_bilibili_id_rejects_invalid_urls(url: str) -> None:
    with pytest.raises(InvalidSourceUrlError):
        extract_bilibili_id(url)


def test_bilibili_source_client_returns_source_ref() -> None:
    url = "https://www.bilibili.com/video/BV1xx411c7mD"

    assert BilibiliSourceClient().resolve(url) == SourceRef(
        source_type="bilibili",
        url=url,
        source_id="BV1xx411c7mD",
    )
