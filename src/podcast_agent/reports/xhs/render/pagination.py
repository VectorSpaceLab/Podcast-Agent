"""Pagination logic for Xiaohongshu body image pages."""

from __future__ import annotations

import math
import re

from podcast_agent.reports.xhs.render.layout import XhsMeasuredBlock, page_height

__all__ = ["paginate_measured_blocks", "split_paragraph_block"]


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
        if page_height(next_page) + heading.outer_height <= usable_height:
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
        if page_height(previous_page) + quote.outer_height <= usable_height:
            previous_page.append(page.pop(0))
    return [page for page in pages if page]


def _rebalance_last_page(
    pages: list[list[XhsMeasuredBlock]],
    *,
    usable_height: float,
    target_height: float,
) -> list[list[XhsMeasuredBlock]]:
    while len(pages) >= 2 and page_height(pages[-1]) < target_height * 0.55:
        previous_page = pages[-2]
        last_page = pages[-1]
        if len(previous_page) <= 1:
            break
        candidate = previous_page[-1]
        if candidate.kind == "heading":
            break
        if page_height(last_page) + candidate.outer_height > usable_height:
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
        while index + 1 < len(pages) and page_height(current) + page_height(pages[index + 1]) <= usable_height:
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
        remaining_height = usable_height - page_height(page)
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
