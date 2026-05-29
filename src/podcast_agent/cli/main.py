"""Podcast-Agent CLI."""

from pathlib import Path

import typer

from podcast_agent.config import DEFAULT_OUTPUT_DIR, YOUTUBE_COOKIES_FILE
from podcast_agent.elements.transcript_format import (
    count_vtt_cues,
    require_non_empty_vtt,
    segments_to_vtt,
    transcript_to_text,
)
from podcast_agent.elements.youtube_transcript import YoutubeTranscriptFetcher
from podcast_agent.errors import PodcastAgentError
from podcast_agent.insights.evidence import extract_evidence
from podcast_agent.insights.llm import build_default_model_writer
from podcast_agent.insights.outline import generate_outline
from podcast_agent.insights.summary import generate_summary
from podcast_agent.insights.viewpoint import generate_viewpoints
from podcast_agent.intent import resolve_report_intent, write_report_intent
from podcast_agent.pipeline.artifacts import load_json
from podcast_agent.pipeline.runner import run_pipeline
from podcast_agent.reports.markdown import render_markdown_report
from podcast_agent.sources.registry import resolve_source
from podcast_agent.transcribers.aliyun import AliyunTranscriber, AliyunTranscriberConfig
from podcast_agent.transcribers.types import TranscriptionRequest

app = typer.Typer(no_args_is_help=True)


class LazyDefaultAliyunTranscriber:
    """Build Aliyun only if transcript acquisition actually needs audio fallback."""

    provider_name = "aliyun"

    def __init__(self) -> None:
        self._transcriber: AliyunTranscriber | None = None

    def transcribe(self, request: TranscriptionRequest):
        if self._transcriber is None:
            self._transcriber = build_default_aliyun_transcriber()
        return self._transcriber.transcribe(request)


@app.callback()
def main() -> None:
    """Podcast-Agent command line interface."""


@app.command()
def run(
    url: str = typer.Option(..., help="Input YouTube URL."),
    question: str = typer.Option(..., help="Question to answer from the content."),
    output_dir: Path = typer.Option(
        Path(DEFAULT_OUTPUT_DIR),
        help="Directory for this pipeline run.",
    ),
) -> None:
    """Initialize a podcast-agent pipeline run."""
    try:
        context = run_pipeline(url=url, question=question, output_dir=output_dir)
    except PodcastAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    source = load_json(context.source_path)
    metadata = load_json(context.elements_dir / "metadata.json")
    transcript_info = load_json(context.elements_dir / "transcript_info.json")
    typer.echo(f"Initialized podcast-agent run at {context.output_dir}")
    typer.echo(f"Resolved source: {source['source_type']} {source['source_id']}")
    typer.echo(f"Fetched metadata: {metadata['title']}")
    typer.echo(
        "Fetched transcript: "
        f"{transcript_info['acquisition_method']} "
        f"({transcript_info['segment_count']} segments)"
    )
    typer.echo("Next step: implement insights extraction.")


@app.command()
def full(
    url: str = typer.Option(..., help="Input YouTube URL."),
    question: str = typer.Option(..., help="Question to answer from the content."),
    output_dir: Path = typer.Option(
        Path(DEFAULT_OUTPUT_DIR),
        help="Directory for this full pipeline run.",
    ),
) -> None:
    """Run the full MVP pipeline and render reports/report.md."""
    try:
        model_writer = build_default_model_writer()

        typer.echo("Stage 1/7: detecting report intent")
        report_intent = resolve_report_intent(question=question, model_writer=model_writer)
        intent_path = write_report_intent(path=output_dir / "insights" / "intent.json", question=question, intent=report_intent)
        typer.echo(f"Detected report intent: {report_intent.report_language} {report_intent.report_length} ({report_intent.source})")
        typer.echo(str(intent_path))

        typer.echo("Stage 2/7: fetching source, metadata, and transcript")
        context = run_pipeline(
            url=url,
            question=question,
            output_dir=output_dir,
            audio_transcriber=LazyDefaultAliyunTranscriber(),
        )
        transcript_info = load_json(context.elements_dir / "transcript_info.json")
        typer.echo(
            "Fetched transcript: "
            f"{transcript_info['acquisition_method']} "
            f"({transcript_info['segment_count']} segments)"
        )

        typer.echo("Stage 3/7: extracting evidence")
        evidence_artifact = extract_evidence(output_dir=output_dir, model_writer=model_writer)
        typer.echo(f"Extracted evidence: {len(evidence_artifact['segments'])} segments")

        typer.echo("Stage 4/7: generating outline")
        outline_artifact = generate_outline(output_dir=output_dir, model_writer=model_writer, report_intent=report_intent)
        typer.echo(f"Generated outline: {len(outline_artifact['viewpoint_breakdown'])} viewpoints")

        typer.echo("Stage 5/7: generating viewpoint details")
        viewpoints_artifact = generate_viewpoints(output_dir=output_dir, model_writer=model_writer, report_intent=report_intent)
        typer.echo(f"Generated viewpoints: {len(viewpoints_artifact['viewpoint_details'])} details")

        typer.echo("Stage 6/7: generating summary")
        summary_artifact = generate_summary(output_dir=output_dir, model_writer=model_writer, report_intent=report_intent)
        typer.echo(f"Generated summary: {len(summary_artifact['core_conclusions'])} conclusions")

        typer.echo("Stage 7/7: rendering report")
        report_path = render_markdown_report(output_dir=output_dir, report_intent=report_intent)
    except PodcastAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Rendered report: {report_path}")
    typer.echo(f"Rendered HTML report: {report_path.with_suffix('.html')}")


