"""Pure-function tests for the opencli image link rewriter."""

from __future__ import annotations

from pathlib import Path

from paca.integrations.knowledge.opencli import rewrite_image_links


def _make_images(tmp_path: Path, names: list[str]) -> Path:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    for name in names:
        (images_dir / name).write_bytes(b"")
    return images_dir


def test_all_slots_present(tmp_path: Path) -> None:
    images = _make_images(tmp_path, ["img_001.png", "img_002.jpeg"])
    md = (
        "intro\n\n"
        "![first](https://mmbiz.qpic.cn/a.png#imgIndex=0 \"first\")\n\n"
        "middle\n\n"
        "![second](https://mmbiz.qpic.cn/b.jpeg#imgIndex=1)\n\n"
        "end\n"
    )

    out, warnings = rewrite_image_links(md, images)

    assert warnings == []
    assert "![first](images/img_001.png)" in out
    assert "![second](images/img_002.jpeg)" in out
    assert "mmbiz.qpic.cn" not in out


def test_missing_slot_drops_reference(tmp_path: Path) -> None:
    # Slot 2 failed: files are 001, 003. Markdown line for the missing slot
    # should disappear entirely; the others should be rewritten.
    images = _make_images(tmp_path, ["img_001.png", "img_003.png"])
    md = (
        "head\n\n"
        "![a](https://mmbiz.qpic.cn/a.png#imgIndex=0)\n\n"
        "![b](https://mmbiz.qpic.cn/b.png#imgIndex=1)\n\n"
        "![c](https://mmbiz.qpic.cn/c.png#imgIndex=2)\n\n"
        "tail\n"
    )

    out, warnings = rewrite_image_links(md, images)

    assert len(warnings) == 1
    assert "image #2" in warnings[0]
    assert "b.png" in warnings[0]
    assert "![a](images/img_001.png)" in out
    assert "![c](images/img_003.png)" in out
    assert "b.png" not in out


def test_duplicate_url_maps_to_same_slot(tmp_path: Path) -> None:
    images = _make_images(tmp_path, ["img_001.png", "img_002.png"])
    md = (
        "![a](https://mmbiz.qpic.cn/a.png#imgIndex=0)\n\n"
        "![b](https://mmbiz.qpic.cn/b.png#imgIndex=1)\n\n"
        "![a-again](https://mmbiz.qpic.cn/a.png#imgIndex=2)\n"
    )

    out, warnings = rewrite_image_links(md, images)

    assert warnings == []
    # Same base URL appears twice in markdown — both occurrences rewrite to the
    # same local file (the slot OpenCLI assigned at first occurrence).
    assert out.count("images/img_001.png") == 2
    assert out.count("images/img_002.png") == 1


def test_no_images_at_all(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"  # not created
    md = "just text\n\nno images here\n"
    out, warnings = rewrite_image_links(md, images_dir)
    assert out == md
    assert warnings == []


def test_url_without_fragment_still_matches(tmp_path: Path) -> None:
    # Older articles or non-mp.weixin sources may not carry #imgIndex.
    images = _make_images(tmp_path, ["img_001.png"])
    md = "![a](https://mmbiz.qpic.cn/a.png)\n"
    out, warnings = rewrite_image_links(md, images)
    assert warnings == []
    assert "![a](images/img_001.png)" in out
