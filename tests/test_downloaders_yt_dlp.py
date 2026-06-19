from pathlib import Path

from podcast_agent.downloaders.yt_dlp import (
    build_bilibili_metadata_yt_dlp_options,
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
    assert options["remote_components"] == ["ejs:github"]
    assert options["quiet"] is True
    assert options["no_warnings"] is True
    assert options["socket_timeout"] == 60
    assert options["retries"] == 5
    assert options["extractor_retries"] == 5


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
    assert options["ignore_no_formats_error"] is True
    assert options["subtitleslangs"] == ["en"]
    assert options["subtitlesformat"] == "srt/vtt/best"
    assert options["convertsubtitles"] == "srt"
    assert options["sleep_interval_subtitles"] == 30


def test_build_audio_download_options_contains_audio_postprocessor(tmp_path: Path) -> None:
    options = build_audio_download_yt_dlp_options(output_dir=tmp_path)

    assert options["format"] == "worstaudio"
    assert options["extractaudio"] is True
    assert options["audioformat"] == "wav"
    assert options["postprocessors"][0]["key"] == "FFmpegExtractAudio"


def test_build_bilibili_metadata_options_uses_cookie_referer_and_user_agent(tmp_path: Path) -> None:
    options = build_bilibili_metadata_yt_dlp_options(
        output_dir=tmp_path,
        cookies_file="/tmp/bilibili-cookies.txt",
        cookies_from_browser="chrome",
        user_agent="Custom UA",
    )

    assert options["cookiefile"] == "/tmp/bilibili-cookies.txt"
    assert options["cookiesfrombrowser"] == ("chrome",)
    assert options["http_headers"]["Referer"] == "https://www.bilibili.com/"
    assert options["http_headers"]["User-Agent"] == "Custom UA"
    assert options["listsubtitles"] is True


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
