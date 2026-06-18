"""Shared yt-dlp integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from podcast_agent.config import BILIBILI_USER_AGENT
from podcast_agent.errors import YtDlpError

try:
    import yt_dlp  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - depends on runtime environment.
    yt_dlp = None


def build_base_yt_dlp_options(*, cookies_file: str | None = None) -> dict[str, Any]:
    options: dict[str, Any] = {
        "ignoreconfig": True,
        "js_runtimes": {"node": {}},
        "quiet": True,
        "no_warnings": True,
    }
    if cookies_file:
        options["cookiefile"] = cookies_file
    return options


def build_bilibili_base_yt_dlp_options(
    *,
    cookies_file: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    options = build_base_yt_dlp_options(cookies_file=cookies_file)
    options["http_headers"] = {
        "Referer": "https://www.bilibili.com/",
        "User-Agent": user_agent or BILIBILI_USER_AGENT or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125 Safari/537.36"
        ),
    }
    return options


def build_bilibili_metadata_yt_dlp_options(
    *,
    output_dir: Path,
    cookies_file: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    return {
        **build_bilibili_base_yt_dlp_options(cookies_file=cookies_file, user_agent=user_agent),
        "skip_download": True,
        "listsubtitles": True,
        "writethumbnail": True,
        "postprocessors": [
            {
                "key": "FFmpegThumbnailsConvertor",
                "format": "jpg",
                "when": "before_dl",
            }
        ],
        "paths": {"home": str(output_dir)},
        "outtmpl": "%(id)s.%(ext)s",
    }


def build_bilibili_subtitle_download_yt_dlp_options(
    *,
    output_dir: Path,
    language: str,
    track_kind: str,
    cookies_file: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    return {
        **build_bilibili_base_yt_dlp_options(cookies_file=cookies_file, user_agent=user_agent),
        "skip_download": True,
        "format": None,
        "writesubtitles": track_kind == "manual",
        "writeautomaticsub": track_kind == "automatic",
        "subtitleslangs": [language],
        "subtitlesformat": "srt/vtt/best",
        "convertsubtitles": "srt",
        "writeinfojson": True,
        "paths": {"home": str(output_dir)},
        "outtmpl": "%(id)s.%(ext)s",
    }


def build_bilibili_audio_download_yt_dlp_options(
    *,
    output_dir: Path,
    cookies_file: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    return {
        **build_bilibili_base_yt_dlp_options(cookies_file=cookies_file, user_agent=user_agent),
        "format": "worstaudio",
        "extractaudio": True,
        "audioformat": "wav",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }
        ],
        "paths": {"home": str(output_dir)},
        "outtmpl": "%(id)s.%(ext)s",
    }


def build_metadata_yt_dlp_options(
    *,
    output_dir: Path,
    cookies_file: str | None = None,
) -> dict[str, Any]:
    return {
        **build_base_yt_dlp_options(cookies_file=cookies_file),
        "skip_download": True,
        "listsubtitles": True,
        "writethumbnail": True,
        "postprocessors": [
            {
                "key": "FFmpegThumbnailsConvertor",
                "format": "jpg",
                "when": "before_dl",
            }
        ],
        "paths": {"home": str(output_dir)},
        "outtmpl": "%(id)s.%(ext)s",
    }


def build_subtitle_download_yt_dlp_options(
    *,
    output_dir: Path,
    language: str,
    track_kind: str,
    cookies_file: str | None = None,
) -> dict[str, Any]:
    return {
        **build_base_yt_dlp_options(cookies_file=cookies_file),
        "skip_download": True,
        "format": None,
        "writesubtitles": track_kind == "manual",
        "writeautomaticsub": track_kind == "automatic",
        "subtitleslangs": [language],
        "subtitlesformat": "srt/vtt/best",
        "convertsubtitles": "srt",
        "writeinfojson": True,
        "paths": {"home": str(output_dir)},
        "outtmpl": "%(id)s.%(ext)s",
    }


def build_audio_download_yt_dlp_options(
    *,
    output_dir: Path,
    cookies_file: str | None = None,
) -> dict[str, Any]:
    return {
        **build_base_yt_dlp_options(cookies_file=cookies_file),
        "format": "worstaudio",
        "extractaudio": True,
        "audioformat": "wav",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }
        ],
        "paths": {"home": str(output_dir)},
        "outtmpl": "%(id)s.%(ext)s",
    }


class YtDlpDownloader:
    def __init__(self, *, cookies_file: str | None = None) -> None:
        self.cookies_file = cookies_file

    def extract_info(self, url: str, *, output_dir: Path) -> dict[str, Any]:
        options = build_metadata_yt_dlp_options(
            output_dir=output_dir,
            cookies_file=self.cookies_file,
        )
        info = self._extract(url=url, output_dir=output_dir, options=options, download=True)
        thumbnail_path = _find_downloaded_thumbnail(output_dir=output_dir, video_id=info.get("id"))
        if thumbnail_path is None:
            thumbnail_path = _download_thumbnail_from_url(output_dir=output_dir, info=info)
        if thumbnail_path is not None:
            info["local_thumbnail_path"] = str(thumbnail_path)
        return info

    def download_subtitle(
        self,
        url: str,
        *,
        output_dir: Path,
        language: str,
        track_kind: str,
    ) -> dict[str, Any]:
        options = build_subtitle_download_yt_dlp_options(
            output_dir=output_dir,
            language=language,
            track_kind=track_kind,
            cookies_file=self.cookies_file,
        )
        return self._extract(url=url, output_dir=output_dir, options=options, download=True)

    def download_audio(self, url: str, *, output_dir: Path) -> dict[str, Any]:
        options = build_audio_download_yt_dlp_options(
            output_dir=output_dir,
            cookies_file=self.cookies_file,
        )
        return self._extract(url=url, output_dir=output_dir, options=options, download=True)

    def _extract(
        self,
        *,
        url: str,
        output_dir: Path,
        options: dict[str, Any],
        download: bool,
    ) -> dict[str, Any]:
        if yt_dlp is None:
            raise YtDlpError("yt-dlp is required for YouTube extraction.")
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=download)
                sanitized = ydl.sanitize_info(info)
        except Exception as exc:  # pragma: no cover - depends on yt-dlp runtime behavior.
            raise YtDlpError(f"yt-dlp failed: {exc}") from exc
        if not isinstance(sanitized, dict):
            raise YtDlpError("yt-dlp returned invalid info payload.")
        return sanitized


class BilibiliYtDlpDownloader(YtDlpDownloader):
    def __init__(self, *, cookies_file: str | None = None, user_agent: str | None = None) -> None:
        super().__init__(cookies_file=cookies_file)
        self.user_agent = user_agent

    def extract_info(self, url: str, *, output_dir: Path) -> dict[str, Any]:
        options = build_bilibili_metadata_yt_dlp_options(
            output_dir=output_dir,
            cookies_file=self.cookies_file,
            user_agent=self.user_agent,
        )
        info = self._extract(url=url, output_dir=output_dir, options=options, download=True)
        thumbnail_path = _find_downloaded_thumbnail(output_dir=output_dir, video_id=info.get("id"))
        if thumbnail_path is None:
            thumbnail_path = _download_thumbnail_from_url(output_dir=output_dir, info=info)
        if thumbnail_path is not None:
            info["local_thumbnail_path"] = str(thumbnail_path)
        return info

    def download_subtitle(
        self,
        url: str,
        *,
        output_dir: Path,
        language: str,
        track_kind: str,
    ) -> dict[str, Any]:
        options = build_bilibili_subtitle_download_yt_dlp_options(
            output_dir=output_dir,
            language=language,
            track_kind=track_kind,
            cookies_file=self.cookies_file,
            user_agent=self.user_agent,
        )
        return self._extract(url=url, output_dir=output_dir, options=options, download=True)

    def download_audio(self, url: str, *, output_dir: Path) -> dict[str, Any]:
        options = build_bilibili_audio_download_yt_dlp_options(
            output_dir=output_dir,
            cookies_file=self.cookies_file,
            user_agent=self.user_agent,
        )
        return self._extract(url=url, output_dir=output_dir, options=options, download=True)


def _find_downloaded_thumbnail(*, output_dir: Path, video_id: Any) -> Path | None:
    if not isinstance(video_id, str) or not video_id:
        return None

    thumbnail_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    for path in sorted(output_dir.iterdir()):
        if path.is_file() and path.stem == video_id and path.suffix.lower() in thumbnail_extensions:
            return path
    return None


def _download_thumbnail_from_url(*, output_dir: Path, info: dict[str, Any]) -> Path | None:
    video_id = info.get("id")
    thumbnail_url = info.get("thumbnail")
    if not isinstance(video_id, str) or not video_id:
        return None
    if not isinstance(thumbnail_url, str) or not thumbnail_url.strip():
        return None

    try:
        import requests
    except ImportError:
        return None

    thumbnail_url = thumbnail_url.strip()
    target = output_dir / f"{video_id}{_thumbnail_suffix(thumbnail_url)}"
    try:
        response = requests.get(thumbnail_url, timeout=30)
        response.raise_for_status()
    except Exception:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    return target


def _thumbnail_suffix(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    return ".jpg"
