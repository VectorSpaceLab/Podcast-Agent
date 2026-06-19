"""VideoChat-compatible progress JSONL helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Any


ProgressEvent = dict[str, object]

PROGRESS_PHASE_MESSAGES = {
    "prepare": "任务准备中",
    "media_acquire": "正在获取视频内容",
    "question_analysis": "正在分析问题",
    "evidence_search": "正在分析视频内容",
    "report_write": "正在生成报告",
    "completed": "报告生成完成",
    "failed": "任务失败",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProgressLog:
    def __init__(self, path: Path, lock: threading.Lock) -> None:
        self.path = Path(path)
        self._lock = lock

    def append(
        self,
        event_type: str,
        phase: str,
        message: str,
        *,
        data: dict[str, object] | None = None,
    ) -> ProgressEvent:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            event: ProgressEvent = {
                "seq": self._next_seq_unlocked(),
                "ts": utc_now(),
                "type": event_type,
                "phase": phase,
                "message": message,
                "data": data or {},
            }
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            return dict(event)

    def read(self, *, after_seq: int = 0, limit: int = 100) -> list[ProgressEvent]:
        if not self.path.exists():
            return []

        events: list[ProgressEvent] = []
        with self._lock:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                event = json.loads(line)
                if int(event.get("seq", 0)) > after_seq:
                    events.append(event)
                if len(events) >= limit:
                    break
        return events

    def _next_seq_unlocked(self) -> int:
        if not self.path.exists():
            return 1

        max_seq = 0
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                continue
            max_seq = max(max_seq, int(event.get("seq", 0)))
        return max_seq + 1

