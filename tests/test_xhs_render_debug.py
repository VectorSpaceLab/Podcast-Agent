from pathlib import Path

from podcast_agent.reports.xhs.render.debug import write_pagination_debug
from podcast_agent.reports.xhs.render.layout import safe_body_usable_height
from tests.xhs_helpers import measured_block


def test_write_pagination_debug_writes_page_heights_and_warnings(tmp_path: Path) -> None:
    path = tmp_path / "pagination_debug.json"
    pages = [
        [measured_block("b1", "paragraph", 300)],
        [measured_block("b2", "paragraph", 1200, warning="block exceeds usable page height")],
    ]

    write_pagination_debug(path, width=1080, height=1440, usable_height=safe_body_usable_height(1440), pages=pages)
    text = path.read_text(encoding="utf-8")

    assert '"page_count": 2' in text
    assert '"block_ids": [' in text
    assert "block exceeds usable page height" in text


def test_write_pagination_debug_includes_split_metadata(tmp_path: Path) -> None:
    path = tmp_path / "pagination_debug.json"
    pages = [[measured_block("b2b", "paragraph", 300, text="后半段", split_from="b2", split_part=2, continuation=True)]]

    write_pagination_debug(path, width=1080, height=1440, usable_height=safe_body_usable_height(1440), pages=pages)
    text = path.read_text(encoding="utf-8")

    assert '"split_from": "b2"' in text
    assert '"split_part": 2' in text
    assert '"continuation": true' in text
