from typer.testing import CliRunner

from podcast_agent.cli.commands import FullBatchCase, FullBatchCaseResult
from podcast_agent.cli.main import app
from podcast_agent.intent import ReportIntent
from podcast_agent.types import TranscriptInfo, TranscriptSegment
from podcast_agent.transcribers.types import TranscriptionResult
from tests.fakes import FakeMetadataDownloader, FakeTranscriptDownloader


def test_cli_run_initializes_pipeline(tmp_path) -> None:
    output_dir = tmp_path / "demo"
    runner = CliRunner()

    def fake_run_pipeline(url, question, output_dir):
        from podcast_agent.pipeline.runner import run_pipeline

        return run_pipeline(
            url=url,
            question=question,
            output_dir=output_dir,
            metadata_downloader=FakeMetadataDownloader(
                {
                    "id": "xxxx",
                    "title": "Example Video",
                    "uploader": "Example Channel",
                    "webpage_url": "https://www.youtube.com/watch?v=xxxx",
                }
            ),
            transcript_downloader=FakeTranscriptDownloader(),
        )

    from podcast_agent.cli import stages as main

    original = main.run_pipeline
    main.run_pipeline = fake_run_pipeline
    try:
        result = runner.invoke(
            app,
            [
                "run",
                "--url",
                "https://www.youtube.com/watch?v=xxxx",
                "--question",
                "这个视频讲了什么？",
                "--output-dir",
                str(output_dir),
            ],
        )
    finally:
        main.run_pipeline = original

    assert result.exit_code == 0
    assert "Initialized podcast-agent run" in result.output
    assert "Resolved source: youtube xxxx" in result.output
    assert "Fetched metadata: Example Video" in result.output
    assert "Fetched transcript: youtube_subtitle (2 segments)" in result.output
    assert (output_dir / "input.json").is_file()
    assert (output_dir / "source.json").is_file()
    assert (output_dir / "elements" / "metadata.json").is_file()
    assert (output_dir / "elements" / "transcript.vtt").is_file()
    assert (output_dir / "elements" / "transcript.txt").is_file()
    assert (output_dir / "elements" / "transcript_info.json").is_file()
    assert (output_dir / "elements").is_dir()
    assert (output_dir / "insights").is_dir()
    assert (output_dir / "reports").is_dir()


def test_cli_run_exits_for_unsupported_source(tmp_path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run",
            "--url",
            "https://example.com/video",
            "--question",
            "这个视频讲了什么？",
            "--output-dir",
            str(tmp_path / "demo"),
        ],
    )

    assert result.exit_code == 1
    assert "Unsupported source URL" in result.output


