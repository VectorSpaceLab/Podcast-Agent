"""CSS styles for Xiaohongshu image pages."""

from __future__ import annotations

from podcast_agent.reports.shared.fonts import DEFAULT_SERIF_FONT_STACK, lxgw_wenkai_font_face

__all__ = ["render_page_css"]


def render_page_css(*, width: int, height: int, extra_gap: float = 0) -> str:
    return f"""
    @page {{ margin: 0; size: {width}px {height}px; }}
    {lxgw_wenkai_font_face(display="block")}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; width: {width}px; height: {height}px; font-family: {DEFAULT_SERIF_FONT_STACK}; color: #17201c; }}
    body {{ background: #f6efe3; }}
    body {{ position: relative; }}
    main {{ width: {width}px; height: {height}px; padding: 88px 108px; overflow: hidden; }}
    .intro {{ display: flex; flex-direction: column; justify-content: center; padding-top: 54px; padding-bottom: 122px; background: #fffaf1; }}
    .intro-cover {{ width: 100%; aspect-ratio: 16 / 9; object-fit: cover; display: block; margin: 0 0 46px; border-radius: 18px; border: 1px solid rgba(23, 32, 28, 0.12); box-shadow: 0 24px 54px rgba(36, 28, 18, 0.24), 0 4px 12px rgba(36, 28, 18, 0.14); }}
    h1 {{ margin: 0; font-size: 72px; line-height: 1.12; font-weight: 850; letter-spacing: 0; text-wrap: balance; }}
    .intro p {{ margin: 34px 0 0; font-size: 30px; line-height: 1.72; font-weight: 400; color: #4f5a55; }}
    .intro-source {{ margin-top: 44px; padding-top: 24px; border-top: 2px solid rgba(23, 32, 28, 0.2); display: grid; gap: 10px; font-size: 22px; line-height: 1.45; color: #59625e; }}
    .source-row {{ display: grid; grid-template-columns: 18px 1fr; gap: 10px; align-items: start; }}
    .source-label {{ color: rgba(89, 98, 94, 0.72); font-weight: 700; }}
    .source-value {{ color: #3f4945; word-break: break-word; }}
    .page-footer {{ position: absolute; left: 108px; right: 108px; bottom: 34px; font-size: 20px; color: rgba(89, 98, 94, 0.72); text-align: center; }}
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
