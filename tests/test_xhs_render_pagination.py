from podcast_agent.reports.xhs.render.layout import XhsMeasuredBlock
from podcast_agent.reports.xhs.render.pagination import paginate_measured_blocks, split_paragraph_block
from tests.xhs_helpers import measured_block


def test_paginate_measured_blocks_leaves_sparse_last_page_unchanged() -> None:
    blocks = [
        measured_block("b1", "paragraph", 100),
        measured_block("b2", "paragraph", 100),
        measured_block("b3", "paragraph", 600),
        measured_block("b4", "paragraph", 250),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=1000)

    assert [[block.id for block in page] for page in pages] == [["b1", "b2", "b3"], ["b4"]]


def test_paginate_measured_blocks_moves_orphan_heading_to_next_page() -> None:
    blocks = [
        measured_block("b1", "paragraph", 500),
        measured_block("b2", "heading", 100),
        measured_block("b3", "paragraph", 500),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=700)

    assert [[block.id for block in page] for page in pages] == [["b1"], ["b2", "b3"]]


def test_paginate_measured_blocks_keeps_quote_with_previous_paragraph() -> None:
    blocks = [
        measured_block("b1", "paragraph", 500),
        measured_block("b2", "paragraph", 500),
        measured_block("b3", "quote", 100),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=1100)

    assert [[block.id for block in page] for page in pages] == [["b1", "b2", "b3"]]


def test_paginate_measured_blocks_keeps_oversized_block_on_own_page() -> None:
    blocks = [
        measured_block("b1", "paragraph", 300),
        measured_block("b2", "paragraph", 1200, warning="block exceeds usable page height"),
        measured_block("b3", "paragraph", 300),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=1000)

    assert [[block.id for block in page] for page in pages] == [["b1"], ["b2"], ["b3"]]


def test_paginate_measured_blocks_merges_sparse_adjacent_pages() -> None:
    blocks = [
        measured_block("b1", "paragraph", 850),
        measured_block("b2", "paragraph", 850),
        measured_block("b3", "paragraph", 950),
        measured_block("b4", "heading", 100),
        measured_block("b5", "paragraph", 287),
        measured_block("b6", "paragraph", 733),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=1240)

    assert [[block.id for block in page] for page in pages][-1] == ["b4", "b5", "b6"]
    assert _page_height_for_test(pages[-1]) <= 1240


def test_paginate_measured_blocks_splits_paragraph_to_fill_previous_page() -> None:
    long_text = "第一句可以放进上一页。第二句继续解释背景。第三句留到下一页继续。第四句作为收尾。"
    blocks = [
        measured_block("b1", "paragraph", 760),
        measured_block("b2", "paragraph", 900, text=long_text),
        measured_block("b3", "paragraph", 180),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=1000)

    assert pages[0][-1].id == "b2a"
    assert pages[0][-1].split_from == "b2"
    assert pages[1][0].id == "b2b"
    assert pages[1][0].continuation is True
    assert pages[1][0].text in long_text


def test_paginate_measured_blocks_splits_next_paragraph_to_fill_previous_page() -> None:
    text = "第一句补到上一页，交代背景和主要观点。第二句留在下一页，继续解释为什么这个变化重要。第三句继续展开，把剩余信息放在后面。"
    blocks = [
        measured_block("b1", "paragraph", 300),
        measured_block("b2", "paragraph", 300),
        measured_block("b3", "paragraph", 900, text=text),
        measured_block("b4", "paragraph", 1000),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=1200)

    assert [block.id for block in pages[0]] == ["b1", "b2", "b3a"]
    assert pages[0][-1].split_from == "b3"
    assert pages[1][0].id == "b3b"
    assert pages[1][0].continuation is True


def test_split_paragraph_block_uses_sentence_prefix_when_possible() -> None:
    block = measured_block("b1", "paragraph", 900, text="第一句可以放进去。第二句留在下一页。第三句继续。")

    split = split_paragraph_block(block, available_height=360, min_prefix_chars=4)

    assert split is not None
    head, tail = split
    assert head.text == "第一句可以放进去。"
    assert tail.text == "第二句留在下一页。第三句继续。"
    assert tail.continuation is True


def _page_height_for_test(page: list[XhsMeasuredBlock]) -> float:
    return sum(block.outer_height for block in page)
