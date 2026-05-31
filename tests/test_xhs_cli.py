from pathlib import Path

from typer.testing import CliRunner

from podcast_agent.cli.main import app


def test_cli_xhs_report_skip_render_runs_compose_and_cover(tmp_path: Path) -> None:
    from podcast_agent.cli import reports as main

    runner = CliRunner()
    output_dir = tmp_path / "demo"
    calls = []

    class ComposeResult:
        note_path = output_dir / "reports" / "xhs" / "note.md"
        post_meta_path = output_dir / "reports" / "xhs" / "post_meta.json"

    def fake_compose_xhs_report(*, output_dir, model_writer, angle=None):
        calls.append(("compose", str(output_dir), model_writer("prompt"), angle))
        result = ComposeResult()
        result.note_path.parent.mkdir(parents=True, exist_ok=True)
        result.note_path.write_text("note\n", encoding="utf-8")
        result.post_meta_path.write_text("{}\n", encoding="utf-8")
        return result

    def fake_prepare_xhs_cover(*, output_dir, xhs_dir):
        calls.append(("cover", str(output_dir), str(xhs_dir)))
        return None

    original_compose = main.compose_xhs_report
    original_cover = main.prepare_xhs_cover
    original_render = main.render_xhs_images
    original_model_writer = main.build_default_model_writer
    main.compose_xhs_report = fake_compose_xhs_report
    main.prepare_xhs_cover = fake_prepare_xhs_cover
    main.render_xhs_images = lambda **kwargs: calls.append(("render", kwargs))
    main.build_default_model_writer = lambda: (lambda prompt: f"model:{prompt}")
    try:
        result = runner.invoke(
            app,
            [
                "xhs-report",
                "--output-dir",
                str(output_dir),
                "--angle",
                "关注商业判断",
                "--skip-render",
            ],
        )
    finally:
        main.compose_xhs_report = original_compose
        main.prepare_xhs_cover = original_cover
        main.render_xhs_images = original_render
        main.build_default_model_writer = original_model_writer

    assert result.exit_code == 0
    assert [call[0] for call in calls] == ["compose", "cover"]
    assert calls[0][3] == "关注商业判断"
    assert "Stage 1/3: composing xhs note" in result.output
    assert "Stage 3/3: rendering xhs images skipped" in result.output
    assert "Generated XHS note:" in result.output
