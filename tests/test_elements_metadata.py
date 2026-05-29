import pytest

from podcast_agent.elements.metadata import normalize_chapters, normalize_metadata, parse_timestamp
from podcast_agent.errors import MetadataFetchError
from podcast_agent.types import Chapter, SourceRef, VideoMetadata
from tests.fakes import fake_metadata_info


SOURCE = SourceRef(
    source_type="youtube",
    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    source_id="dQw4w9WgXcQ",
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (12, 12.0),
        (12.5, 12.5),
        ("12.5", 12.5),
        ("00:01:02.500", 62.5),
        ("01:02:03", 3723.0),
        ("bad", None),
        (-1, None),
    ],
)
def test_parse_timestamp(value, expected) -> None:
    assert parse_timestamp(value) == expected


def test_normalize_chapters_sorts_and_deduplicates() -> None:
    chapters = normalize_chapters(fake_metadata_info()["chapters"])

    assert chapters == [
        Chapter(start=0.0, title="Opening"),
        Chapter(start=60.0, title="Middle"),
        Chapter(start=120.5, title="Ending"),
    ]


def test_normalize_metadata_returns_video_metadata() -> None:
    metadata = normalize_metadata(SOURCE, fake_metadata_info())

    assert metadata == VideoMetadata(
        source_type="youtube",
        source_id="dQw4w9WgXcQ",
        source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="Example Video",
        author="Example Channel",
        webpage_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        duration_seconds=212.0,
        description="Example description",
        publish_date="20091025",
        thumbnail_url="https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
        thumbnail_path="/tmp/output/elements/dQw4w9WgXcQ.jpg",
        chapters=[
            Chapter(start=0.0, title="Opening"),
            Chapter(start=60.0, title="Middle"),
            Chapter(start=120.5, title="Ending"),
        ],
    )


@pytest.mark.parametrize("missing_key", ["title", "uploader", "webpage_url"])
def test_normalize_metadata_rejects_missing_required_fields(missing_key: str) -> None:
    info = fake_metadata_info()
    info.pop(missing_key)
    if missing_key == "uploader":
        info.pop("channel", None)
    if missing_key == "webpage_url":
        info["original_url"] = ""

    with pytest.raises(MetadataFetchError):
        normalize_metadata(
            SourceRef(source_type="youtube", url="", source_id="dQw4w9WgXcQ"),
            info,
        )
