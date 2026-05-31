"""Playwright screenshot helpers for Xiaohongshu images."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

__all__ = ["clear_rendered_images", "screenshot_html"]


def clear_rendered_images(images_dir: Path) -> None:
    """Remove stale rendered pages before writing a fresh XHS image set."""
    for path in [images_dir / "intro.png", *sorted(images_dir.glob("page_*.png"))]:
        if path.is_file():
            path.unlink()


def screenshot_html(*, page: Any, html: str, path: Path) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", delete=False) as file:
        file.write(html)
        temp_path = Path(file.name)
    try:
        page.goto(temp_path.as_uri())
        page.screenshot(path=str(path), full_page=False)
    finally:
        temp_path.unlink(missing_ok=True)
