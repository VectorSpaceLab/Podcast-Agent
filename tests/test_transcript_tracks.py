from podcast_agent.elements.transcript_tracks import (
    TranscriptLanguagePreference,
    rank_transcript_tracks,
    transcript_tracks_from_info,
)
from podcast_agent.types import TranscriptTrack


def test_transcript_tracks_from_info_reads_manual_and_automatic() -> None:
    tracks = transcript_tracks_from_info(
        {
            "subtitles": {"en": [{"ext": "vtt"}]},
            "automatic_captions": {"zh": [{"ext": "vtt"}]},
        }
    )

    assert tracks == [
        TranscriptTrack(id="en", language="en", status="serving", track_kind="manual"),
        TranscriptTrack(id="zh", language="zh", status="serving", track_kind="automatic"),
    ]


def test_rank_transcript_tracks_prefers_matching_manual() -> None:
    tracks = [
        TranscriptTrack(id="zh", language="zh", track_kind="automatic"),
        TranscriptTrack(id="en", language="en", track_kind="manual"),
        TranscriptTrack(id="zh-Hans", language="zh-Hans", track_kind="manual"),
    ]

    ranked = rank_transcript_tracks(
        tracks,
        TranscriptLanguagePreference(preferred_languages=("zh",)),
    )

    assert ranked[0].id == "zh-Hans"
    assert ranked[1].id == "zh"


def test_rank_transcript_tracks_prefers_manual_without_language_match() -> None:
    tracks = [
        TranscriptTrack(id="zh", language="zh", track_kind="automatic"),
        TranscriptTrack(id="en", language="en", track_kind="manual"),
    ]

    ranked = rank_transcript_tracks(
        tracks,
        TranscriptLanguagePreference(preferred_languages=()),
    )

    assert ranked[0].id == "en"
