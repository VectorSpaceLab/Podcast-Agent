"""YouTube metadata fetching."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from podcast_agent.config import (
    BILIBILI_COOKIES_FILE,
    BILIBILI_COOKIES_FROM_BROWSER,
    BILIBILI_USER_AGENT,
    YOUTUBE_COOKIES_FILE,
)
from podcast_agent.downloaders.yt_dlp import BilibiliYtDlpDownloader, YtDlpDownloader
from podcast_agent.errors import MetadataFetchError, YtDlpError
from podcast_agent.elements.metadata import normalize_metadata
from podcast_agent.types import SourceRef, VideoMetadata


class MetadataDownloader(Protocol):
    def extract_info(self, url: str, *, output_dir: Path) -> dict[str, Any]:
        ...


class YoutubeMetadataFetcher:
    def __init__(
        self,
        *,
        output_dir: Path,
        cookies_file: str | None = None,
        downloader: MetadataDownloader | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.downloader = downloader
        self.cookies_file = cookies_file

    def fetch(self, source: SourceRef) -> VideoMetadata:
        try:
            downloader = self.downloader or _default_metadata_downloader(source, self.cookies_file)
            info = downloader.extract_info(source.url, output_dir=self.output_dir)
            return normalize_metadata(source, info)
        except MetadataFetchError:
            raise
        except YtDlpError as exc:
            raise MetadataFetchError(f"Metadata fetch failed: {exc}") from exc
        except Exception as exc:
            raise MetadataFetchError(f"Metadata fetch failed: {exc}") from exc


def _default_metadata_downloader(source: SourceRef, cookies_file: str | None) -> MetadataDownloader:
    if source.source_type == "bilibili":
        return BilibiliYtDlpDownloader(
            cookies_file=cookies_file or BILIBILI_COOKIES_FILE,
            cookies_from_browser=BILIBILI_COOKIES_FROM_BROWSER,
            user_agent=BILIBILI_USER_AGENT,
        )
    return YtDlpDownloader(cookies_file=cookies_file or YOUTUBE_COOKIES_FILE)
