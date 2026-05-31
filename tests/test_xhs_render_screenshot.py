from pathlib import Path

from podcast_agent.reports.xhs.render.screenshot import clear_rendered_images


def test_clear_rendered_images_removes_stale_intro_and_pages(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    for name in ("intro.png", "page_1.png", "page_5.png", "cover.png"):
        (images_dir / name).write_bytes(b"old")

    clear_rendered_images(images_dir)

    assert not (images_dir / "intro.png").exists()
    assert not (images_dir / "page_1.png").exists()
    assert not (images_dir / "page_5.png").exists()
    assert (images_dir / "cover.png").exists()
