"""CLI commands for pipeline and insight generation stages."""

from pathlib import Path

import typer

from podcast_agent.cli.app import app
from podcast_agent.cli.audio import LazyDefaultAliyunTranscriber
from podcast_agent.config import DEFAULT_OUTPUT_DIR
from podcast_agent.errors import PodcastAgentError
from podcast_agent.insights.evidence import extract_evidence
from podcast_agent.insights.llm import build_default_model_writer
from podcast_agent.insights.outline import generate_outline
from podcast_agent.insights.summary import generate_summary
from podcast_agent.insights.viewpoint import generate_viewpoints
from podcast_agent.intent import resolve_report_intent, write_report_intent
from podcast_agent.pipeline.artifacts import load_json
from podcast_agent.pipeline.runner import run_pipeline
from podcast_agent.reports.html import render_pdf_report
from podcast_agent.reports.markdown import render_markdown_report
from podcast_agent.reports.xhs import compose_xhs_report, prepare_xhs_cover, render_xhs_images


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
    """Run the full pipeline and render Markdown, HTML, PDF, and XHS reports."""
    try:
        model_writer = build_default_model_writer()

        typer.echo("Stage 1/11: detecting report intent")
        report_intent = resolve_report_intent(question=question, model_writer=model_writer)
        intent_path = write_report_intent(path=output_dir / "insights" / "intent.json", question=question, intent=report_intent)
        typer.echo(f"Detected report intent: {report_intent.report_language} {report_intent.report_length} ({report_intent.source})")
        typer.echo(str(intent_path))

        typer.echo("Stage 2/11: fetching source, metadata, and transcript")
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

        typer.echo("Stage 3/11: extracting evidence")
        evidence_artifact = extract_evidence(output_dir=output_dir, model_writer=model_writer)
        typer.echo(f"Extracted evidence: {len(evidence_artifact['segments'])} segments")

        typer.echo("Stage 4/11: generating outline")
        outline_artifact = generate_outline(output_dir=output_dir, model_writer=model_writer, report_intent=report_intent)
        typer.echo(f"Generated outline: {len(outline_artifact['viewpoint_breakdown'])} viewpoints")

        typer.echo("Stage 5/11: generating viewpoint details")
        viewpoints_artifact = generate_viewpoints(output_dir=output_dir, model_writer=model_writer, report_intent=report_intent)
        typer.echo(f"Generated viewpoints: {len(viewpoints_artifact['viewpoint_details'])} details")

        typer.echo("Stage 6/11: generating summary")
        summary_artifact = generate_summary(output_dir=output_dir, model_writer=model_writer, report_intent=report_intent)
        typer.echo(f"Generated summary: {len(summary_artifact['core_conclusions'])} conclusions")

        typer.echo("Stage 7/11: rendering Markdown and HTML report")
        report_path = render_markdown_report(output_dir=output_dir, report_intent=report_intent)

        typer.echo("Stage 8/11: rendering PDF report")
        pdf_path = render_pdf_report(output_dir=output_dir, html_path=report_path.with_suffix(".html"))

        typer.echo("Stage 9/11: composing xhs note")
        compose_result = compose_xhs_report(output_dir=output_dir, model_writer=model_writer)

        typer.echo("Stage 10/11: preparing xhs cover")
        xhs_dir = output_dir / "reports" / "xhs"
        prepare_xhs_cover(output_dir=output_dir, xhs_dir=xhs_dir)

        typer.echo("Stage 11/11: rendering xhs images")
        xhs_render_result = render_xhs_images(note_path=compose_result.note_path, output_dir=xhs_dir)
    except PodcastAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Rendered report: {report_path}")
    typer.echo(f"Rendered HTML report: {report_path.with_suffix('.html')}")
    typer.echo(f"Rendered PDF report: {pdf_path}")
    typer.echo(f"Generated XHS note: {compose_result.note_path}")
    typer.echo(f"Generated XHS post meta: {compose_result.post_meta_path}")
    typer.echo(f"Rendered XHS images: {xhs_render_result.intro_path.parent}")


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
