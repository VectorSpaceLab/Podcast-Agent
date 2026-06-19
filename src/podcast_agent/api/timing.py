"""Timing estimates for VideoChat-compatible task progress."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol


class TimingTaskRecord(Protocol):
    status: str
    created_at: str
    updated_at: str


PHASE_ORDER = ["prepare", "media_acquire", "evidence_search", "report_write"]
DEFAULT_REMAINING_MS = {
    "prepare": (2_000, 4_000),
    "media_acquire": (40_000, 60_000),
    "evidence_search": (60_000, 120_000),
    "report_write": (120_000, 180_000),
}
REPORT_STAGE_DEFAULT_REMAINING_MS = {
    "outline": (30_000, 60_000),
    "viewpoint_detail": (60_000, 120_000),
    "summary": (50_000, 100_000),
    "render": (1_000, 5_000),
}
LOW_CONFIDENCE_OVERRUN_REMAINING_MAX_MS = 60_000


def build_task_timing(
    record: TimingTaskRecord,
    events: list[dict[str, object]] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    active_now = now or datetime.now(timezone.utc)
    all_events = events or []
    task_elapsed_ms = _elapsed_ms(_parse_ts(record.created_at), active_now)
    phase_timing = _build_phase_timing(all_events, active_now)
    task_remaining = _estimate_task_remaining(all_events, phase_timing, record.status)
    task_timing: dict[str, Any] = {
        "elapsed_ms": task_elapsed_ms,
        "confidence": task_remaining["confidence"],
    }
    if task_remaining["available"]:
        task_timing.update(
            {
                "remaining_min_ms": task_remaining["remaining_min_ms"],
                "remaining_max_ms": task_remaining["remaining_max_ms"],
                "estimated_total_min_ms": task_elapsed_ms + task_remaining["remaining_min_ms"],
                "estimated_total_max_ms": task_elapsed_ms + task_remaining["remaining_max_ms"],
            }
        )
        if task_remaining.get("overrun"):
            task_timing["overrun"] = True
    return {"task": task_timing, "phase": phase_timing}


def _build_phase_timing(events: list[dict[str, object]], now: datetime) -> dict[str, Any]:
    current_phase = _current_phase(events)
    if current_phase is None:
        return {"phase": "", "elapsed_ms": 0, "confidence": "unavailable"}

    latest_event = _latest_event_for_phase(events, current_phase) or {}
    latest_data = latest_event.get("data") if isinstance(latest_event.get("data"), dict) else {}
    stage = str(latest_data.get("stage", "") or "")
    started_at = (
        _latest_stage_started_at(events, current_phase, stage)
        or _latest_phase_started_at(events, current_phase)
        or _parse_ts(events[0].get("ts"))
        or now
    )
    elapsed_ms = _elapsed_ms(started_at, now)

    timing: dict[str, Any] = {"phase": current_phase, "elapsed_ms": elapsed_ms, "confidence": "low"}
    if stage:
        timing["stage"] = stage

    progress = _progress_from_data(latest_data)
    if progress is not None:
        if progress["completed"] > 0:
            remaining = _estimate_remaining_from_progress(
                elapsed_ms,
                progress["completed"],
                progress["total"],
                progress.get("workers", 1),
            )
            timing["confidence"] = "medium"
        else:
            remaining = _default_remaining_for_phase_stage(current_phase, stage, elapsed_ms)
        timing.update(remaining)
        timing["progress"] = progress
        return timing

    if current_phase == "report_write" and stage in REPORT_STAGE_DEFAULT_REMAINING_MS:
        min_ms, max_ms = REPORT_STAGE_DEFAULT_REMAINING_MS[stage]
        timing.update(_default_remaining_payload(min_ms, max_ms, elapsed_ms))
        return timing

    if current_phase in DEFAULT_REMAINING_MS:
        min_ms, max_ms = DEFAULT_REMAINING_MS[current_phase]
        timing.update(_default_remaining_payload(min_ms, max_ms, elapsed_ms))
    return timing


def _default_remaining_for_phase_stage(phase: str, stage: str, elapsed_ms: int) -> dict[str, int | bool]:
    if phase == "report_write" and stage in REPORT_STAGE_DEFAULT_REMAINING_MS:
        min_ms, max_ms = REPORT_STAGE_DEFAULT_REMAINING_MS[stage]
    elif phase in DEFAULT_REMAINING_MS:
        min_ms, max_ms = DEFAULT_REMAINING_MS[phase]
    else:
        min_ms, max_ms = 0, 0
    return _default_remaining_payload(min_ms, max_ms, elapsed_ms)


def _estimate_task_remaining(events: list[dict[str, object]], phase_timing: dict[str, Any], status: str) -> dict[str, Any]:
    if status == "completed":
        return _estimate_payload(0, 0, "high", available=True)
    if status == "failed":
        return _estimate_payload(0, 0, "unavailable", available=False)

    current_phase = str(phase_timing.get("phase", "") or "")
    if not current_phase:
        return _estimate_payload(0, 0, "unavailable", available=False)

    current_remaining_min = int(phase_timing.get("remaining_min_ms", 0) or 0)
    current_remaining_max = int(phase_timing.get("remaining_max_ms", 0) or 0)
    phase_index = PHASE_ORDER.index(current_phase) if current_phase in PHASE_ORDER else len(PHASE_ORDER) - 1
    future_min = 0
    future_max = 0
    for phase in PHASE_ORDER[phase_index + 1:]:
        if _phase_completed(events, phase):
            continue
        min_ms, max_ms = DEFAULT_REMAINING_MS[phase]
        future_min += min_ms
        future_max += max_ms

    confidence = str(phase_timing.get("confidence", "low") or "low")
    if future_min or future_max:
        confidence = "low"
    payload = _estimate_payload(
        current_remaining_min + future_min,
        current_remaining_max + future_max,
        confidence,
        available=True,
    )
    if phase_timing.get("overrun"):
        payload["overrun"] = True
    return payload


def _progress_from_data(data: dict[str, Any]) -> dict[str, int] | None:
    if "completed_chunks" in data and "chunk_count" in data:
        completed = _safe_int(data.get("completed_chunks"))
        total = _safe_int(data.get("chunk_count"))
    elif "completed_viewpoints" in data and "total_viewpoints" in data:
        completed = _safe_int(data.get("completed_viewpoints"))
        total = _safe_int(data.get("total_viewpoints"))
    else:
        return None
    if completed < 0 or total <= 0 or completed > total:
        return None
    progress = {"completed": completed, "total": total}
    workers = _safe_int(data.get("worker_count"))
    if workers > 0:
        progress["workers"] = min(workers, total)
    return progress


def _estimate_remaining_from_progress(elapsed_ms: int, completed: int, total: int, workers: int = 1) -> dict[str, int]:
    remaining_units = max(0, total - completed)
    if remaining_units == 0:
        return _remaining_payload(0, 0, elapsed_ms)
    active_workers = max(1, min(workers, total))
    completed_waves = max(1.0, completed / active_workers)
    remaining_waves = (remaining_units + active_workers - 1) // active_workers
    average_wave_ms = elapsed_ms / completed_waves
    remaining = int(average_wave_ms * remaining_waves)
    return _remaining_payload(int(remaining * 0.75), int(remaining * 1.5), elapsed_ms)


def _remaining_payload(remaining_min_ms: int, remaining_max_ms: int, elapsed_ms: int) -> dict[str, int]:
    min_ms = max(0, int(remaining_min_ms))
    max_ms = max(min_ms, int(remaining_max_ms))
    return {
        "remaining_min_ms": min_ms,
        "remaining_max_ms": max_ms,
        "estimated_total_min_ms": elapsed_ms + min_ms,
        "estimated_total_max_ms": elapsed_ms + max_ms,
    }


def _default_remaining_payload(default_min_ms: int, default_max_ms: int, elapsed_ms: int) -> dict[str, int | bool]:
    if elapsed_ms >= default_max_ms:
        payload = _remaining_payload(0, LOW_CONFIDENCE_OVERRUN_REMAINING_MAX_MS, elapsed_ms)
        payload["overrun"] = True
        return payload
    return _remaining_payload(max(0, default_min_ms - elapsed_ms), default_max_ms - elapsed_ms, elapsed_ms)


def _estimate_payload(remaining_min_ms: int, remaining_max_ms: int, confidence: str, *, available: bool) -> dict[str, Any]:
    return {
        "available": available,
        "remaining_min_ms": max(0, remaining_min_ms),
        "remaining_max_ms": max(0, remaining_max_ms),
        "confidence": confidence,
    }


def _current_phase(events: list[dict[str, object]]) -> str | None:
    for event in reversed(events):
        event_type = str(event.get("type", "") or "")
        phase = str(event.get("phase", "") or "")
        if event_type == "task_completed":
            return "completed"
        if event_type == "task_failed":
            return "failed"
        if phase:
            return phase
    return None


def _latest_phase_started_at(events: list[dict[str, object]], phase: str) -> datetime | None:
    for event in reversed(events):
        if event.get("type") == "phase_started" and event.get("phase") == phase:
            return _parse_ts(event.get("ts"))
    return None


def _latest_stage_started_at(events: list[dict[str, object]], phase: str, stage: str) -> datetime | None:
    if not stage:
        return None
    for event in reversed(events):
        if event.get("phase") != phase:
            continue
        data = event.get("data")
        if isinstance(data, dict) and data.get("stage") == stage and data.get("stage_status") == "started":
            return _parse_ts(event.get("ts"))
    return None


def _latest_event_for_phase(events: list[dict[str, object]], phase: str) -> dict[str, object] | None:
    for event in reversed(events):
        if event.get("phase") == phase:
            return event
    return None


def _phase_completed(events: list[dict[str, object]], phase: str) -> bool:
    return any(event.get("type") == "phase_completed" and event.get("phase") == phase for event in events)


def _parse_ts(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _elapsed_ms(started_at: datetime | None, now: datetime) -> int:
    if started_at is None:
        return 0
    return max(0, int((now.astimezone(timezone.utc) - started_at).total_seconds() * 1000))


def _safe_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
