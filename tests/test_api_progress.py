import threading
from pathlib import Path

from podcast_agent.api.progress import ProgressLog


def test_progress_log_appends_monotonic_seq(tmp_path: Path) -> None:
    progress = ProgressLog(tmp_path / "progress.jsonl", threading.Lock())

    first = progress.append("phase_started", "prepare", "任务准备中")
    second = progress.append("phase_started", "media_acquire", "正在获取视频内容")

    assert first["seq"] == 1
    assert second["seq"] == 2


def test_progress_log_reads_after_seq_with_limit(tmp_path: Path) -> None:
    progress = ProgressLog(tmp_path / "progress.jsonl", threading.Lock())
    progress.append("phase_started", "prepare", "任务准备中")
    progress.append("phase_started", "media_acquire", "正在获取视频内容")

    events = progress.read(after_seq=1, limit=1)

    assert [event["seq"] for event in events] == [2]


def test_progress_log_missing_file_returns_empty_list(tmp_path: Path) -> None:
    progress = ProgressLog(tmp_path / "progress.jsonl", threading.Lock())

    assert progress.read() == []

