import pytest

from podcast_agent.errors import UnsupportedSourceError
from podcast_agent.sources.registry import get_source_client, resolve_source


def test_get_source_client_returns_youtube_client() -> None:
    client = get_source_client("youtube")

    assert client.source_type == "youtube"


def test_get_source_client_returns_bilibili_client() -> None:
    client = get_source_client("bilibili")

    assert client.source_type == "bilibili"


def test_get_source_client_rejects_unknown_source_type() -> None:
    with pytest.raises(UnsupportedSourceError):
        get_source_client("unknown")


def test_resolve_source_returns_source_ref() -> None:
    source_ref = resolve_source("https://youtu.be/dQw4w9WgXcQ")

    assert source_ref.source_type == "youtube"
    assert source_ref.source_id == "dQw4w9WgXcQ"


def test_resolve_source_returns_bilibili_source_ref() -> None:
    source_ref = resolve_source("https://www.bilibili.com/video/BV1xx411c7mD")

    assert source_ref.source_type == "bilibili"
    assert source_ref.source_id == "BV1xx411c7mD"
