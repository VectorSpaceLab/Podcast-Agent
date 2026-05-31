from podcast_agent.reports.xhs.render.styles import render_page_css


def test_render_page_css_includes_dimensions_font_and_gap() -> None:
    css = render_page_css(width=1080, height=1440, extra_gap=26)

    assert "@page { margin: 0; size: 1080px 1440px; }" in css
    assert 'font-family: "LXGW WenKai", serif' in css
    assert "main { width: 1080px; height: 1440px; padding: 88px 108px; overflow: hidden; }" in css
    assert ".xhs-block { margin: 0 0 calc(34px + 26.00px); }" in css
