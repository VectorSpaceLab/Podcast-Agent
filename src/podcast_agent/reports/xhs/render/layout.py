"""Layout measurement helpers for Xiaohongshu image rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any

__all__ = [
    "XhsMeasuredBlock",
    "balanced_extra_gap",
    "measure_xhs_blocks",
    "page_height",
    "safe_body_usable_height",
]


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


def measure_xhs_blocks(
    *,
    page: Any,
    html: str,
    blocks: list[dict[str, str]],
    height: int,
) -> list[XhsMeasuredBlock]:
    """Measure body blocks with the same browser layout used for screenshots."""
    if not blocks:
        return []
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


def safe_body_usable_height(height: int) -> float:
    return float(height - 88 - 88 - 24)


def balanced_extra_gap(*, content_height: float | None, block_count: int, usable_height: float) -> float:
    """Spread leftover vertical space between blocks so it does not pool at page bottom."""
    if content_height is None or block_count <= 1:
        return 0.0
    leftover = usable_height - content_height
    if leftover <= 0:
        return 0.0
    return min(26.0, leftover / (block_count - 1))


def page_height(page: list[XhsMeasuredBlock]) -> float:
    return sum(block.outer_height for block in page)
