"""Pipeline log writer for API task runs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def log_event(log_path: Path, event: str, **fields: object) -> None:
    """Append a human-readable event block to an API pipeline log."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(format_event(event, **fields))
        handle.write("\n")


def format_event(event: str, **fields: object) -> str:
    lines = [f"{_utc_now()} | {event}"]
    for key, value in fields.items():
        lines.append(f"  {key}: {_format_value(value)}")
    return "\n".join(lines)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_value(value: object) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
