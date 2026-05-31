from podcast_agent.reports.xhs.render.layout import balanced_extra_gap, safe_body_usable_height


def test_balanced_extra_gap_skips_single_block_and_caps_gap() -> None:
    assert balanced_extra_gap(content_height=900, block_count=1, usable_height=1240) == 0
    assert balanced_extra_gap(content_height=1208, block_count=3, usable_height=1240) == 16
    assert balanced_extra_gap(content_height=900, block_count=3, usable_height=1240) == 26


def test_safe_body_usable_height_uses_padding_and_margin() -> None:
    assert safe_body_usable_height(1440) == 1240
