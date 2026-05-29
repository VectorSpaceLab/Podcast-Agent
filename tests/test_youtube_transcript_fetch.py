from pathlib import Path

from podcast_agent.elements.youtube_transcript import YoutubeTranscriptFetcher
from podcast_agent.pipeline.artifacts import load_json
from podcast_agent.types import SourceRef
from tests.fakes import FakeAudioTranscriber, FakeTranscriptDownloader


SOURCE = SourceRef(
    source_type="youtube",
    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    source_id="dQw4w9WgXcQ",
)


def test_youtube_transcript_fetcher_writes_vtt_text_and_info(tmp_path: Path) -> None:
    info = YoutubeTranscriptFetcher(
        elements_dir=tmp_path,
        downloader=FakeTranscriptDownloader(),
    ).fetch(SOURCE)

    assert info.acquisition_method == "youtube_subtitle"
    assert info.language == "zh-Hans"
    assert info.subtitle_kind == "manual"
    assert (tmp_path / "transcript.vtt").read_text(encoding="utf-8").startswith("WEBVTT")
    assert (tmp_path / "transcript.txt").read_text(encoding="utf-8") == "第一句字幕。\n第二句字幕。\n"
    assert load_json(tmp_path / "transcript_info.json")["segment_count"] == 2


def test_youtube_transcript_fetcher_converts_srt_to_vtt(tmp_path: Path) -> None:
    YoutubeTranscriptFetcher(
        elements_dir=tmp_path,
        downloader=FakeTranscriptDownloader(subtitle_suffix=".srt"),
    ).fetch(SOURCE)

    vtt = (tmp_path / "transcript.vtt").read_text(encoding="utf-8")
    assert "00:00:00.000 --> 00:00:01.500" in vtt


def test_youtube_transcript_fetcher_falls_back_to_audio_transcription(tmp_path: Path) -> None:
    downloader = FakeTranscriptDownloader(info={"subtitles": {}, "automatic_captions": {}})
    transcriber = FakeAudioTranscriber()

    info = YoutubeTranscriptFetcher(
        elements_dir=tmp_path,
        downloader=downloader,
        transcriber=transcriber,
    ).fetch(SOURCE)

    assert info.acquisition_method == "audio_transcription"
    assert info.audio_fallback_used is True
    assert info.transcription_provider == "fake"
    assert (tmp_path / "audio_info.json").is_file()
    assert (tmp_path / "transcript.txt").read_text(encoding="utf-8") == "转录第一句。\n转录第二句。\n"
    assert transcriber.calls