def test_cli_full_runs_all_stages_and_renders_report(tmp_path) -> None:
    from podcast_agent.cli import stages as main

    output_dir = tmp_path / "full-demo"
    runner = CliRunner()
    calls = []

    def fake_run_pipeline(url, question, output_dir, audio_transcriber=None):
        calls.append(("run_pipeline", url, question, audio_transcriber))
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "input.json").write_text('{"url": "u", "question": "q"}\n', encoding="utf-8")
        elements_dir = output_dir / "elements"
        elements_dir.mkdir(parents=True, exist_ok=True)
        (elements_dir / "transcript_info.json").write_text(
            '{"acquisition_method": "youtube_subtitle", "segment_count": 2}\n',
            encoding="utf-8",
        )

        class Context:
            pass

        context = Context()
        context.elements_dir = elements_dir
        return context

    def fake_extract_evidence(*, output_dir, model_writer):
        calls.append(("evidence", model_writer("evidence")))
        return {"segments": [{"index": 1}]}

    def fake_resolve_report_intent(*, question, model_writer):
        calls.append(("intent", question, model_writer("intent")))
        return ReportIntent(report_language="en", report_length="brief", source="model")

    def fake_write_report_intent(*, path, question, intent):
        calls.append(("write_intent", str(path), intent.report_language, intent.report_length))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"report_language": "en", "report_length": "brief"}\n', encoding="utf-8")
        return path

    def fake_generate_outline(*, output_dir, model_writer, report_intent=None):
        calls.append(("outline", model_writer("outline"), report_intent))
        return {"viewpoint_breakdown": [{"id": "V1"}]}

    def fake_generate_viewpoints(*, output_dir, model_writer, report_intent=None):
        calls.append(("viewpoints", model_writer("viewpoints"), report_intent))
        return {"viewpoint_details": [{"viewpoint_id": "V1"}]}

    def fake_generate_summary(*, output_dir, model_writer, report_intent=None):
        calls.append(("summary", model_writer("summary"), report_intent))
        return {"core_conclusions": [{"id": "C1"}]}

    def fake_render_markdown_report(*, output_dir, report_intent=None):
        calls.append(("report", str(output_dir), report_intent))
        report_path = output_dir / "reports" / "report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("# Demo\n", encoding="utf-8")
        report_path.with_suffix(".html").write_text("<!doctype html><html></html>\n", encoding="utf-8")
        return report_path

    def fake_render_pdf_report(*, output_dir, html_path=None):
        calls.append(("pdf", str(output_dir), str(html_path)))
        pdf_path = output_dir / "reports" / "report.pdf"
        pdf_path.write_bytes(b"%PDF")
        return pdf_path

    class ComposeResult:
        note_path = output_dir / "reports" / "xhs" / "note.md"
        post_meta_path = output_dir / "reports" / "xhs" / "post_meta.json"

    def fake_compose_xhs_report(*, output_dir, model_writer, angle=None):
        calls.append(("xhs_compose", str(output_dir), model_writer("xhs"), angle))
        result = ComposeResult()
        result.note_path.parent.mkdir(parents=True, exist_ok=True)
        result.note_path.write_text("note\n", encoding="utf-8")
        result.post_meta_path.write_text("{}\n", encoding="utf-8")
        return result

    def fake_prepare_xhs_cover(*, output_dir, xhs_dir):
        calls.append(("xhs_cover", str(output_dir), str(xhs_dir)))

    class XhsRenderResult:
        intro_path = output_dir / "reports" / "xhs" / "images" / "intro.png"
        page_paths = [output_dir / "reports" / "xhs" / "images" / "page_1.png"]

    def fake_render_xhs_images(*, note_path, output_dir, width=1080, height=1440, dpr=2):
        calls.append(("xhs_render", str(note_path), str(output_dir), width, height, dpr))
        result = XhsRenderResult()
        result.intro_path.parent.mkdir(parents=True, exist_ok=True)
        result.intro_path.write_bytes(b"png")
        result.page_paths[0].write_bytes(b"png")
        return result

    original_run = main.run_pipeline
    original_extract = main.extract_evidence
    original_outline = main.generate_outline
    original_viewpoints = main.generate_viewpoints
    original_summary = main.generate_summary
    original_report = main.render_markdown_report
    original_pdf = main.render_pdf_report
    original_compose = main.compose_xhs_report
    original_cover = main.prepare_xhs_cover
    original_render_xhs = main.render_xhs_images
    original_model_writer = main.build_default_model_writer
    original_resolve_intent = main.resolve_report_intent
    original_write_intent = main.write_report_intent
    main.run_pipeline = fake_run_pipeline
    main.extract_evidence = fake_extract_evidence
    main.generate_outline = fake_generate_outline
    main.generate_viewpoints = fake_generate_viewpoints
    main.generate_summary = fake_generate_summary
    main.render_markdown_report = fake_render_markdown_report
    main.render_pdf_report = fake_render_pdf_report
    main.compose_xhs_report = fake_compose_xhs_report
    main.prepare_xhs_cover = fake_prepare_xhs_cover
    main.render_xhs_images = fake_render_xhs_images
    main.build_default_model_writer = lambda: (lambda prompt: f"model:{prompt}")
    main.resolve_report_intent = fake_resolve_report_intent
    main.write_report_intent = fake_write_report_intent
    try:
        result = runner.invoke(
            app,
            [
                "full",
                "--url",
                "https://www.youtube.com/watch?v=xxxx",
                "--question",
                "这个视频讲了什么？",
                "--output-dir",
                str(output_dir),
            ],
        )
    finally:
        main.run_pipeline = original_run
        main.extract_evidence = original_extract
        main.generate_outline = original_outline
        main.generate_viewpoints = original_viewpoints
        main.generate_summary = original_summary
        main.render_markdown_report = original_report
        main.render_pdf_report = original_pdf
        main.compose_xhs_report = original_compose
        main.prepare_xhs_cover = original_cover
        main.render_xhs_images = original_render_xhs
        main.build_default_model_writer = original_model_writer
        main.resolve_report_intent = original_resolve_intent
        main.write_report_intent = original_write_intent

    assert result.exit_code == 0
    assert [call[0] for call in calls] == [
        "intent",
        "write_intent",
        "run_pipeline",
        "evidence",
        "outline",
        "viewpoints",
        "summary",
        "report",
        "pdf",
        "xhs_compose",
        "xhs_cover",
        "xhs_render",
    ]
    assert calls[4][2].report_language == "en"
    assert calls[5][2].report_length == "brief"
    assert calls[6][2].report_language == "en"
    assert calls[7][2].report_length == "brief"
    assert "Stage 1/11: detecting report intent" in result.output
    assert "Stage 8/11: rendering PDF report" in result.output
    assert "Stage 11/11: rendering xhs images" in result.output
    assert "Detected report intent: en brief (model)" in result.output
    assert "Rendered report:" in result.output
    assert "Rendered HTML report:" in result.output
    assert "Rendered PDF report:" in result.output
    assert "Generated XHS note:" in result.output
    assert "Rendered XHS images:" in result.output
    assert (output_dir / "reports" / "report.md").is_file()
    assert (output_dir / "reports" / "report.html").is_file()
    assert (output_dir / "reports" / "report.pdf").is_file()
    assert (output_dir / "reports" / "xhs" / "images" / "intro.png").is_file()


