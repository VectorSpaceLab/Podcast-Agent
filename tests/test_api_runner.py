from pathlib import Path

from podcast_agent.intent import ReportIntent


def test_api_runner_default_mode_renders_only_markdown(monkeypatch, tmp_path: Path) -> None:
    from podcast_agent.api import runner

    calls = []
    _patch_runner_dependencies(monkeypatch, runner, calls, tmp_path)

    runner.run_api_pipeline(url="https://example.com", question="q", task_dir=tmp_path)

    assert [call[0] for call in calls] == [
        "intent",
        "write_intent",
        "run_pipeline",
        "evidence",
        "outline",
        "viewpoints",
        "summary",
        "markdown",
    ]
    log_text = (tmp_path / "pipeline.log").read_text(encoding="utf-8")
    assert "workflow_start" in log_text
    assert "acquire_subtitles_start" in log_text
    assert "extract_evidence_done" in log_text
    assert "write_report_done" in log_text
    assert "workflow_done" in log_text


def test_api_runner_pdf_mode_invokes_pdf_renderer(monkeypatch, tmp_path: Path) -> None:
    from podcast_agent.api import runner

    calls = []
    _patch_runner_dependencies(monkeypatch, runner, calls, tmp_path)

    runner.run_api_pipeline(url="https://example.com", question="q", task_dir=tmp_path, report_mode="pdf")

    assert "pdf" in [call[0] for call in calls]


def test_api_runner_xhs_and_all_modes_invoke_optional_renderers(monkeypatch, tmp_path: Path) -> None:
    from podcast_agent.api import runner

    calls = []
    _patch_runner_dependencies(monkeypatch, runner, calls, tmp_path)
    runner.run_api_pipeline(url="https://example.com", question="q", task_dir=tmp_path, report_mode="xhs")
    xhs_call_names = [call[0] for call in calls]
    assert "xhs_compose" in xhs_call_names
    assert "xhs_cover" in xhs_call_names
    assert "xhs_render" in xhs_call_names
    assert "pdf" not in xhs_call_names

    calls.clear()
    runner.run_api_pipeline(url="https://example.com", question="q", task_dir=tmp_path, report_mode="all")
    all_call_names = [call[0] for call in calls]
    assert "pdf" in all_call_names
    assert "xhs_compose" in all_call_names
    assert "xhs_cover" in all_call_names
    assert "xhs_render" in all_call_names


def _patch_runner_dependencies(monkeypatch, runner, calls, output_dir: Path) -> None:
    monkeypatch.setattr(runner, "build_default_model_writer", lambda: (lambda prompt: f"model:{prompt}"))

    def fake_resolve_report_intent(*, question, model_writer):
        calls.append(("intent", question, model_writer("intent")))
        return ReportIntent(report_language="en", report_length="brief", source="model")

    def fake_write_report_intent(*, path, question, intent):
        calls.append(("write_intent", str(path), question, intent.report_language))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
        return path

    def fake_run_pipeline(*, url, question, output_dir, audio_transcriber=None):
        calls.append(("run_pipeline", url, question, output_dir, audio_transcriber))

    def fake_extract_evidence(*, output_dir, model_writer):
        calls.append(("evidence", output_dir, model_writer("evidence")))
        return {"segments": []}

    def fake_generate_outline(*, output_dir, model_writer, report_intent=None):
        calls.append(("outline", output_dir, model_writer("outline"), report_intent))
        return {"viewpoint_breakdown": []}

    def fake_generate_viewpoints(*, output_dir, model_writer, report_intent=None):
        calls.append(("viewpoints", output_dir, model_writer("viewpoints"), report_intent))
        return {"viewpoint_details": []}

    def fake_generate_summary(*, output_dir, model_writer, report_intent=None):
        calls.append(("summary", output_dir, model_writer("summary"), report_intent))
        return {"core_conclusions": []}

    def fake_render_markdown_report(*, output_dir, report_intent=None):
        calls.append(("markdown", output_dir, report_intent))
        report_path = output_dir / "reports" / "report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("# Demo\n", encoding="utf-8")
        report_path.with_suffix(".html").write_text("<html></html>\n", encoding="utf-8")
        return report_path

    def fake_render_pdf_report(*, output_dir, html_path=None):
        calls.append(("pdf", output_dir, html_path))
        return output_dir / "reports" / "report.pdf"

    class ComposeResult:
        note_path = output_dir / "reports" / "xhs" / "note.md"
        post_meta_path = output_dir / "reports" / "xhs" / "post_meta.json"

    def fake_compose_xhs_report(*, output_dir, model_writer):
        calls.append(("xhs_compose", output_dir, model_writer("xhs")))
        return ComposeResult()

    def fake_prepare_xhs_cover(*, output_dir, xhs_dir):
        calls.append(("xhs_cover", output_dir, xhs_dir))

    def fake_render_xhs_images(*, note_path, output_dir):
        calls.append(("xhs_render", note_path, output_dir))
        class RenderResult:
            intro_path = output_dir / "images" / "intro.png"
            page_paths = [output_dir / "images" / "page_1.png"]

        return RenderResult()

    monkeypatch.setattr(runner, "resolve_report_intent", fake_resolve_report_intent)
    monkeypatch.setattr(runner, "write_report_intent", fake_write_report_intent)
    monkeypatch.setattr(runner, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(runner, "extract_evidence", fake_extract_evidence)
    monkeypatch.setattr(runner, "generate_outline", fake_generate_outline)
    monkeypatch.setattr(runner, "generate_viewpoints", fake_generate_viewpoints)
    monkeypatch.setattr(runner, "generate_summary", fake_generate_summary)
    monkeypatch.setattr(runner, "render_markdown_report", fake_render_markdown_report)
    monkeypatch.setattr(runner, "render_pdf_report", fake_render_pdf_report)
    monkeypatch.setattr(runner, "compose_xhs_report", fake_compose_xhs_report)
    monkeypatch.setattr(runner, "prepare_xhs_cover", fake_prepare_xhs_cover)
    monkeypatch.setattr(runner, "render_xhs_images", fake_render_xhs_images)
