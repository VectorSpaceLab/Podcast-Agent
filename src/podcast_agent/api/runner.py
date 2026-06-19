"""Podcast-Agent pipeline runner for API tasks."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Callable, Literal

from podcast_agent.api.logging import log_event
from podcast_agent.cli.audio import LazyDefaultAliyunTranscriber
from podcast_agent.insights.evidence import extract_evidence
from podcast_agent.insights.llm import build_default_model_writer
from podcast_agent.insights.outline import generate_outline
from podcast_agent.insights.summary import generate_summary
from podcast_agent.insights.viewpoint import generate_viewpoints
from podcast_agent.intent import resolve_report_intent, write_report_intent
from podcast_agent.pipeline.runner import run_pipeline
from podcast_agent.reports.html import render_pdf_report
from podcast_agent.reports.markdown import render_markdown_report
from podcast_agent.reports.xhs import compose_xhs_report, prepare_xhs_cover, render_xhs_images


ReportMode = Literal["markdown", "html", "pdf", "xhs", "all"]
ProgressSink = Callable[[dict[str, object]], None]


def run_api_pipeline(
    *,
    url: str,
    question: str,
    task_dir: Path,
    progress_sink: ProgressSink | None = None,
    report_mode: ReportMode = "markdown",
) -> None:
    """Run the Podcast-Agent pipeline and render requested reports."""
    _validate_report_mode(report_mode)
    log_path = task_dir / "pipeline.log"
    workflow_start = perf_counter()
    log_event(
        log_path,
        "workflow_start",
        url=url,
        workspace_dir=task_dir,
        report_dir=task_dir / "reports",
        report_mode=report_mode,
    )

    try:
        _run_api_pipeline(
            url=url,
            question=question,
            task_dir=task_dir,
            progress_sink=progress_sink,
            report_mode=report_mode,
            log_path=log_path,
        )
    except Exception as exc:
        log_event(log_path, "workflow_failed", error=exc, elapsed_ms=_elapsed_ms(workflow_start))
        raise

    log_event(log_path, "workflow_done", elapsed_ms=_elapsed_ms(workflow_start))


def _run_api_pipeline(
    *,
    url: str,
    question: str,
    task_dir: Path,
    progress_sink: ProgressSink | None,
    report_mode: ReportMode,
    log_path: Path,
) -> None:
    model_writer = build_default_model_writer()

    stage_start = perf_counter()
    _emit(progress_sink, "phase_started", "media_acquire", "正在获取视频内容")
    log_event(log_path, "acquire_subtitles_start", workspace_dir=task_dir)
    report_intent = resolve_report_intent(question=question, model_writer=model_writer)
    write_report_intent(path=task_dir / "insights" / "intent.json", question=question, intent=report_intent)
    log_event(
        log_path,
        "report_intent_done",
        report_language=report_intent.report_language,
        report_length=report_intent.report_length,
        source=report_intent.source,
    )
    run_pipeline(
        url=url,
        question=question,
        output_dir=task_dir,
        audio_transcriber=LazyDefaultAliyunTranscriber(),
    )
    log_event(log_path, "acquire_subtitles_done", elapsed_ms=_elapsed_ms(stage_start))
    _emit(progress_sink, "phase_completed", "media_acquire", "视频内容获取完成")

    stage_start = perf_counter()
    _emit(progress_sink, "phase_started", "evidence_search", "正在分析视频内容")
    log_event(log_path, "extract_evidence_start", evidence_path=task_dir / "insights" / "evidence.json")
    extract_evidence(output_dir=task_dir, model_writer=model_writer)
    log_event(log_path, "extract_evidence_done", evidence_path=task_dir / "insights" / "evidence.json", elapsed_ms=_elapsed_ms(stage_start))
    _emit(progress_sink, "phase_completed", "evidence_search", "视频内容分析完成")

    stage_start = perf_counter()
    _emit(progress_sink, "phase_started", "report_write", "正在生成报告")
    log_event(log_path, "write_report_start", evidence_path=task_dir / "insights" / "evidence.json")
    generate_outline(output_dir=task_dir, model_writer=model_writer, report_intent=report_intent)
    log_event(log_path, "report_outline_completed", stage="outline")
    generate_viewpoints(output_dir=task_dir, model_writer=model_writer, report_intent=report_intent)
    log_event(log_path, "report_viewpoints_completed", stage="viewpoint_detail")
    generate_summary(output_dir=task_dir, model_writer=model_writer, report_intent=report_intent)
    log_event(log_path, "report_summary_completed", stage="summary")
    report_path = render_markdown_report(output_dir=task_dir, report_intent=report_intent)
    log_event(log_path, "report_render_completed", stage="render", report_path=report_path)

    if report_mode in {"pdf", "all"}:
        pdf_path = render_pdf_report(output_dir=task_dir, html_path=report_path.with_suffix(".html"))
        log_event(log_path, "pdf_render_completed", report_path=pdf_path)
    if report_mode in {"xhs", "all"}:
        compose_result = compose_xhs_report(output_dir=task_dir, model_writer=model_writer)
        xhs_dir = task_dir / "reports" / "xhs"
        prepare_xhs_cover(output_dir=task_dir, xhs_dir=xhs_dir)
        xhs_render_result = render_xhs_images(note_path=compose_result.note_path, output_dir=xhs_dir)
        log_event(
            log_path,
            "xhs_render_completed",
            note_path=compose_result.note_path,
            post_meta_path=compose_result.post_meta_path,
            intro_path=xhs_render_result.intro_path,
            page_count=len(xhs_render_result.page_paths),
        )

    log_event(log_path, "write_report_done", report_path=report_path, elapsed_ms=_elapsed_ms(stage_start))
    _emit(progress_sink, "phase_completed", "report_write", "报告生成完成")


def _validate_report_mode(report_mode: str) -> None:
    if report_mode not in {"markdown", "html", "pdf", "xhs", "all"}:
        raise ValueError(f"Unsupported report mode: {report_mode}")


def _emit(
    progress_sink: ProgressSink | None,
    event_type: str,
    phase: str,
    message: str,
    *,
    data: dict[str, object] | None = None,
) -> None:
    if progress_sink is None:
        return
    progress_sink({"type": event_type, "phase": phase, "message": message, "data": data or {}})


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)
