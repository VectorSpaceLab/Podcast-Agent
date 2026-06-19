from pathlib import Path

from podcast_agent.api.store import TaskRecord, TaskStore
from podcast_agent.api.timing import build_task_timing


def test_task_store_sync_success_writes_status_and_report(tmp_path: Path) -> None:
    def fake_runner(_url: str, _question: str, task_dir: Path) -> None:
        report_path = task_dir / "reports" / "report.md"
        report_path.parent.mkdir(parents=True)
        report_path.write_text("# Demo\n", encoding="utf-8")

    store = TaskStore(tmp_path, runner=fake_runner)

    record = store.run_task_sync(url="https://example.com", question="q")

    assert record.status == "completed"
    assert (record.task_dir / "status.json").is_file()
    assert store.read_report(record.task_id) == "# Demo\n"


def test_task_store_missing_report_fails(tmp_path: Path) -> None:
    store = TaskStore(tmp_path, runner=lambda _url, _question, _task_dir: None)

    record = store.run_task_sync(url="https://example.com", question="q")

    assert record.status == "failed"
    assert record.error_message == "report.md was not generated"


def test_task_store_lazy_loads_status(tmp_path: Path) -> None:
    def fake_runner(_url: str, _question: str, task_dir: Path) -> None:
        report_path = task_dir / "reports" / "report.md"
        report_path.parent.mkdir(parents=True)
        report_path.write_text("# Demo\n", encoding="utf-8")

    first_store = TaskStore(tmp_path, runner=fake_runner)
    record = first_store.run_task_sync(url="https://example.com", question="q")
    second_store = TaskStore(tmp_path, runner=fake_runner)

    loaded = second_store.get_or_load_task(record.task_id)

    assert loaded is not None
    assert loaded.status == "completed"
    assert second_store.read_report(record.task_id) == "# Demo\n"


def test_task_timing_completed_has_zero_remaining() -> None:
    record = TaskRecord(
        task_id="task",
        url="u",
        question="q",
        task_dir=Path("/tmp/task"),
        status="completed",
        created_at="2026-06-19T00:00:00+00:00",
    )

    timing = build_task_timing(record, [])

    assert timing["task"]["confidence"] == "high"
    assert timing["task"]["remaining_min_ms"] == 0