def test_cli_intent_writes_intent_json(tmp_path) -> None:
    from podcast_agent.cli import stages as main

    output_dir = tmp_path / "intent-demo"
    runner = CliRunner()

    original_model_writer = main.build_default_model_writer
    main.build_default_model_writer = lambda: (lambda _prompt: '{"language": "en", "length": "brief"}')
    try:
        result = runner.invoke(
            app,
            [
                "intent",
                "--question",
                "Please summarize this briefly in English.",
                "--output-dir",
                str(output_dir),
            ],
        )
    finally:
        main.build_default_model_writer = original_model_writer

    assert result.exit_code == 0
    assert "Detected report intent: en brief (model)" in result.output
    assert (output_dir / "insights" / "intent.json").is_file()


def test_cli_full_batch_dry_run_filters_cases(tmp_path) -> None:
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        """{"id": "old", "url": "https://www.youtube.com/watch?v=old", "question": "旧问题？", "enabled": true, "tags": ["legacy"]}
{"id": "skip", "url": "https://www.youtube.com/watch?v=skip", "question": "跳过？", "enabled": false, "tags": ["new"]}
{"id": "new", "url": "https://www.youtube.com/watch?v=new", "question": "新问题？", "enabled": true, "tags": ["new", "pdf"], "notes": "extra fields are ignored"}
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "full-batch",
            "--cases",
            str(cases_path),
            "--tag",
            "new",
            "--run-id",
            "rid",
            "--output-root",
            str(tmp_path / "out"),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "Dry run: 1 cases selected." in result.output
    assert "new\thttps://www.youtube.com/watch?v=new" in result.output
    assert "old\thttps://www.youtube.com/watch?v=old" not in result.output
    assert "skip\thttps://www.youtube.com/watch?v=skip" not in result.output
    assert not (tmp_path / "out" / "batch-rid" / "logs" / "summary.json").exists()


def test_cli_full_batch_keeps_legacy_json_cases_support(tmp_path) -> None:
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        """{
  "version": 1,
  "default_question": "默认问题？",
  "cases": [
    {"id": "legacy", "url": "https://www.youtube.com/watch?v=legacy", "tags": ["old"]}
  ]
}
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["full-batch", "--cases", str(cases_path), "--dry-run"])

    assert result.exit_code == 0
    assert "legacy\thttps://www.youtube.com/watch?v=legacy" in result.output


