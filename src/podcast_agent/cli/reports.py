"""CLI commands for rendered report formats."""

from pathlib import Path

import typer

from podcast_agent.cli.app import app
from podcast_agent.config import DEFAULT_OUTPUT_DIR
from podcast_agent.errors import PodcastAgentError
from podcast_agent.insights.llm import build_default_model_writer
from podcast_agent.reports.html import render_pdf_report
from podcast_agent.reports.markdown import render_markdown_report
from podcast_agent.reports.xhs import compose_xhs_report, prepare_xhs_cover, render_xhs_images


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


@app.command("report-pdf")
def report_pdf(
    output_dir: Path = typer.Option(
        Path(DEFAULT_OUTPUT_DIR),
        help="Directory containing reports/report.html.",
    ),
) -> None:
    """Render reports/report.pdf from an existing HTML report."""
    try:
        pdf_path = render_pdf_report(output_dir=output_dir)
    except PodcastAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Rendered PDF report: {pdf_path}")


@app.command("xhs-report")
def xhs_report(
    output_dir: Path = typer.Option(
        Path(DEFAULT_OUTPUT_DIR),
        help="Directory containing existing podcast-agent artifacts.",
    ),
    angle: str | None = typer.Option(None, help="Optional writing angle for the XHS note."),
    width: int = typer.Option(1080, help="Rendered image width in CSS pixels."),
    height: int = typer.Option(1440, help="Rendered image height in CSS pixels."),
    dpr: int = typer.Option(2, help="Rendered image device pixel ratio."),
    skip_render: bool = typer.Option(False, help="Only generate note.md and post_meta.json."),
) -> None:
    """Generate a Xiaohongshu image-text report from an existing run directory."""
    try:
        typer.echo("Stage 1/3: composing xhs note")
        compose_result = compose_xhs_report(
            output_dir=output_dir,
            model_writer=build_default_model_writer(),
            angle=angle,
        )

        typer.echo("Stage 2/3: preparing cover")
        xhs_dir = output_dir / "reports" / "xhs"
        prepare_xhs_cover(output_dir=output_dir, xhs_dir=xhs_dir)

        if skip_render:
            typer.echo("Stage 3/3: rendering xhs images skipped")
            render_result = None
        else:
            typer.echo("Stage 3/3: rendering xhs images")
            render_result = render_xhs_images(
                note_path=compose_result.note_path,
                output_dir=xhs_dir,
                width=width,
                height=height,
                dpr=dpr,
            )
    except PodcastAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Generated XHS note: {compose_result.note_path}")
    typer.echo(f"Generated XHS post meta: {compose_result.post_meta_path}")
    if render_result is not None:
        typer.echo(f"Rendered XHS images: {render_result.intro_path.parent}")
