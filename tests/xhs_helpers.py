from podcast_agent.reports.xhs.render.layout import XhsMeasuredBlock


def measured_block(
    block_id: str,
    kind: str,
    height: float,
    warning: str | None = None,
    text: str | None = None,
    split_from: str | None = None,
    split_part: int | None = None,
    continuation: bool = False,
) -> XhsMeasuredBlock:
    value = text or block_id
    return XhsMeasuredBlock(
        id=block_id,
        kind=kind,
        text=value,
        block={"kind": kind, "text": value, "continuation": continuation},
        outer_height=height,
        warning=warning,
        split_from=split_from,
        split_part=split_part,
        continuation=continuation,
    )
