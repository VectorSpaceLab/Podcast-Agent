"""Task state store for the VideoChat-compatible API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
import shutil
import threading
import traceback
from typing import Callable
import uuid

from podcast_agent.api.adapters import find_report_path, load_source_metadata
from podcast_agent.api.progress import PROGRESS_PHASE_MESSAGES, ProgressLog
from podcast_agent.api.timing import build_task_timing


DEFAULT_TASK_ROOT = Path("output") / "api"
ProgressSink = Callable[[dict[str, object]], None]
TaskRunner = Callable[..., None]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_task_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


@dataclass
class TaskRecord:
    task_id: str
    url: str
    question: str
    task_dir: Path
    status: str = "queued"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    error_message: str = ""
    report_path: Path | None = None

    def to_dict(self, *, include_source_metadata: bool = True) -> dict[str, object]:
        report_path = self.report_path or find_report_path(self.task_dir)
        payload: dict[str, object] = {
            "task_id": self.task_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "report_available": report_path is not None and report_path.exists(),
            "report_path": str(report_path) if report_path else "",
            "error_message": self.error_message,
        }
        if include_source_metadata:
            payload["source_metadata"] = load_source_metadata(self.task_dir)
        return payload

    @classmethod
    def from_status_file(cls, task_dir: Path) -> "TaskRecord" | None:
        status_path = task_dir / "status.json"
        if not status_path.is_file():
            return None
        try:
            payload = json.loads(status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        task_id = str(payload.get("task_id") or task_dir.name)
        report_path_value = str(payload.get("report_path") or "").strip()
        return cls(
            task_id=task_id,
            url=str(payload.get("url") or ""),
            question=str(payload.get("question") or ""),
            task_dir=task_dir,
            status=str(payload.get("status") or "completed"),
            created_at=str(payload.get("created_at") or utc_now()),
            updated_at=str(payload.get("updated_at") or utc_now()),
            error_message=str(payload.get("error_message") or ""),
            report_path=Path(report_path_value) if report_path_value else find_report_path(task_dir),
        )


class TaskStore:
    def __init__(self, task_root: Path = DEFAULT_TASK_ROOT, runner: TaskRunner | None = None) -> None:
        self.task_root = Path(task_root)
        self.runner = runner or _default_runner
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = threading.Lock()
        self.task_root.mkdir(parents=True, exist_ok=True)

    def create_task(self, *, url: str, question: str) -> TaskRecord:
        record = self._create_queued_record(url=url, question=question)
        response_record = TaskRecord(task_id=record.task_id, url=record.url, question=record.question, task_dir=record.task_dir)
        self._save(record)
        self.append_progress(record.task_id, "phase_started", "prepare")
        thread = threading.Thread(target=self._run_task, args=(record.task_id,), daemon=True)
        thread.start()
        return response_record

    def run_task_sync(self, *, url: str, question: str) -> TaskRecord:
        record = self._create_queued_record(url=url, question=question)
        self._save(record)
        self.append_progress(record.task_id, "phase_started", "prepare")
        self._run_task(record.task_id)
        synced_record = self.get_task(record.task_id)
        if synced_record is None:
            raise RuntimeError(f"Task {record.task_id} disappeared during synchronous execution")
        return synced_record

    def _create_queued_record(self, *, url: str, question: str) -> TaskRecord:
        task_id = new_task_id()
        task_dir = self.task_root / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return TaskRecord(task_id=task_id, url=url, question=question, task_dir=task_dir)

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._tasks.get(task_id)

    def load_task(self, task_id: str) -> TaskRecord | None:
        task_dir = self.task_root / task_id
        record = TaskRecord.from_status_file(task_dir)
        if record is None:
            return None
        with self._lock:
            self._tasks[task_id] = record
        return record

    def get_or_load_task(self, task_id: str) -> TaskRecord | None:
        return self.get_task(task_id) or self.load_task(task_id)

    def delete_task(self, task_id: str) -> bool:
        record = self.get_or_load_task(task_id)
        if record is None:
            return False
        with self._lock:
            self._tasks.pop(task_id, None)
        shutil.rmtree(record.task_dir, ignore_errors=True)
        return True

    def read_report(self, task_id: str) -> str | None:
        record = self.get_or_load_task(task_id)
        if record is None:
            return None
        report_path = find_report_path(record.task_dir)
        if report_path is None:
            return None
        return report_path.read_text(encoding="utf-8")

    def append_progress(
        self,
        task_id: str,
        event_type: str,
        phase: str,
        message: str | None = None,
        *,
        data: dict[str, object] | None = None,
    ) -> dict[str, object] | None:
        record = self.get_or_load_task(task_id)
        if record is None:
            return None
        resolved_message = message or PROGRESS_PHASE_MESSAGES.get(phase, phase)
        return ProgressLog(record.task_dir / "progress.jsonl", self._lock).append(
            event_type,
            phase,
            resolved_message,
            data=data,
        )

    def read_progress(self, task_id: str, *, after_seq: int = 0, limit: int = 100) -> list[dict[str, object]] | None:
        record = self.get_or_load_task(task_id)
        if record is None:
            return None
        return ProgressLog(record.task_dir / "progress.jsonl", self._lock).read(after_seq=after_seq, limit=limit)

    def timing_snapshot(self, task_id: str) -> dict[str, object] | None:
        record = self.get_or_load_task(task_id)
        if record is None:
            return None
        events = ProgressLog(record.task_dir / "progress.jsonl", self._lock).read(after_seq=0, limit=10000)
        return build_task_timing(record, events)

    def _has_progress_event(self, task_id: str, *, event_type: str, phase: str) -> bool:
        events = self.read_progress(task_id, after_seq=0, limit=10000)
        if events is None:
            return False
        return any(event.get("type") == event_type and event.get("phase") == phase for event in events)

    def _run_task(self, task_id: str) -> None:
        record = self.get_task(task_id)
        if record is None:
            return

        self._update(task_id, status="running")
        try:
            self._call_runner(record)
            report_path = find_report_path(record.task_dir)
            if report_path is None:
                message = "report.md was not generated"
                self._update(task_id, status="failed", error_message=message)
                self.append_progress(task_id, "task_failed", "failed", data={"error_message": message})
            else:
                self._update(task_id, status="completed", report_path=report_path)
                if not self._has_progress_event(task_id, event_type="task_completed", phase="completed"):
                    self.append_progress(task_id, "task_completed", "completed")
        except Exception as exc:  # pragma: no cover - stored for API consumers
            record.task_dir.mkdir(parents=True, exist_ok=True)
            (record.task_dir / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
            self._update(task_id, status="failed", error_message=str(exc))
            self.append_progress(task_id, "task_failed", "failed", data={"error_message": str(exc)})

    def _call_runner(self, record: TaskRecord) -> None:
        def progress_sink(event: dict[str, object]) -> None:
            data = event.get("data")
            self.append_progress(
                record.task_id,
                str(event.get("type", "phase_progress")),
                str(event.get("phase", "prepare")),
                str(event.get("message", "")),
                data=data if isinstance(data, dict) else {},
            )

        if self._runner_accepts_progress_sink():
            self.runner(record.url, record.question, record.task_dir, progress_sink)
        else:
            self.runner(record.url, record.question, record.task_dir)

    def _runner_accepts_progress_sink(self) -> bool:
        try:
            signature = inspect.signature(self.runner)
        except (TypeError, ValueError):
            return True
        positional_count = 0
        for parameter in signature.parameters.values():
            if parameter.kind == inspect.Parameter.VAR_POSITIONAL:
                return True
            if parameter.kind in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}:
                positional_count += 1
        return positional_count >= 4

    def _save(self, record: TaskRecord) -> None:
        with self._lock:
            self._tasks[record.task_id] = record
        self._write_status(record)

    def _update(self, task_id: str, *, status: str, error_message: str = "", report_path: Path | None = None) -> None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return
            record.status = status
            record.updated_at = utc_now()
            record.error_message = error_message
            if report_path is not None:
                record.report_path = report_path
        self._write_status(record)

    def _write_status(self, record: TaskRecord) -> None:
        payload = {
            **record.to_dict(),
            "url": record.url,
            "question": record.question,
        }
        (record.task_dir / "status.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _default_runner(url: str, question: str, task_dir: Path, progress_sink: ProgressSink | None = None) -> None:
    from podcast_agent.api.runner import run_api_pipeline

    run_api_pipeline(url=url, question=question, task_dir=task_dir, progress_sink=progress_sink)
