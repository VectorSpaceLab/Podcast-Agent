from podcast_agent.elements.transcript_tracks import (
    TranscriptLanguagePreference,
    rank_transcript_tracks,
    transcript_download_candidates,
    transcript_tracks_from_info,
    transcript_tracks_from_info_for_source,
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


def test_bilibili_transcript_tracks_filter_danmaku_xml() -> None:
    tracks = transcript_tracks_from_info_for_source(
        {
            "subtitles": {
                "danmaku": [{"ext": "xml"}],
                "zh-Hans": [{"ext": "json"}],
            },
            "automatic_captions": {
                "ai-zh": [{"ext": "json"}],
            },
        },
        source_type="bilibili",
    )

    assert [track.id for track in tracks] == ["zh-Hans", "ai-zh"]


def test_rank_transcript_tracks_treats_bilibili_ai_language_as_natural_language() -> None:
    tracks = [
        TranscriptTrack(id="ai-ar", language="ai-ar", track_kind="automatic"),
        TranscriptTrack(id="ai-en", language="ai-en", track_kind="automatic"),
        TranscriptTrack(id="ai-ja", language="ai-ja", track_kind="automatic"),
        TranscriptTrack(id="ai-zh", language="ai-zh", track_kind="automatic"),
    ]

    ranked = rank_transcript_tracks(
        tracks,
        TranscriptLanguagePreference(preferred_languages=("zh-Hans",)),
    )

    assert [track.id for track in ranked] == ["ai-zh", "ai-ar", "ai-en", "ai-ja"]


def test_transcript_download_candidates_keep_manual_and_matching_automatic() -> None:
    tracks = [
        TranscriptTrack(id="zh", language="zh", track_kind="automatic"),
        TranscriptTrack(id="ai-zh", language="ai-zh", track_kind="automatic"),
        TranscriptTrack(id="en", language="en", track_kind="automatic"),
        TranscriptTrack(id="ja", language="ja", track_kind="manual"),
    ]

    candidates = transcript_download_candidates(
        tracks,
        TranscriptLanguagePreference(preferred_languages=("zh-Hans",)),
    )

    assert [track.id for track in candidates] == ["zh", "ai-zh", "ja"]


def test_transcript_download_candidates_keep_all_without_preferred_language() -> None:
    tracks = [
        TranscriptTrack(id="en", language="en", track_kind="automatic"),
        TranscriptTrack(id="ja", language="ja", track_kind="manual"),
    ]

    candidates = transcript_download_candidates(
        tracks,
        TranscriptLanguagePreference(preferred_languages=()),
    )

    assert candidates == tracks
