from pathlib import Path

from podcast_agent.pipeline.context import PipelineContext


def test_pipeline_context_create_makes_output_directories(tmp_path: Path) -> None:
    output_dir = tmp_path / "demo"

    context = PipelineContext.create(
        url="https://www.youtube.com/watch?v=xxxx",
        question="这个视频讲了什么？",
        output_dir=output_dir,
    )

    assert context.output_dir == output_dir
    assert context.input_path == output_dir / "input.json"
    assert context.source_path == output_dir / "source.json"
    assert context.elements_dir.is_dir()
    assert context.insights_dir.is_dir()
    assert context.reports_dir.is_dir()
    assert context.run_id
