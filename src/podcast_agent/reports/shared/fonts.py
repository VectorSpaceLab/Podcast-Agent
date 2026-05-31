"""Shared font assets and CSS snippets for rendered outputs."""

from __future__ import annotations

from pathlib import Path


LXGW_WENKAI_FAMILY = "LXGW WenKai"
DEFAULT_SERIF_FONT_STACK = f'"{LXGW_WENKAI_FAMILY}", serif'
DEFAULT_MONO_FONT_STACK = "monospace"


def lxgw_wenkai_font_path() -> Path:
    """Return the bundled LXGW WenKai regular font path."""
    return Path(__file__).parent / "assets" / "fonts" / "LXGWWenKai-Regular.ttf"


def lxgw_wenkai_font_url() -> str:
    """Return a file URL usable from browser-rendered HTML."""
    return lxgw_wenkai_font_path().resolve().as_uri()


def lxgw_wenkai_font_face(*, display: str = "swap") -> str:
    """Return the @font-face rule for the bundled LXGW WenKai font."""
    return (
        "@font-face {\n"
        f'  font-family: "{LXGW_WENKAI_FAMILY}";\n'
        f'  src: url("{lxgw_wenkai_font_url()}") format("truetype");\n'
        "  font-weight: 400;\n"
        "  font-style: normal;\n"
        f"  font-display: {display};\n"
        "}"
    )
