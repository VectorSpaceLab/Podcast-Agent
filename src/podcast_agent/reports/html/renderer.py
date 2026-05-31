"""HTML report rendering from generated Markdown reports."""

from __future__ import annotations

import shutil
from html import escape
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt

from podcast_agent.errors import ReportRenderError
from podcast_agent.reports.shared.fonts import DEFAULT_MONO_FONT_STACK, DEFAULT_SERIF_FONT_STACK, lxgw_wenkai_font_face


def render_html_report(
    *,
    output_dir: Path,
    markdown_path: Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Render reports/report.html from reports/report.md."""
    markdown_path = markdown_path or output_dir / "reports" / "report.md"
    report_dir = output_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    markdown = markdown_path.read_text(encoding="utf-8")
    title = _markdown_title(markdown)
    body = _render_markdown_body(markdown)
    body = _mark_source_info(body)

    cover_name = _copy_cover_image(report_dir=report_dir, metadata=metadata or {})
    if cover_name:
        body = _insert_cover_image(body=body, cover_name=cover_name, title=title)

    html_path = report_dir / "report.html"
    html_path.write_text(_html_document(title=title, body=body), encoding="utf-8")
    _make_browser_readable(report_dir, html_path, cover_name)
    return html_path


def render_pdf_report(
    *,
    output_dir: Path,
    html_path: Path | None = None,
) -> Path:
    """Render reports/report.pdf from reports/report.html using Playwright Chromium."""
    html_path = html_path or output_dir / "reports" / "report.html"
    if not html_path.is_file():
        raise ReportRenderError("PDF report rendering failed: reports/report.html is required.")

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment dependent.
        raise ReportRenderError("PDF report rendering failed: install optional dependencies with `pip install .[pdf]`.") from exc

    pdf_path = html_path.with_suffix(".pdf")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
            page.emulate_media(media="print")
            page.add_style_tag(content=_pdf_print_override_css())
            page.evaluate("async () => { await document.fonts.ready; }")
            page.pdf(
                path=str(pdf_path),
                format="A4",
                print_background=True,
                margin={"top": "14mm", "right": "14mm", "bottom": "16mm", "left": "14mm"},
                prefer_css_page_size=True,
            )
            browser.close()
    except PlaywrightError as exc:  # pragma: no cover - environment dependent.
        raise ReportRenderError(
            "PDF report rendering failed: Playwright Chromium is not ready. Run `playwright install chromium`."
        ) from exc

    pdf_path.chmod(0o644)
    return pdf_path


def _render_markdown_body(markdown: str) -> str:
    renderer = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True}).enable("table")
    return renderer.render(markdown)


def _markdown_title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or "Report"
    return "Report"


def _mark_source_info(body: str) -> str:
    for heading in ("来源信息", "Source Info"):
        body = body.replace(f"<h2>{heading}</h2>\n<ul>", f'<h2 class="source-heading">{heading}</h2>\n<ul class="source-list">')
    return body


def _copy_cover_image(*, report_dir: Path, metadata: dict[str, Any]) -> str | None:
    raw_path = str(metadata.get("thumbnail_path") or "").strip()
    if not raw_path:
        return None
    source = Path(raw_path).expanduser()
    if not source.is_file():
        return None
    suffix = source.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        return None
    cover_name = f"cover{suffix}"
    target = report_dir / cover_name
    if source.resolve() != target.resolve():
        shutil.copyfile(source, target)
    target.chmod(0o644)
    return cover_name


def _insert_cover_image(*, body: str, cover_name: str, title: str) -> str:
    marker = "</h1>"
    image_html = f'\n<img class="cover-image" src="{escape(cover_name, quote=True)}" alt="{escape(title, quote=True)}">'
    return body.replace(marker, marker + image_html, 1)


def _make_browser_readable(report_dir: Path, html_path: Path, cover_name: str | None) -> None:
    report_dir.chmod(0o755)
    html_path.chmod(0o644)
    if cover_name:
        cover_path = report_dir / cover_name
        if cover_path.is_file():
            cover_path.chmod(0o644)


def _html_document(*, title: str, body: str) -> str:
    return _render_template(
        _asset_text("templates/report.html"),
        {
            "title": escape(title),
            "css": _report_css(),
            "body": body,
        },
    )


def _report_css() -> str:
    return _render_template(
        _asset_text("assets/report.css"),
        {
            "font_face": lxgw_wenkai_font_face(display="swap"),
            "serif_font_stack": DEFAULT_SERIF_FONT_STACK,
            "mono_font_stack": DEFAULT_MONO_FONT_STACK,
        },
    )


def _asset_text(relative_path: str) -> str:
    return (Path(__file__).parent / relative_path).read_text(encoding="utf-8")


def _render_template(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"{{{{ {key} }}}}", value)
    return template


def _pdf_print_override_css() -> str:
    return f"""
    {lxgw_wenkai_font_face(display="swap")}
    @page {{
      size: A4;
      margin: 14mm 14mm 16mm;
    }}
    @media print {{
      body {{
        background: #fff !important;
        font-family: {DEFAULT_SERIF_FONT_STACK} !important;
      }}
      main {{
        width: auto !important;
        margin: 0 !important;
        padding: 0 !important;
        background: #fff !important;
        border: 0 !important;
        border-radius: 0 !important;
        box-shadow: none !important;
      }}
      h1, h2, h3 {{ break-after: auto; }}
      blockquote, .cover-image {{ break-inside: avoid; }}
      li {{ break-inside: auto; }}
      a {{ color: var(--accent); }}
    }}
    """
