"""CLI commands and helpers for transcript acquisition and audio transcription."""

from pathlib import Path

import typer

from podcast_agent.cli.app import app
from podcast_agent.config import DEFAULT_OUTPUT_DIR, YOUTUBE_COOKIES_FILE
from podcast_agent.elements.transcript_format import (
    count_vtt_cues,
    require_non_empty_vtt,
    segments_to_vtt,
    transcript_to_text,
)
from podcast_agent.elements.youtube_transcript import YoutubeTranscriptFetcher
from podcast_agent.errors import PodcastAgentError
from podcast_agent.sources.registry import resolve_source
from podcast_agent.transcribers.aliyun import AliyunTranscriber, AliyunTranscriberConfig
from podcast_agent.transcribers.types import TranscriptionRequest


class LazyDefaultAliyunTranscriber:
    """Build Aliyun only if transcript acquisition actually needs audio fallback."""

    provider_name = "aliyun"

    def __init__(self) -> None:
        self._transcriber: AliyunTranscriber | None = None

    def transcribe(self, request: TranscriptionRequest):
        if self._transcriber is None:
            self._transcriber = build_default_aliyun_transcriber()
        return self._transcriber.transcribe(request)


@app.command()
def transcript(
    url: str = typer.Option(..., help="Input YouTube URL."),
    output_dir: Path = typer.Option(
        Path(DEFAULT_OUTPUT_DIR) / "transcript-demo",
        help="Directory for transcript artifacts.",
    ),
) -> None:
    """Fetch transcript artifacts for a YouTube URL."""
    try:
        source = resolve_source(url)
        info = YoutubeTranscriptFetcher(
            elements_dir=output_dir / "elements",
            cookies_file=YOUTUBE_COOKIES_FILE,
            transcriber=LazyDefaultAliyunTranscriber(),
        ).fetch(source)
    except PodcastAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Fetched transcript: {info.acquisition_method} ({info.segment_count} segments)")
    typer.echo(str(output_dir / info.transcript_path))
    typer.echo(str(output_dir / info.text_path))
    typer.echo(str(output_dir / "elements" / "transcript_info.json"))


@app.command("transcribe-audio")
def transcribe_audio(
    audio_path: Path = typer.Option(..., help="Local audio file to transcribe."),
    output_dir: Path = typer.Option(
        Path(DEFAULT_OUTPUT_DIR) / "transcribe-audio-demo",
        help="Directory for transcript artifacts.",
    ),
    language: str = typer.Option("zh", help="Primary transcription language hint."),
) -> None:
    """Transcribe a local audio file into transcript.vtt and transcript.txt."""
    try:
        transcriber = build_default_aliyun_transcriber()
        result = transcriber.transcribe(
            TranscriptionRequest(
                audio_path=audio_path,
                language_hints=(language,) if language else (),
            )
        )
        elements_dir = output_dir / "elements"
        elements_dir.mkdir(parents=True, exist_ok=True)
        vtt_content = segments_to_vtt(result.segments)
        require_non_empty_vtt(vtt_content)
        text_content = transcript_to_text(vtt_content)
        (elements_dir / "transcript.vtt").write_text(vtt_content, encoding="utf-8")
        (elements_dir / "transcript.txt").write_text(text_content, encoding="utf-8")
    except PodcastAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Transcribed audio: {result.provider} ({count_vtt_cues(vtt_content)} segments)")
    typer.echo(str(elements_dir / "transcript.vtt"))
    typer.echo(str(elements_dir / "transcript.txt"))


def build_default_aliyun_transcriber() -> AliyunTranscriber:
    import os

    required = {
        "ALIYUN_API_KEY": os.getenv("ALIYUN_API_KEY"),
        "OSS_ENDPOINT": os.getenv("OSS_ENDPOINT"),
        "OSS_BUCKET_NAME": os.getenv("OSS_BUCKET_NAME"),
        "OSS_ACCESS_KEY_ID": os.getenv("OSS_ACCESS_KEY_ID"),
        "OSS_ACCESS_KEY_SECRET": os.getenv("OSS_ACCESS_KEY_SECRET"),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise PodcastAgentError(f"Missing required Aliyun environment variables: {', '.join(missing)}")

    return AliyunTranscriber(
        AliyunTranscriberConfig(
            api_key=required["ALIYUN_API_KEY"] or "",
            oss_endpoint=required["OSS_ENDPOINT"] or "",
            oss_bucket_name=required["OSS_BUCKET_NAME"] or "",
            oss_access_key_id=required["OSS_ACCESS_KEY_ID"] or "",
            oss_access_key_secret=required["OSS_ACCESS_KEY_SECRET"] or "",
            api_base=os.getenv("ALIYUN_ASR_API_BASE") or "https://dashscope.aliyuncs.com/api/v1",
            model=os.getenv("ALIYUN_ASR_MODEL") or "fun-asr",
        )
    )