def test_cli_full_batch_runs_selected_cases_and_writes_summary(tmp_path) -> None:
    from podcast_agent.cli import batch as main

    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        """{"id": "a", "url": "https://www.youtube.com/watch?v=a", "question": "问题 A？", "tags": ["new"]}
{"id": "b", "url": "https://www.youtube.com/watch?v=b", "question": "问题 B？", "tags": ["legacy"]}
""",
        encoding="utf-8",
    )
    calls = []

    def fake_run_full_batch_case(*, case, output_dir, log_path):
        calls.append((case.id, case.question, output_dir, log_path))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok\n", encoding="utf-8")
        output_dir.mkdir(parents=True, exist_ok=True)
        return FullBatchCaseResult(case=case, output_dir=output_dir, log_path=log_path, exit_code=0)

    original = main.run_full_batch_case
    main.run_full_batch_case = fake_run_full_batch_case
    try:
        result = CliRunner().invoke(
            app,
            [
                "full-batch",
                "--cases",
                str(cases_path),
                "--case",
                "a",
                "--run-id",
                "rid",
                "--output-root",
                str(tmp_path / "out"),
                "--max-jobs",
                "1",
            ],
        )
    finally:
        main.run_full_batch_case = original

    summary_path = tmp_path / "out" / "batch-rid" / "logs" / "summary.json"
    assert result.exit_code == 0
    assert calls[0][0] == "a"
    assert calls[0][1] == "问题 A？"
    assert "OK   a" in result.output
    assert summary_path.is_file()
    assert '"success_count": 1' in summary_path.read_text(encoding="utf-8")


def test_cli_full_batch_exits_nonzero_for_failed_case(tmp_path) -> None:
    from podcast_agent.cli import batch as main

    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        """{"id": "a", "url": "https://www.youtube.com/watch?v=a", "question": "默认问题？"}
""",
        encoding="utf-8",
    )

    def fake_run_full_batch_case(*, case, output_dir, log_path):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("failed\n", encoding="utf-8")
        return FullBatchCaseResult(case=case, output_dir=output_dir, log_path=log_path, exit_code=7)

    original = main.run_full_batch_case
    main.run_full_batch_case = fake_run_full_batch_case
    try:
        result = CliRunner().invoke(
            app,
            [
                "full-batch",
                "--cases",
                str(cases_path),
                "--run-id",
                "rid",
                "--output-root",
                str(tmp_path / "out"),
            ],
        )
    finally:
        main.run_full_batch_case = original

    assert result.exit_code == 1
    assert "FAIL a" in result.output
    summary = (tmp_path / "out" / "batch-rid" / "logs" / "summary.json").read_text(encoding="utf-8")
    assert '"failure_count": 1' in summary


