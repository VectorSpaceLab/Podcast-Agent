from typer.testing import CliRunner

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

    from podcast_agent.cli import main

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
    from podcast_agent.cli import main

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
        return report_path

    original_run = main.run_pipeline
    original_extract = main.extract_evidence
    original_outline = main.generate_outline
    original_viewpoints = main.generate_viewpoints
    original_summary = main.generate_summary
    original_report = main.render_markdown_report
    original_model_writer = main.build_default_model_writer
    original_resolve_intent = main.resolve_report_intent
    original_write_intent = main.write_report_intent
    main.run_pipeline = fake_run_pipeline
    main.extract_evidence = fake_extract_evidence
    main.generate_outline = fake_generate_outline
    main.generate_viewpoints = fake_generate_viewpoints
    main.generate_summary = fake_generate_summary
    main.render_markdown_report = fake_render_markdown_report
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
    ]
    assert calls[4][2].report_language == "en"
    assert calls[5][2].report_length == "brief"
    assert calls[6][2].report_language == "en"
    assert calls[7][2].report_length == "brief"
    assert "Stage 1/7: detecting report intent" in result.output
    assert "Detected report intent: en brief (model)" in result.output
    assert "Rendered report:" in result.output
    assert "Rendered HTML report:" in result.output
    assert (output_dir / "reports" / "report.md").is_file()


def test_cli_intent_writes_intent_json(tmp_path) -> None:
    from podcast_agent.cli import main

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


def test_cli_transcript_fetches_transcript(tmp_path) -> None:
    from podcast_agent.cli import main

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
    from podcast_agent.cli import main

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
    from podcast_agent.cli import main

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
    from podcast_agent.cli import main

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
    from podcast_agent.cli import main

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
    from podcast_agent.cli import main

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
    from podcast_agent.cli import main

    output_dir = tmp_path / "demo"
    runner = CliRunner()

    def fake_render_markdown_report(*, output_dir):
        report_path = output_dir / "reports" / "report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("# Demo\n", encoding="utf-8")
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


def test_cli_transcribe_audio_writes_transcripts(tmp_path) -> None:
    from podcast_agent.cli import main

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
