"""Debug artifact helpers for Xiaohongshu image pagination."""

from __future__ import annotations

import json
from pathlib import Path

from podcast_agent.reports.xhs.render.layout import XhsMeasuredBlock, page_height

__all__ = ["write_pagination_debug"]


def write_pagination_debug(
    path: Path,
    *,
    width: int,
    height: int,
    usable_height: float,
    pages: list[list[XhsMeasuredBlock]],
) -> None:
    total_height = sum(page_height(page) for page in pages)
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
                "height": page_height(page),
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
