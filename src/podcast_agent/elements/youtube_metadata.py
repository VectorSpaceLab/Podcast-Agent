"""YouTube metadata fetching."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from podcast_agent.downloaders.yt_dlp import YtDlpDownloader
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
        self.downloader = downloader or YtDlpDownloader(cookies_file=cookies_file)

    def fetch(self, source: SourceRef) -> VideoMetadata:
        try:
            info = self.downloader.extract_info(source.url, output_dir=self.output_dir)
            return normalize_metadata(source, info)
        except MetadataFetchError:
            raise
        except YtDlpError as exc:
            raise MetadataFetchError(f"Metadata fetch failed: {exc}") from exc
        except Exception as exc:
            raise MetadataFetchError(f"Metadata fetch failed: {exc}") from exc
