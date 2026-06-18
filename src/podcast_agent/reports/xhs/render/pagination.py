"""Pagination logic for Xiaohongshu body image pages."""

from __future__ import annotations

import re

from podcast_agent.reports.xhs.render.layout import XhsMeasuredBlock

__all__ = ["paginate_measured_blocks", "split_paragraph_block"]

def paginate_measured_blocks(
    *,
    blocks: list[XhsMeasuredBlock],
    usable_height: float,
) -> list[list[XhsMeasuredBlock]]:
    """Paginate measured blocks sequentially, splitting paragraphs at overflow."""
    if not blocks:
        return []
    return _sequential_pages(blocks, usable_height=usable_height)


def split_paragraph_block(
    block: XhsMeasuredBlock,
    *,
    available_height: float,
    min_prefix_chars: int = 10,
) -> tuple[XhsMeasuredBlock, XhsMeasuredBlock] | None:
    if not _can_split_block(block) or available_height <= 0:
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


def _sequential_pages(
    blocks: list[XhsMeasuredBlock],
    *,
    usable_height: float,
) -> list[list[XhsMeasuredBlock]]:
    pending = list(blocks)
    pages: list[list[XhsMeasuredBlock]] = []
    current: list[XhsMeasuredBlock] = []
    current_height = 0.0

    while pending:
        block = pending.pop(0)
        if current_height + block.outer_height <= usable_height:
            current.append(block)
            current_height += block.outer_height
            continue

        if current:
            split = split_paragraph_block(block, available_height=usable_height - current_height)
            if split is not None:
                head, tail = split
                current.append(head)
                pages.append(current)
                current = []
                current_height = 0.0
                pending.insert(0, tail)
                continue

            pages.append(current)
            current = []
            current_height = 0.0
            pending.insert(0, block)
            continue

        split = split_paragraph_block(block, available_height=usable_height)
        if split is not None:
            head, tail = split
            pages.append([head])
            pending.insert(0, tail)
            continue

        pages.append([block])

    if current:
        pages.append(current)
    return pages


def _can_split_block(block: XhsMeasuredBlock) -> bool:
    return block.kind == "paragraph" and not block.continuation and block.split_from is None


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