def test_cli_full_batch_rejects_duplicate_case_ids(tmp_path) -> None:
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        """{"id": "a", "url": "https://www.youtube.com/watch?v=a", "question": "问题？"}
{"id": "a", "url": "https://www.youtube.com/watch?v=b", "question": "问题？"}
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["full-batch", "--cases", str(cases_path), "--dry-run"])

    assert result.exit_code == 1
    assert "cases[].id must be unique" in result.output


def test_cli_transcript_fetches_transcript(tmp_path) -> None:
    from podcast_agent.cli import audio as main

    output_dir = tmp_path / "transcript"
    runner = CliRunner()

    class FakeFetcher:
        def __init__(self, *, elements_dir, cookies_file=None, transcriber=None):
            self.elements_dir = elements_dir

        def fetch(self, source):
            self.elements_dir.mkdir(parents=True, exist_ok=True)
            (self.elements_dir / "transcript.vtt").write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhi\n", encoding="utf-8")
            (self.elements_dir / "transcript.txt").write_text("hi\n", encoding="utf-8")
            return TranscriptInfo(
                source_type="youtube",
                source_id=source.source_id,
                source_url=source.url,
                transcript_path="elements/transcript.vtt",
                text_path="elements/transcript.txt",
                transcript_format="vtt",
                language="en",
                acquisition_method="youtube_subtitle",
                subtitle_source="youtube_captions",
                subtitle_kind="manual",
                subtitle_track_id="en",
                source_format="vtt",
                downloaded_subtitle_path=None,
                audio_fallback_used=False,
                audio_info_path=None,
                transcription_provider=None,
                segment_count=1,
            )

    original = main.YoutubeTranscriptFetcher
    main.YoutubeTranscriptFetcher = FakeFetcher
    try:
        result = runner.invoke(
            app,
            [
                "transcript",
                "--url",
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "--output-dir",
                str(output_dir),
            ],
        )
    finally:
        main.YoutubeTranscriptFetcher = original

    assert result.exit_code == 0
    assert "Fetched transcript: youtube_subtitle (1 segments)" in result.output
    assert (output_dir / "elements" / "transcript.vtt").is_file()
    assert (output_dir / "elements" / "transcript.txt").is_file()


def test_cli_evidence_extracts_evidence(tmp_path) -> None:
    from podcast_agent.cli import stages as main

    output_dir = tmp_path / "demo"
    (output_dir / "elements").mkdir(parents=True)
    (output_dir / "input.json").write_text(
        '{"url": "https://www.youtube.com/watch?v=xxxx", "question": "q", "status": "initialized"}\n',
        encoding="utf-8",
    )
    (output_dir / "elements" / "transcript.vtt").write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhi\n",
        encoding="utf-8",
    )
    runner = CliRunner()

    def fake_extract_evidence(*, output_dir, model_writer):
        evidence_path = output_dir / "insights" / "evidence.json"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            '{"question": "q", "subtitle_path": "elements/transcript.vtt", "segments": []}\n',
            encoding="utf-8",
        )
        return {"question": "q", "subtitle_path": "elements/transcript.vtt", "segments": []}

    original_extract = main.extract_evidence
    original_model_writer = main.build_default_model_writer
    main.extract_evidence = fake_extract_evidence
    main.build_default_model_writer = lambda: (lambda prompt: '{"segments": []}')
    try:
        result = runner.invoke(
            app,
            [
                "evidence",
                "--output-dir",
                str(output_dir),
            ],
        )
    finally:
        main.extract_evidence = original_extract
        main.build_default_model_writer = original_model_writer

    assert result.exit_code == 0
    assert "Extracted evidence: 0 segments" in result.output
    assert (output_dir / "insights" / "evidence.json").is_file()


def test_cli_evidence_generates_upstream_artifacts_when_missing(tmp_path) -> None:
    from podcast_agent.cli import stages as main

    output_dir = tmp_path / "demo"
    runner = CliRunner()
    calls = []

    def fake_run_pipeline(url, question, output_dir, audio_transcriber=None):
        calls.append((url, question, output_dir, audio_transcriber))
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "input.json").write_text(
            '{"url": "https://www.youtube.com/watch?v=xxxx", "question": "q", "status": "initialized"}\n',
            encoding="utf-8",
        )
        elements_dir = output_dir / "elements"
        elements_dir.mkdir(parents=True, exist_ok=True)
        (elements_dir / "transcript.vtt").write_text(
            "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhi\n",
            encoding="utf-8",
        )

    def fake_extract_evidence(*, output_dir, model_writer):
        return {"question": "q", "subtitle_path": "elements/transcript.vtt", "segments": [{"index": 1}]}

    original_run = main.run_pipeline
    original_extract = main.extract_evidence
    original_model_writer = main.build_default_model_writer
    main.run_pipeline = fake_run_pipeline
    main.extract_evidence = fake_extract_evidence
    main.build_default_model_writer = lambda: (lambda prompt: '{"segments": []}')
    try:
        result = runner.invoke(
            app,
            [
                "evidence",
                "--url",
                "https://www.youtube.com/watch?v=xxxx",
                "--question",
                "q",
                "--output-dir",
                str(output_dir),
            ],
        )
    finally:
        main.run_pipeline = original_run
        main.extract_evidence = original_extract
        main.build_default_model_writer = original_model_writer

    assert result.exit_code == 0
    assert calls
    assert calls[0][0] == "https://www.youtube.com/watch?v=xxxx"
    assert calls[0][1] == "q"
    assert "Extracted evidence: 1 segments" in result.output


def test_cli_evidence_requires_upstream_artifacts_or_url_and_question(tmp_path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "evidence",
            "--output-dir",
            str(tmp_path / "missing"),
        ],
    )

    assert result.exit_code == 1
    assert "Provide --url and --question" in result.output


def test_cli_outline_generates_outline(tmp_path) -> None:
    from podcast_agent.cli import stages as main

    output_dir = tmp_path / "demo"
    runner = CliRunner()

    def fake_generate_outline(*, output_dir, model_writer):
        outline_path = output_dir / "insights" / "outline.json"
        outline_path.parent.mkdir(parents=True, exist_ok=True)
        outline_path.write_text('{"viewpoint_breakdown": [{"id": "V1"}]}\n', encoding="utf-8")
        return {"viewpoint_breakdown": [{"id": "V1"}]}

    original_outline = main.generate_outline
    original_model_writer = main.build_default_model_writer
    main.generate_outline = fake_generate_outline
    main.build_default_model_writer = lambda: (lambda prompt: '{"viewpoint_breakdown": []}')
    try:
        result = runner.invoke(
            app,
            [
                "outline",
                "--output-dir",
                str(output_dir),
            ],
        )
    finally:
        main.generate_outline = original_outline
        main.build_default_model_writer = original_model_writer

    assert result.exit_code == 0
    assert "Generated outline: 1 viewpoints" in result.output
    assert (output_dir / "insights" / "outline.json").is_file()


def test_cli_viewpoints_generates_viewpoints(tmp_path) -> None:
    from podcast_agent.cli import stages as main

    output_dir = tmp_path / "demo"
    runner = CliRunner()

    def fake_generate_viewpoints(*, output_dir, model_writer):
        viewpoints_path = output_dir / "insights" / "viewpoints.json"
        viewpoints_path.parent.mkdir(parents=True, exist_ok=True)
        viewpoints_path.write_text('{"report_type": "viewpoints", "viewpoint_details": [{"viewpoint_id": "V1"}]}\n', encoding="utf-8")
        return {"report_type": "viewpoints", "viewpoint_details": [{"viewpoint_id": "V1"}]}

    original_viewpoints = main.generate_viewpoints
    original_model_writer = main.build_default_model_writer
    main.generate_viewpoints = fake_generate_viewpoints
    main.build_default_model_writer = lambda: (lambda prompt: "{}")
    try:
        result = runner.invoke(
            app,
            [
                "viewpoints",
                "--output-dir",
                str(output_dir),
            ],
        )
    finally:
        main.generate_viewpoints = original_viewpoints
        main.build_default_model_writer = original_model_writer

    assert result.exit_code == 0
    assert "Generated viewpoints: 1 details" in result.output
    assert (output_dir / "insights" / "viewpoints.json").is_file()


def test_cli_summary_generates_summary(tmp_path) -> None:
    from podcast_agent.cli import stages as main

    output_dir = tmp_path / "demo"
    runner = CliRunner()

    def fake_generate_summary(*, output_dir, model_writer):
        summary_path = output_dir / "insights" / "summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text('{"report_type": "summary", "core_conclusions": [{"id": "C1"}]}\n', encoding="utf-8")
        return {"report_type": "summary", "core_conclusions": [{"id": "C1"}]}

    original_summary = main.generate_summary
    original_model_writer = main.build_default_model_writer
    main.generate_summary = fake_generate_summary
    main.build_default_model_writer = lambda: (lambda prompt: "{}")
    try:
        result = runner.invoke(
            app,
            [
                "summary",
                "--output-dir",
                str(output_dir),
            ],
        )
    finally:
        main.generate_summary = original_summary
        main.build_default_model_writer = original_model_writer

    assert result.exit_code == 0
    assert "Generated summary: 1 conclusions" in result.output
    assert (output_dir / "insights" / "summary.json").is_file()


def test_cli_report_renders_markdown(tmp_path) -> None:
    from podcast_agent.cli import reports as main

    output_dir = tmp_path / "demo"
    runner = CliRunner()

    def fake_render_markdown_report(*, output_dir):
        report_path = output_dir / "reports" / "report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("# Demo\n", encoding="utf-8")
        report_path.with_suffix(".html").write_text("<!doctype html><html><body>Demo</body></html>\n", encoding="utf-8")
        return report_path

    original_report = main.render_markdown_report
    main.render_markdown_report = fake_render_markdown_report
    try:
        result = runner.invoke(
            app,
            [
                "report",
                "--output-dir",
                str(output_dir),
            ],
        )
    finally:
        main.render_markdown_report = original_report

    assert result.exit_code == 0
    assert "Rendered report:" in result.output
    assert "Rendered HTML report:" in result.output
    assert (output_dir / "reports" / "report.md").is_file()
    assert (output_dir / "reports" / "report.html").is_file()


def test_cli_report_pdf_renders_existing_html(tmp_path) -> None:
    from podcast_agent.cli import reports as main

    output_dir = tmp_path / "demo"
    runner = CliRunner()
    calls = []

    def fake_render_pdf_report(*, output_dir):
        calls.append(str(output_dir))
        pdf_path = output_dir / "reports" / "report.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"%PDF")
        return pdf_path

    original_pdf = main.render_pdf_report
    main.render_pdf_report = fake_render_pdf_report
    try:
        result = runner.invoke(
            app,
            [
                "report-pdf",
                "--output-dir",
                str(output_dir),
            ],
        )
    finally:
        main.render_pdf_report = original_pdf

    assert result.exit_code == 0
    assert calls == [str(output_dir)]
    assert "Rendered PDF report:" in result.output
    assert (output_dir / "reports" / "report.pdf").is_file()


def test_cli_transcribe_audio_writes_transcripts(tmp_path) -> None:
    from podcast_agent.cli import audio as main

    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"audio")
    output_dir = tmp_path / "audio-output"
    runner = CliRunner()

    class FakeTranscriber:
        def transcribe(self, request):
            return TranscriptionResult(
                provider="fake",
                segments=[
                    TranscriptSegment(start=0.0, end=1.0, text="第一句。"),
                    TranscriptSegment(start=1.0, end=2.0, text="第二句。"),
                ],
            )

    original = main.build_default_aliyun_transcriber
    main.build_default_aliyun_transcriber = lambda: FakeTranscriber()
    try:
        result = runner.invoke(
            app,
            [
                "transcribe-audio",
                "--audio-path",
                str(audio_path),
                "--output-dir",
                str(output_dir),
                "--language",
                "zh",
            ],
        )
    finally:
        main.build_default_aliyun_transcriber = original

    assert result.exit_code == 0
    assert "Transcribed audio: fake (2 segments)" in result.output
    assert (output_dir / "elements" / "transcript.vtt").is_file()
    assert (output_dir / "elements" / "transcript.txt").read_text(encoding="utf-8") == "第一句。\n第二句。\n"
