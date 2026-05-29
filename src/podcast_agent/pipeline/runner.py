"""Top-level pipeline runner."""

from __future__ import annotations

from pathlib import Path

from podcast_agent.config import YOUTUBE_COOKIES_FILE
from podcast_agent.elements.youtube_metadata import MetadataDownloader, YoutubeMetadataFetcher
from podcast_agent.elements.youtube_transcript import (
    TranscriptDownloader,
    YoutubeTranscriptFetcher,
)
from podcast_agent.pipeline.artifacts import save_json
from podcast_agent.pipeline.context import PipelineContext
from podcast_agent.sources.registry import resolve_source
from podcast_agent.transcribers.base import Transcriber
from podcast_agent.types import PipelineInput


def run_pipeline(
    url: str,
    question: str,
    output_dir: Path,
    *,
    metadata_downloader: MetadataDownloader | None = None,
    transcript_downloader: TranscriptDownloader | None = None,
    audio_transcriber: Transcriber | None = None,
) -> PipelineContext:
    context = PipelineContext.create(
        url=url,
        question=question,
        output_dir=output_dir,
    )
    save_json(context.input_path, PipelineInput(url=url, question=question))
    source_ref = resolve_source(url)
    save_json(context.source_path, source_ref)
    metadata = YoutubeMetadataFetcher(
        output_dir=context.elements_dir,
        cookies_file=YOUTUBE_COOKIES_FILE,
        downloader=metadata_downloader,
    ).fetch(source_ref)
    save_json(context.elements_dir / "metadata.json", metadata)
    YoutubeTranscriptFetcher(
        elements_dir=context.elements_dir,
        cookies_file=YOUTUBE_COOKIES_FILE,
        downloader=transcript_downloader,
        transcriber=audio_transcriber,
    ).fetch(source_ref)
    return context
