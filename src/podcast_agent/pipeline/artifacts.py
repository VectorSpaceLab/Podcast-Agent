"""JSON artifact persistence helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def to_jsonable(data: Any) -> Any:
    if is_dataclass(data) and not isinstance(data, type):
        return to_jsonable(asdict(data))
    if isinstance(data, Path):
        return str(data)
    if isinstance(data, dict):
        return {str(key): to_jsonable(value) for key, value in data.items()}
    if isinstance(data, (list, tuple)):
        return [to_jsonable(item) for item in data]
    return data


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_jsonable(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
