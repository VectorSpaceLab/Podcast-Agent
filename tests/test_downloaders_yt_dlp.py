from pathlib import Path

from podcast_agent.downloaders.yt_dlp import (
    build_audio_download_yt_dlp_options,
    build_base_yt_dlp_options,
    build_metadata_yt_dlp_options,
    build_subtitle_download_yt_dlp_options,
    _download_thumbnail_from_url,
)


def test_build_base_yt_dlp_options_contains_common_options() -> None:
    options = build_base_yt_dlp_options()

    assert options["ignoreconfig"] is True
    assert options["js_runtimes"] == {"node": {}}
    assert options["quiet"] is True
    assert options["no_warnings"] is True


def test_build_base_yt_dlp_options_adds_cookiefile() -> None:
    options = build_base_yt_dlp_options(cookies_file="/tmp/cookies.txt")

    assert options["cookiefile"] == "/tmp/cookies.txt"


def test_build_metadata_yt_dlp_options_contains_metadata_options(tmp_path: Path) -> None:
    options = build_metadata_yt_dlp_options(output_dir=tmp_path)

    assert options["skip_download"] is True
    assert options["listsubtitles"] is True
    assert options["writethumbnail"] is True
    assert options["postprocessors"] == [
        {
            "key": "FFmpegThumbnailsConvertor",
            "format": "jpg",
            "when": "before_dl",
        }
    ]
    assert options["paths"] == {"home": str(tmp_path)}
    assert options["outtmpl"] == "%(id)s.%(ext)s"


def test_build_subtitle_download_options_selects_manual_track(tmp_path: Path) -> None:
    options = build_subtitle_download_yt_dlp_options(
        output_dir=tmp_path,
        language="en",
        track_kind="manual",
    )

    assert options["writesubtitles"] is True
    assert options["writeautomaticsub"] is False
    assert options["subtitleslangs"] == ["en"]
    assert options["subtitlesformat"] == "srt/vtt/best"
    assert options["convertsubtitles"] == "srt"


def test_build_audio_download_options_contains_audio_postprocessor(tmp_path: Path) -> None:
    options = build_audio_download_yt_dlp_options(output_dir=tmp_path)

    assert options["format"] == "worstaudio"
    assert options["extractaudio"] is True
    assert options["audioformat"] == "wav"
    assert options["postprocessors"][0]["key"] == "FFmpegExtractAudio"


def test_download_thumbnail_from_url_writes_thumbnail(tmp_path: Path, monkeypatch) -> None:
    class FakeResponse:
        content = b"jpg"

        def raise_for_status(self) -> None:
            return None

    class FakeRequests:
        @staticmethod
        def get(url: str, timeout: int) -> FakeResponse:
            assert url == "https://i.ytimg.com/vi/demo/maxresdefault.jpg"
            assert timeout == 30
            return FakeResponse()

    monkeypatch.setitem(__import__("sys").modules, "requests", FakeRequests)

    path = _download_thumbnail_from_url(
        output_dir=tmp_path,
        info={"id": "demo", "thumbnail": "https://i.ytimg.com/vi/demo/maxresdefault.jpg"},
    )

    assert path == tmp_path / "demo.jpg"
    assert path.read_bytes() == b"jpg"


def test_download_thumbnail_from_url_returns_none_on_failure(tmp_path: Path, monkeypatch) -> None:
    class FakeRequests:
        @staticmethod
        def get(url: str, timeout: int):
            raise RuntimeError("network down")

    monkeypatch.setitem(__import__("sys").modules, "requests", FakeRequests)

    path = _download_thumbnail_from_url(
        output_dir=tmp_path,
        info={"id": "demo", "thumbnail": "https://i.ytimg.com/vi/demo/maxresdefault.jpg"},
    )

    assert path is None
    assert not list(tmp_path.iterdir())
