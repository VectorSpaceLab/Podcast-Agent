"""Render Xiaohongshu note markdown into vertical PNG pages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from podcast_agent.errors import XhsReportError
from podcast_agent.reports.xhs.render.debug import write_pagination_debug
from podcast_agent.reports.xhs.render.html import (
    render_body_html,
    render_intro_html,
    render_measure_html,
)
from podcast_agent.reports.xhs.render.layout import (
    measure_xhs_blocks,
    page_height,
    safe_body_usable_height,
)
from podcast_agent.reports.xhs.render.pagination import paginate_measured_blocks
from podcast_agent.reports.xhs.parser import parse_xhs_note
from podcast_agent.reports.xhs.render.screenshot import clear_rendered_images, screenshot_html


@dataclass(frozen=True)
class XhsRenderResult:
    intro_path: Path
    page_paths: list[Path]


def render_xhs_images(
    *,
    note_path: Path,
    output_dir: Path,
    width: int = 1080,
    height: int = 1440,
    dpr: int = 2,
) -> XhsRenderResult:
    """Render reports/xhs/images/intro.png and body page images using Playwright."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment dependent.
        raise XhsReportError("XHS image rendering failed: install optional dependencies with `pip install .[xhs]`.") from exc

    note = parse_xhs_note(note_path)
    if not note["body_blocks"]:
        raise XhsReportError("XHS image rendering failed: note.md body is empty.")

    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    clear_rendered_images(images_dir)
    intro_path = images_dir / "intro.png"
    usable_height = safe_body_usable_height(height)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=dpr)
            measure_html = render_measure_html(blocks=note["body_blocks"], width=width, height=height)
            measured_blocks = measure_xhs_blocks(
                page=page,
                html=measure_html,
                blocks=note["body_blocks"],
                height=height,
            )
            measured_pages = paginate_measured_blocks(
                blocks=measured_blocks,
                usable_height=usable_height,
            )
            page_paths = [images_dir / f"page_{index}.png" for index in range(1, len(measured_pages) + 1)]
            write_pagination_debug(
                output_dir / "pagination_debug.json",
                width=width,
                height=height,
                usable_height=usable_height,
                pages=measured_pages,
            )
            screenshot_html(
                page=page,
                html=render_intro_html(note=note, width=width, height=height),
                path=intro_path,
            )
            for measured_page, page_path in zip(measured_pages, page_paths):
                screenshot_html(
                    page=page,
                    html=render_body_html(
                        note=note,
                        blocks=[measured.block for measured in measured_page],
                        width=width,
                        height=height,
                        content_height=page_height(measured_page),
                    ),
                    path=page_path,
                )
            browser.close()
    except PlaywrightError as exc:  # pragma: no cover - environment dependent.
        raise XhsReportError(
            "XHS image rendering failed: Playwright Chromium is not ready. Run `playwright install chromium`."
        ) from exc
    return XhsRenderResult(intro_path=intro_path, page_paths=page_paths)


__all__ = ["XhsRenderResult", "render_xhs_images"]
