from podcast_agent.reports.xhs.render.layout import XhsMeasuredBlock
from podcast_agent.reports.xhs.render.pagination import paginate_measured_blocks, split_paragraph_block
from tests.xhs_helpers import measured_block


def test_paginate_measured_blocks_returns_empty_pages_for_empty_blocks() -> None:
    assert paginate_measured_blocks(blocks=[], usable_height=1000) == []


def test_paginate_measured_blocks_keeps_fitting_blocks_on_same_page() -> None:
    blocks = [
        measured_block("b1", "heading", 100),
        measured_block("b2", "paragraph", 300),
        measured_block("b3", "quote", 150),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=700)

    assert _page_ids(pages) == [["b1", "b2", "b3"]]


def test_paginate_measured_blocks_moves_oversized_heading_to_next_page() -> None:
    blocks = [
        measured_block("b1", "paragraph", 600),
        measured_block("b2", "heading", 200),
        measured_block("b3", "paragraph", 200),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=700)

    assert _page_ids(pages) == [["b1"], ["b2", "b3"]]


def test_paginate_measured_blocks_moves_oversized_quote_to_next_page() -> None:
    blocks = [
        measured_block("b1", "paragraph", 600),
        measured_block("b2", "quote", 200),
        measured_block("b3", "paragraph", 200),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=700)

    assert _page_ids(pages) == [["b1"], ["b2", "b3"]]


def test_paginate_measured_blocks_splits_paragraph_at_overflow() -> None:
    text = "第一句补到上一页，交代背景和主要观点。第二句留在下一页，继续解释为什么这个变化重要。第三句继续展开，把剩余信息放在后面。"
    blocks = [
        measured_block("b1", "paragraph", 300),
        measured_block("b2", "paragraph", 300),
        measured_block("b3", "paragraph", 900, text=text),
        measured_block("b4", "paragraph", 200),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=1000)

    assert _page_ids(pages)[0] == ["b1", "b2", "b3a"]
    assert pages[0][-1].split_from == "b3"
    assert pages[1][0].id == "b3b"
    assert pages[1][0].continuation is True
    assert pages[1][0].text in text


def test_paginate_measured_blocks_splits_oversized_paragraph_on_empty_page() -> None:
    text = (
        "第一句占据第一页并提供足够长的背景信息。"
        "第二句继续进入下一页，说明为什么这个段落必须被拆开。"
        "第三句作为更多内容，保证前后缀都有足够长度。"
        "第四句继续展开，避免因为文本太短而无法安全拆分。"
    )
    blocks = [
        measured_block("b1", "paragraph", 1400, text=text),
        measured_block("b2", "paragraph", 100),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=700)

    assert _page_ids(pages)[0] == ["b1a"]
    assert pages[0][0].split_from == "b1"
    assert pages[1][0].id == "b1b"
    assert pages[1][0].continuation is True


def test_paginate_measured_blocks_keeps_oversized_unsplittable_block_on_own_page() -> None:
    blocks = [
        measured_block("b1", "paragraph", 300),
        measured_block("b2", "heading", 1200, warning="block exceeds usable page height"),
        measured_block("b3", "paragraph", 300),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=1000)

    assert _page_ids(pages) == [["b1"], ["b2"], ["b3"]]


def test_paginate_measured_blocks_does_not_split_continuation_paragraph_again() -> None:
    continuation = measured_block(
        "b1b",
        "paragraph",
        900,
        text="第二页继续的段落，不应该在第一版顺序分页中继续拆开。",
        split_from="b1",
        split_part=2,
        continuation=True,
    )
    blocks = [
        measured_block("b0", "paragraph", 200),
        continuation,
        measured_block("b2", "paragraph", 100),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=700)

    assert _page_ids(pages) == [["b0"], ["b1b"], ["b2"]]


def test_paginate_measured_blocks_splits_paragraph_after_heading_to_reduce_blank_space() -> None:
    text = "这一段应该拆出前半部分放到上一页。后半部分继续留在下一页，用来模拟第二个标题之后的正文。"
    blocks = [
        measured_block("b1", "heading", 83),
        measured_block("b2", "paragraph", 304),
        measured_block("b3", "quote", 131),
        measured_block("b4", "heading", 83),
        measured_block("b5", "paragraph", 304, text=text),
        measured_block("b6", "paragraph", 200),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=700)

    assert _page_ids(pages)[0] == ["b1", "b2", "b3", "b4", "b5a"]
    assert pages[1][0].id == "b5b"
    assert pages[1][0].continuation is True


def test_paginate_measured_blocks_preserves_order_after_split() -> None:
    text = (
        "第一句放到第一页，补足当前页面剩余空间。"
        "第二句接在下一页，继续解释这个顺序分页行为。"
        "第三句继续提供足够长度，避免拆分失败。"
        "第四句结束，并保持后续引用块的顺序。"
    )
    blocks = [
        measured_block("b1", "heading", 100),
        measured_block("b2", "paragraph", 600),
        measured_block("b3", "paragraph", 400, text=text),
        measured_block("b4", "quote", 100),
    ]

    pages = paginate_measured_blocks(blocks=blocks, usable_height=800)

    assert _flatten_ids(pages) == ["b1", "b2", "b3a", "b3b", "b4"]


def test_split_paragraph_block_uses_sentence_prefix_when_possible() -> None:
    block = measured_block("b1", "paragraph", 900, text="第一句可以放进去。第二句留在下一页。第三句继续。")

    split = split_paragraph_block(block, available_height=360, min_prefix_chars=4)

    assert split is not None
    head, tail = split
    assert head.text == "第一句可以放进去。"
    assert tail.text == "第二句留在下一页。第三句继续。"
    assert tail.continuation is True


def test_split_paragraph_block_does_not_split_continuation() -> None:
    block = measured_block(
        "b1b",
        "paragraph",
        900,
        text="这一段已经是拆分后的延续文本，不再继续拆。",
        split_from="b1",
        split_part=2,
        continuation=True,
    )

    assert split_paragraph_block(block, available_height=400, min_prefix_chars=4) is None


def _page_ids(pages: list[list[XhsMeasuredBlock]]) -> list[list[str]]:
    return [[block.id for block in page] for page in pages]


def _flatten_ids(pages: list[list[XhsMeasuredBlock]]) -> list[str]:
    return [block.id for page in pages for block in page]
