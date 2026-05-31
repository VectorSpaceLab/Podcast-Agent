"""Render Xiaohongshu note markdown into vertical PNG pages."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
import math
from pathlib import Path
import re
import tempfile
from typing import Any

from podcast_agent.errors import XhsReportError
from podcast_agent.reports.shared.fonts import DEFAULT_SERIF_FONT_STACK, lxgw_wenkai_font_face


@dataclass(frozen=True)
class XhsRenderResult:
    intro_path: Path
    page_paths: list[Path]


@dataclass(frozen=True)
class XhsMeasuredBlock:
    id: str
    kind: str
    text: str
    block: dict[str, str]
    outer_height: float
    warning: str | None = None
    split_from: str | None = None
    split_part: int | None = None
    continuation: bool = False


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

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=dpr)
            measured_blocks = measure_xhs_blocks(
                page=page,
                blocks=note["body_blocks"],
                width=width,
                height=height,
            )
            measured_pages = paginate_measured_blocks(
                blocks=measured_blocks,
                usable_height=safe_body_usable_height(height),
            )
            page_paths = [images_dir / f"page_{index}.png" for index in range(1, len(measured_pages) + 1)]
            write_pagination_debug(
                output_dir / "pagination_debug.json",
                width=width,
                height=height,
                usable_height=safe_body_usable_height(height),
                pages=measured_pages,
            )
            _screenshot_html(
                page=page,
                html=render_intro_html(note=note, width=width, height=height),
                path=intro_path,
            )
            for measured_page, page_path in zip(measured_pages, page_paths):
                _screenshot_html(
                    page=page,
                    html=render_body_html(
                        note=note,
                        blocks=[measured.block for measured in measured_page],
                        width=width,
                        height=height,
                        content_height=_page_height(measured_page),
                    ),
                    path=page_path,
                )
            browser.close()
    except PlaywrightError as exc:  # pragma: no cover - environment dependent.
        raise XhsReportError(
            "XHS image rendering failed: Playwright Chromium is not ready. Run `playwright install chromium`."
        ) from exc
    return XhsRenderResult(intro_path=intro_path, page_paths=page_paths)


def parse_xhs_note(note_path: Path) -> dict[str, Any]:
    if not note_path.is_file():
        raise XhsReportError("XHS image rendering failed: note.md is required.")
    text = note_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise XhsReportError("XHS image rendering failed: note.md must start with frontmatter.")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise XhsReportError("XHS image rendering failed: note.md frontmatter is incomplete.")
    frontmatter_text = parts[1].strip()
    rest = parts[2].strip()
    frontmatter = _parse_frontmatter(frontmatter_text)
    intro, separator, body = rest.partition("\n---")
    if not separator or not intro.strip() or not body.strip():
        raise XhsReportError("XHS image rendering failed: note.md must contain intro and body separated by `---`.")
    return {
        "frontmatter": frontmatter,
        "intro": intro.strip(),
        "base_dir": note_path.parent,
        "body_blocks": parse_markdown_blocks(body.strip()),
    }


def parse_markdown_blocks(markdown: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    current: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append(_markdown_block("\n".join(current)))
                current = []
            continue
        if stripped.startswith("## "):
            if current:
                blocks.append(_markdown_block("\n".join(current)))
                current = []
            blocks.append({"kind": "heading", "text": stripped[3:].strip()})
            continue
        current.append(stripped)
    if current:
        blocks.append(_markdown_block("\n".join(current)))
    return blocks


def measure_xhs_blocks(
    *,
    page: Any,
    blocks: list[dict[str, str]],
    width: int,
    height: int,
) -> list[XhsMeasuredBlock]:
    """Measure body blocks with the same browser layout used for screenshots."""
    if not blocks:
        return []
    html = render_measure_html(blocks=blocks, width=width, height=height)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", delete=False) as file:
        file.write(html)
        temp_path = Path(file.name)
    try:
        page.goto(temp_path.as_uri())
        rows = page.locator(".xhs-block").evaluate_all(
            """
            blocks => blocks.map(block => {
              const rect = block.getBoundingClientRect();
              const style = window.getComputedStyle(block);
              return {
                id: block.dataset.blockId,
                kind: block.dataset.blockKind,
                height: rect.height,
                marginTop: parseFloat(style.marginTop || "0"),
                marginBottom: parseFloat(style.marginBottom || "0")
              };
            })
            """
        )
    finally:
        temp_path.unlink(missing_ok=True)

    measured: list[XhsMeasuredBlock] = []
    for index, row in enumerate(rows):
        block = blocks[index]
        outer_height = float(row["height"]) + float(row["marginTop"]) + float(row["marginBottom"])
        usable_height = safe_body_usable_height(height)
        measured.append(
            XhsMeasuredBlock(
                id=str(row["id"]),
                kind=str(row["kind"]),
                text=block["text"],
                block=block,
                outer_height=outer_height,
                warning="block exceeds usable page height" if outer_height > usable_height else None,
            )
        )
    return measured


def paginate_measured_blocks(
    *,
    blocks: list[XhsMeasuredBlock],
    usable_height: float,
) -> list[list[XhsMeasuredBlock]]:
    """Balance pages using measured DOM heights and semantic cleanup rules."""
    if not blocks:
        return []
    total_height = sum(block.outer_height for block in blocks)
    page_count = max(1, math.ceil(total_height / usable_height))
    target_height = total_height / page_count
    pages = _initial_balanced_pages(blocks, usable_height=usable_height, target_height=target_height)
    pages = _fix_orphan_headings(pages, usable_height=usable_height)
    pages = _keep_quotes_with_previous_paragraph(pages, usable_height=usable_height)
    pages = _split_paragraphs_to_fill_pages(pages, usable_height=usable_height)
    pages = _rebalance_last_page(pages, usable_height=usable_height, target_height=target_height)
    pages = _merge_adjacent_pages_when_possible(pages, usable_height=usable_height)
    return [page for page in pages if page]


def safe_body_usable_height(height: int) -> float:
    return float(height - 88 - 88 - 24)


def render_intro_html(*, note: dict[str, Any], width: int, height: int) -> str:
    frontmatter = note["frontmatter"]
    title = str(frontmatter.get("title") or "播客笔记")
    source = str(frontmatter.get("source") or "")
    cover_html = _render_intro_cover(note)
    return _page_html(
        width=width,
        height=height,
        body=f"""
        <main class="intro">
          {cover_html}
          <div class="kicker">{render_text("Generated by Podcast Agent")}</div>
          <h1>{render_title_text(title)}</h1>
          <p>{render_text(str(note["intro"]))}</p>
          <footer>{render_text(source)}</footer>
        </main>
        """,
    )


def render_body_html(
    *,
    note: dict[str, Any],
    blocks: list[dict[str, str]],
    width: int,
    height: int,
    content_height: float | None = None,
) -> str:
    body = "\n".join(_render_block(block, block_id=f"b{index}") for index, block in enumerate(blocks, start=1))
    extra_gap = balanced_extra_gap(
        content_height=content_height,
        block_count=len(blocks),
        usable_height=safe_body_usable_height(height),
    )
    return _page_html(
        width=width,
        height=height,
        extra_gap=extra_gap,
        body=f"<main class=\"body\"><article>{body}</article></main>",
    )


def render_measure_html(*, blocks: list[dict[str, str]], width: int, height: int) -> str:
    body = "\n".join(_render_block(block, block_id=f"b{index}") for index, block in enumerate(blocks, start=1))
    return _page_html(
        width=width,
        height=height,
        extra_gap=0,
        body=f"<main class=\"body measure\"><article>{body}</article></main>",
    )


def clear_rendered_images(images_dir: Path) -> None:
    """Remove stale rendered pages before writing a fresh XHS image set."""
    for path in [images_dir / "intro.png", *sorted(images_dir.glob("page_*.png"))]:
        if path.is_file():
            path.unlink()


def balanced_extra_gap(*, content_height: float | None, block_count: int, usable_height: float) -> float:
    """Spread leftover vertical space between blocks so it does not pool at page bottom."""
    if content_height is None or block_count <= 1:
        return 0.0
    leftover = usable_height - content_height
    if leftover <= 0:
        return 0.0
    return min(26.0, leftover / (block_count - 1))


def _screenshot_html(*, page: Any, html: str, path: Path) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", delete=False) as file:
        file.write(html)
        temp_path = Path(file.name)
    try:
        page.goto(temp_path.as_uri())
        page.screenshot(path=str(path), full_page=False)
    finally:
        temp_path.unlink(missing_ok=True)


def write_pagination_debug(
    path: Path,
    *,
    width: int,
    height: int,
    usable_height: float,
    pages: list[list[XhsMeasuredBlock]],
) -> None:
    total_height = sum(_page_height(page) for page in pages)
    payload = {
        "width": width,
        "height": height,
        "usable_height": usable_height,
        "total_height": total_height,
        "page_count": len(pages),
        "target_height": total_height / len(pages) if pages else 0,
        "pages": [
            {
                "index": index,
                "height": _page_height(page),
                "blocks": [
                    {
                        "id": block.id,
                        **({"split_from": block.split_from} if block.split_from else {}),
                        **({"split_part": block.split_part} if block.split_part is not None else {}),
                        **({"continuation": block.continuation} if block.continuation else {}),
                    }
                    for block in page
                ],
                "block_ids": [block.id for block in page],
            }
            for index, page in enumerate(pages, start=1)
        ],
        "warnings": [
            {"block_id": block.id, "warning": block.warning}
            for page in pages
            for block in page
            if block.warning
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _render_block(block: dict[str, str], *, block_id: str) -> str:
    kind = escape(block["kind"])
    continuation = str(bool(block.get("continuation"))).lower()
    if block["kind"] == "heading":
        content = f"<h2>{render_text(_plain_heading_text(block['text']))}</h2>"
    elif block["kind"] == "quote":
        content = f"<blockquote>{render_text(block['text'])}</blockquote>"
    else:
        content = f"<p>{render_text(block['text'])}</p>"
    return f'<section class="xhs-block" data-block-id="{block_id}" data-block-kind="{kind}" data-continuation="{continuation}">{content}</section>'


def _plain_heading_text(text: str) -> str:
    return text.strip()


def render_text(text: str) -> str:
    """Escape text for safe HTML rendering."""
    return escape(text)


def render_title_text(text: str, *, min_tail_chars: int = 4) -> str:
    """Escape title text and prevent a single trailing CJK character from wrapping alone."""
    escaped = escape(text)
    match = re.search(r"([\u4e00-\u9fff]{2,})([。！？!?：:，,、；;]*)$", escaped)
    if not match:
        return escaped
    cjk_tail = match.group(1)
    punctuation = match.group(2)
    protected_count = min(len(cjk_tail), min_tail_chars)
    split_at = len(cjk_tail) - protected_count
    prefix = escaped[: match.start(1)] + cjk_tail[:split_at]
    protected = cjk_tail[split_at:] + punctuation
    return f'{prefix}<span class="no-orphan">{protected}</span>'


def _render_intro_cover(note: dict[str, Any]) -> str:
    frontmatter = note.get("frontmatter", {})
    intro_image = str(frontmatter.get("intro_image") or "").strip()
    base_dir = note.get("base_dir")
    if not intro_image or not isinstance(base_dir, Path):
        return ""
    image_path = Path(intro_image)
    if not image_path.is_absolute():
        image_path = base_dir / image_path
    if not image_path.is_file():
        return ""
    return f'<img class="intro-cover" src="{escape(image_path.resolve().as_uri())}" alt="">'


def _markdown_block(text: str) -> dict[str, str]:
    stripped = text.strip()
    if stripped.startswith(">"):
        return {"kind": "quote", "text": stripped.lstrip("> ").strip()}
    return {"kind": "paragraph", "text": re.sub(r"\s+", " ", stripped)}


def _parse_frontmatter(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"')
    return result


def _page_html(*, width: int, height: int, body: str, extra_gap: float = 0) -> str:
    css = f"""
    @page {{ margin: 0; size: {width}px {height}px; }}
    {lxgw_wenkai_font_face(display="block")}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; width: {width}px; height: {height}px; font-family: {DEFAULT_SERIF_FONT_STACK}; color: #17201c; }}
    body {{ background: #f6efe3; }}
    main {{ width: {width}px; height: {height}px; padding: 88px 108px; overflow: hidden; }}
    .intro {{ display: flex; flex-direction: column; justify-content: center; background: #fffaf1; }}
    .intro-cover {{ width: 100%; aspect-ratio: 16 / 9; object-fit: cover; display: block; margin: 0 0 46px; border-radius: 18px; border: 1px solid rgba(23, 32, 28, 0.12); box-shadow: 0 24px 54px rgba(36, 28, 18, 0.24), 0 4px 12px rgba(36, 28, 18, 0.14); }}
    .kicker {{ font-size: 30px; font-weight: 700; font-style: italic; color: #9a422a; margin-bottom: 28px; }}
    h1 {{ margin: 0; font-size: 72px; line-height: 1.12; font-weight: 850; letter-spacing: 0; text-wrap: balance; }}
    .intro p {{ margin: 34px 0 0; font-size: 30px; line-height: 1.72; font-weight: 400; color: #4f5a55; }}
    footer {{ margin-top: 52px; font-size: 26px; color: #59625e; }}
    .body {{ background: #fffaf1; }}
    article {{ height: 100%; display: flex; flex-direction: column; justify-content: flex-start; }}
    .measure {{ height: auto; min-height: {height}px; overflow: visible; }}
    .measure article {{ height: auto; display: block; }}
    .xhs-block {{ margin: 0 0 calc(34px + {extra_gap:.2f}px); }}
    .xhs-block:last-child {{ margin-bottom: 0; }}
    .xhs-block[data-continuation="true"] {{ margin-top: 0; }}
    h2 {{ margin: 0; font-size: 34px; line-height: 1.45; letter-spacing: 0; color: #13231d; text-wrap: balance; }}
    .no-orphan {{ white-space: nowrap; }}
    p, blockquote {{ margin: 0; font-size: 29px; line-height: 1.86; letter-spacing: 0; }}
    blockquote {{ padding-left: 24px; border-left: 4px solid rgba(200, 95, 61, 0.75); color: #5f6a65; font-size: 27px; font-style: italic; line-height: 1.8; }}
    """
    return f"<!doctype html><html><head><meta charset=\"utf-8\"><style>{css}</style></head><body>{body}</body></html>"


def _initial_balanced_pages(
    blocks: list[XhsMeasuredBlock],
    *,
    usable_height: float,
    target_height: float,
) -> list[list[XhsMeasuredBlock]]:
    pages: list[list[XhsMeasuredBlock]] = []
    current: list[XhsMeasuredBlock] = []
    current_height = 0.0
    for block in blocks:
        if block.outer_height > usable_height:
            if current:
                pages.append(current)
                current = []
                current_height = 0.0
            pages.append([block])
            continue
        added_height = current_height + block.outer_height
        if not current:
            current = [block]
            current_height = added_height
            continue
        current_distance = abs(target_height - current_height)
        added_distance = abs(target_height - added_height)
        if added_height <= usable_height and added_distance <= current_distance:
            current.append(block)
            current_height = added_height
        else:
            pages.append(current)
            current = [block]
            current_height = block.outer_height
    if current:
        pages.append(current)
    return pages


def _fix_orphan_headings(
    pages: list[list[XhsMeasuredBlock]],
    *,
    usable_height: float,
) -> list[list[XhsMeasuredBlock]]:
    for index in range(len(pages) - 1):
        page = pages[index]
        next_page = pages[index + 1]
        if len(page) <= 1 or page[-1].kind != "heading":
            continue
        heading = page[-1]
        if _page_height(next_page) + heading.outer_height <= usable_height:
            page.pop()
            next_page.insert(0, heading)
    return [page for page in pages if page]


def _keep_quotes_with_previous_paragraph(
    pages: list[list[XhsMeasuredBlock]],
    *,
    usable_height: float,
) -> list[list[XhsMeasuredBlock]]:
    for index in range(1, len(pages)):
        page = pages[index]
        previous_page = pages[index - 1]
        if not page or not previous_page:
            continue
        quote = page[0]
        if quote.kind != "quote" or previous_page[-1].kind != "paragraph":
            continue
        if _page_height(previous_page) + quote.outer_height <= usable_height:
            previous_page.append(page.pop(0))
    return [page for page in pages if page]


def _rebalance_last_page(
    pages: list[list[XhsMeasuredBlock]],
    *,
    usable_height: float,
    target_height: float,
) -> list[list[XhsMeasuredBlock]]:
    while len(pages) >= 2 and _page_height(pages[-1]) < target_height * 0.55:
        previous_page = pages[-2]
        last_page = pages[-1]
        if len(previous_page) <= 1:
            break
        candidate = previous_page[-1]
        if candidate.kind == "heading":
            break
        if _page_height(last_page) + candidate.outer_height > usable_height:
            break
        previous_page.pop()
        last_page.insert(0, candidate)
    return [page for page in pages if page]


def _merge_adjacent_pages_when_possible(
    pages: list[list[XhsMeasuredBlock]],
    *,
    usable_height: float,
) -> list[list[XhsMeasuredBlock]]:
    merged: list[list[XhsMeasuredBlock]] = []
    index = 0
    while index < len(pages):
        current = list(pages[index])
        while index + 1 < len(pages) and _page_height(current) + _page_height(pages[index + 1]) <= usable_height:
            current.extend(pages[index + 1])
            index += 1
        merged.append(current)
        index += 1
    return [page for page in merged if page]


def _split_paragraphs_to_fill_pages(
    pages: list[list[XhsMeasuredBlock]],
    *,
    usable_height: float,
) -> list[list[XhsMeasuredBlock]]:
    for index in range(len(pages) - 1):
        page = pages[index]
        next_page = pages[index + 1]
        if not page or not next_page:
            continue
        next_block = next_page[0]
        remaining_height = usable_height - _page_height(page)
        if next_block.kind != "paragraph" or remaining_height < usable_height * 0.18:
            continue
        if next_block.outer_height <= remaining_height:
            continue
        split = split_paragraph_block(next_block, available_height=remaining_height)
        if split is None:
            continue
        head, tail = split
        page.append(head)
        next_page[0] = tail
    return [page for page in pages if page]


def split_paragraph_block(
    block: XhsMeasuredBlock,
    *,
    available_height: float,
    min_prefix_chars: int = 10,
) -> tuple[XhsMeasuredBlock, XhsMeasuredBlock] | None:
    if block.kind != "paragraph" or available_height <= 0:
        return None
    text = block.text.strip()
    if len(text) < min_prefix_chars * 2:
        return None

    prefix = _largest_prefix_for_height(
        text,
        available_height=available_height,
        full_height=block.outer_height,
    )
    if len(prefix) < min_prefix_chars or len(text) - len(prefix) < min_prefix_chars:
        return None

    suffix = text[len(prefix) :].lstrip()
    prefix = prefix.rstrip()
    if not prefix or not suffix:
        return None

    prefix_height = _estimate_text_height(prefix, text=text, full_height=block.outer_height)
    suffix_height = max(block.outer_height - prefix_height, _estimate_text_height(suffix, text=text, full_height=block.outer_height))
    split_from = block.split_from or block.id
    head_block = {**block.block, "text": prefix, "split_from": split_from, "split_part": 1, "continuation": False}
    tail_block = {**block.block, "text": suffix, "split_from": split_from, "split_part": 2, "continuation": True}
    return (
        XhsMeasuredBlock(
            id=f"{split_from}a",
            kind=block.kind,
            text=prefix,
            block=head_block,
            outer_height=prefix_height,
            split_from=split_from,
            split_part=1,
        ),
        XhsMeasuredBlock(
            id=f"{split_from}b",
            kind=block.kind,
            text=suffix,
            block=tail_block,
            outer_height=suffix_height,
            split_from=split_from,
            split_part=2,
            continuation=True,
        ),
    )


def _largest_prefix_for_height(text: str, *, available_height: float, full_height: float) -> str:
    sentence_prefixes = _sentence_prefixes(text)
    best = ""
    for prefix in sentence_prefixes:
        if _estimate_text_height(prefix, text=text, full_height=full_height) <= available_height:
            best = prefix
        else:
            break
    if best:
        return best

    low = 0
    high = len(text)
    while low < high:
        mid = (low + high + 1) // 2
        prefix = text[:mid].rstrip()
        if _estimate_text_height(prefix, text=text, full_height=full_height) <= available_height:
            low = mid
        else:
            high = mid - 1
    return text[:low].rstrip()


def _sentence_prefixes(text: str) -> list[str]:
    prefixes: list[str] = []
    for match in re.finditer(r".+?[。！？!?；;](?:[”’])?", text):
        prefixes.append(text[: match.end()].strip())
    return prefixes


def _estimate_text_height(value: str, *, text: str, full_height: float) -> float:
    if not text:
        return 0
    ratio = len(value) / len(text)
    return max(1.0, full_height * ratio)


def _page_height(page: list[XhsMeasuredBlock]) -> float:
    return sum(block.outer_height for block in page)
