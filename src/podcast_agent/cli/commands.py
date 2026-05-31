"""Register and re-export Podcast-Agent CLI commands."""

from podcast_agent.cli.app import app

# Import modules for Typer command registration.
from podcast_agent.cli import audio as audio
from podcast_agent.cli import batch as batch
from podcast_agent.cli import reports as reports
from podcast_agent.cli import stages as stages

from podcast_agent.cli.audio import (
    LazyDefaultAliyunTranscriber,
    YoutubeTranscriptFetcher,
    build_default_aliyun_transcriber,
    transcript,
    transcribe_audio,
)
from podcast_agent.cli.batch import (
    FullBatchCase,
    FullBatchCaseResult,
    full_batch,
    load_full_batch_cases,
    resolve_podcast_agent_command,
    run_full_batch_case,
    run_full_batch_plans,
    select_full_batch_cases,
    utc_run_id,
    write_full_batch_summary,
)
from podcast_agent.cli.reports import (
    compose_xhs_report,
    prepare_xhs_cover,
    render_markdown_report,
    render_pdf_report,
    render_xhs_images,
    report,
    report_pdf,
    xhs_report,
)
from podcast_agent.cli.stages import (
    build_default_model_writer,
    evidence,
    extract_evidence,
    full,
    generate_outline,
    generate_summary,
    generate_viewpoints,
    intent,
    outline,
    resolve_report_intent,
    run,
    run_pipeline,
    summary,
    viewpoints,
    write_report_intent,
)

__all__ = [
    "FullBatchCase",
    "FullBatchCaseResult",
    "LazyDefaultAliyunTranscriber",
    "YoutubeTranscriptFetcher",
    "app",
    "build_default_aliyun_transcriber",
    "build_default_model_writer",
    "compose_xhs_report",
    "evidence",
    "extract_evidence",
    "full",
    "full_batch",
    "generate_outline",
    "generate_summary",
    "generate_viewpoints",
    "intent",
    "load_full_batch_cases",
    "outline",
    "prepare_xhs_cover",
    "render_markdown_report",
    "render_pdf_report",
    "render_xhs_images",
    "report",
    "report_pdf",
    "resolve_podcast_agent_command",
    "resolve_report_intent",
    "run",
    "run_full_batch_case",
    "run_full_batch_plans",
    "run_pipeline",
    "select_full_batch_cases",
    "summary",
    "transcribe_audio",
    "transcript",
    "utc_run_id",
    "viewpoints",
    "write_full_batch_summary",
    "write_report_intent",
    "xhs_report",
]
