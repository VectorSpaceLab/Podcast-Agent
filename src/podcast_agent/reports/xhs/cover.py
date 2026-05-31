"""Cover image preparation for Xiaohongshu reports."""

from __future__ import annotations

import shutil
from pathlib import Path

from podcast_agent.pipeline.artifacts import load_json


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def prepare_xhs_cover(*, output_dir: Path, xhs_dir: Path) -> Path | None:
    """Copy an existing local thumbnail-like image into reports/xhs/cover.png when available."""
    xhs_dir.mkdir(parents=True, exist_ok=True)
    source = _find_local_cover(output_dir)
    if source is None:
        return None
    destination = xhs_dir / "cover.png"
    shutil.copyfile(source, destination)
    return destination


def _find_local_cover(output_dir: Path) -> Path | None:
    reports_dir = output_dir / "reports"
    for path in sorted(reports_dir.glob("cover.*")):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            return path

    elements_dir = output_dir / "elements"
    for pattern in ("thumbnail.*", "*thumbnail*.*"):
        for path in sorted(elements_dir.glob(pattern)):
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                return path

    metadata_path = elements_dir / "metadata.json"
    if metadata_path.is_file():
        payload = load_json(metadata_path)
        if isinstance(payload, dict):
            for key in ("thumbnail_path", "local_thumbnail_path"):
                raw_path = str(payload.get(key) or "").strip()
                if not raw_path:
                    continue
                path = Path(raw_path)
                if not path.is_absolute():
                    path = output_dir / path
                if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                    return path
    return None
