from podcast_agent.elements.transcript_format import (
    count_vtt_cues,
    segments_to_vtt,
    srt_to_vtt,
    transcript_to_text,
)
from podcast_agent.types import TranscriptSegment
from tests.fakes import fake_srt_content, fake_vtt_content


def test_srt_to_vtt_converts_timestamps() -> None:
    vtt = srt_to_vtt(fake_srt_content())

    assert vtt.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:01.500" in vtt
    assert "第一句字幕。" in vtt


def test_transcript_to_text_removes_timestamps() -> None:
    text = transcript_to_text(fake_vtt_content())

    assert text == "第一句字幕。\n第二句字幕。\n"


def test_segments_to_vtt_formats_transcription_segments() -> None:
    vtt = segments_to_vtt(
        [
            TranscriptSegment(start=0.0, end=1.5, text="转录第一句。"),
            TranscriptSegment(start=1.5, end=3.0, text="转录第二句。"),
        ]
    )

    assert "WEBVTT" in vtt
    assert "00:00:01.500 --> 00:00:03.000" in vtt
    assert count_vtt_cues(vtt) == 2
