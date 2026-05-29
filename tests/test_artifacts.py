from pathlib import Path

from podcast_agent.pipeline.artifacts import load_json, save_json
from podcast_agent.types import PipelineInput


def test_save_json_supports_dataclass_and_chinese_text(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "input.json"

    save_json(
        path,
        PipelineInput(
            url="https://www.youtube.com/watch?v=xxxx",
            question="这个视频讲了什么？",
        ),
    )

    assert load_json(path) == {
        "url": "https://www.youtube.com/watch?v=xxxx",
        "question": "这个视频讲了什么？",
        "status": "initialized",
    }
    assert "这个视频讲了什么？" in path.read_text(encoding="utf-8")


def test_save_json_supports_path_values(tmp_path: Path) -> None:
    path = tmp_path / "artifact.json"

    save_json(path, {"output_dir": tmp_path})

    assert load_json(path) == {"output_dir": str(tmp_path)}