@app.command()
def intent(
    question: str = typer.Option(..., help="Question used to infer output language and report length."),
    output_dir: Path = typer.Option(
        Path(DEFAULT_OUTPUT_DIR),
        help="Directory for intent.json.",
    ),
) -> None:
    """Detect and persist report intent from a user question."""
    try:
        report_intent = resolve_report_intent(
            question=question,
            model_writer=build_default_model_writer(),
        )
        intent_path = write_report_intent(path=output_dir / "insights" / "intent.json", question=question, intent=report_intent)
    except PodcastAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Detected report intent: {report_intent.report_language} {report_intent.report_length} ({report_intent.source})")
    typer.echo(str(intent_path))


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


@app.command()
def evidence(
    output_dir: Path = typer.Option(
        Path(DEFAULT_OUTPUT_DIR),
        help="Directory containing input/source/elements artifacts.",
    ),
    url: str | None = typer.Option(
        None,
        help="Input YouTube URL used to generate missing upstream artifacts.",
    ),
    question: str | None = typer.Option(
        None,
        help="Question used to generate missing input.json.",
    ),
) -> None:
    """Extract evidence.json, reusing upstream artifacts when present."""
    try:
        if not _has_evidence_inputs(output_dir):
            if not url or not question:
                typer.echo(
                    "Evidence requires existing input.json and elements/transcript.vtt. "
                    "Provide --url and --question to generate upstream artifacts first.",
                    err=True,
                )
                raise typer.Exit(code=1)
            run_pipeline(
                url=url,
                question=question,
                output_dir=output_dir,
                audio_transcriber=LazyDefaultAliyunTranscriber(),
            )
        artifact = extract_evidence(
            output_dir=output_dir,
            model_writer=build_default_model_writer(),
        )
    except PodcastAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Extracted evidence: {len(artifact['segments'])} segments")
    typer.echo(str(output_dir / "insights" / "evidence.json"))


def _has_evidence_inputs(output_dir: Path) -> bool:
    return (output_dir / "input.json").is_file() and (output_dir / "elements" / "transcript.vtt").is_file()


@app.command()
def outline(
    output_dir: Path = typer.Option(
        Path(DEFAULT_OUTPUT_DIR),
        help="Directory containing input/source/metadata/evidence artifacts.",
    ),
) -> None:
    """Generate outline.json from an existing evidence artifact."""
    try:
        artifact = generate_outline(
            output_dir=output_dir,
            model_writer=build_default_model_writer(),
        )
    except PodcastAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Generated outline: {len(artifact['viewpoint_breakdown'])} viewpoints")
    typer.echo(str(output_dir / "insights" / "outline.json"))


@app.command()
def viewpoints(
    output_dir: Path = typer.Option(
        Path(DEFAULT_OUTPUT_DIR),
        help="Directory containing input/source/metadata/evidence/outline artifacts.",
    ),
) -> None:
    """Generate viewpoints.json from existing evidence and outline artifacts."""
    try:
        artifact = generate_viewpoints(
            output_dir=output_dir,
            model_writer=build_default_model_writer(),
        )
    except PodcastAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Generated viewpoints: {len(artifact['viewpoint_details'])} details")
    typer.echo(str(output_dir / "insights" / "viewpoints.json"))


@app.command()
def summary(
    output_dir: Path = typer.Option(
        Path(DEFAULT_OUTPUT_DIR),
        help="Directory containing input/source/metadata/viewpoints artifacts.",
    ),
) -> None:
    """Generate summary.json from an existing viewpoints artifact."""
    try:
        artifact = generate_summary(
            output_dir=output_dir,
            model_writer=build_default_model_writer(),
        )
    except PodcastAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Generated summary: {len(artifact['core_conclusions'])} conclusions")
    typer.echo(str(output_dir / "insights" / "summary.json"))


@app.command()
def report(
    output_dir: Path = typer.Option(
        Path(DEFAULT_OUTPUT_DIR),
        help="Directory containing input/source/elements/insights artifacts.",
    ),
) -> None:
    """Render reports/report.md from existing insight artifacts."""
    try:
        report_path = render_markdown_report(output_dir=output_dir)
    except PodcastAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Rendered report: {report_path}")
    typer.echo(f"Rendered HTML report: {report_path.with_suffix('.html')}")


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
