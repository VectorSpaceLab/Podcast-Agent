"""HTML report rendering from generated Markdown reports."""

from __future__ import annotations

import shutil
from html import escape
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt


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
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f4ee;
      --paper: #fffdf8;
      --ink: #1e2930;
      --line: #ded8ce;
      --accent: #096f7a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Times New Roman", "SimSun", "宋体", "Songti SC", serif;
      font-size: 12pt;
      line-height: 1.72;
    }}
    main {{
      width: min(920px, calc(100vw - 32px));
      margin: 32px auto 56px;
      padding: 44px 56px;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 18px 48px rgba(38, 32, 24, 0.08);
    }}
    h1, h2, h3 {{
      line-height: 1.28;
      margin: 1.4em 0 0.65em;
      color: #14242a;
    }}
    h1 {{
      margin-top: 0;
      font-size: 16pt;
      letter-spacing: 0;
    }}
    h2 {{
      padding-top: 0.35em;
      border-top: 1px solid var(--line);
      font-size: 14pt;
    }}
    h3 {{ font-size: 12pt; }}
    .cover-image {{
      display: block;
      width: 100%;
      max-width: 760px;
      height: auto;
      margin: 0.9em auto 1.4em;
      border-radius: 6px;
    }}
    p {{ margin: 0.85em 0; }}
    ul {{ padding-left: 1.35em; }}
    li {{ margin: 0.65em 0; }}
    li > p {{ margin: 0.3em 0; }}
    blockquote {{
      margin: 0.8em 0 1.1em;
      padding: 0.8em 1em;
      color: #31484d;
      border-left: 4px solid var(--accent);
      border-radius: 0 6px 6px 0;
      font-size: 10.5pt;
      font-style: italic;
    }}
    a {{ color: var(--accent); text-decoration-thickness: 0.08em; text-underline-offset: 0.16em; }}
    strong {{ color: #102026; }}
    code {{
      padding: 0.12em 0.35em;
      border-radius: 4px;
      background: #ede8df;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.92em;
    }}
    hr {{ border: 0; border-top: 1px solid var(--line); margin: 2em 0; }}
    .source-heading,
    .source-list {{
      font-size: 10.5pt;
    }}
    @media (max-width: 720px) {{
      main {{
        width: 100%;
        margin: 0;
        padding: 28px 20px 40px;
        border-width: 0;
        border-radius: 0;
      }}
      h1 {{ font-size: 16pt; }}
    }}
  </style>
</head>
<body>
  <main>
{body}
  </main>
</body>
</html>
"""
