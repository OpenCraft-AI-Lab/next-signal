from __future__ import annotations

import json
from pathlib import Path

import pytest

import paca.workflows.stages.knowledge_ingest.fetch as fetch_mod
from paca.core import paths


@pytest.fixture
def wiki_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("PACA_WIKI_DIR", str(tmp_path / "wiki"))
    monkeypatch.setenv("PACA_WIKI_RAW_DIR", str(tmp_path / "raw"))
    monkeypatch.setattr(paths, "AGENT_TMP_DIR", tmp_path / "agent-tmp")
    return tmp_path


def test_fetch_markdown_copies_raw_and_reads_body(wiki_paths) -> None:
    src = paths.AGENT_TMP_DIR / "note.md"
    src.parent.mkdir(parents=True)
    src.write_text("# Hello\n\nbody", encoding="utf-8")

    artifact = fetch_mod.fetch_markdown(str(src), category="knowledge")

    assert artifact.source_type == "markdown"
    assert artifact.title == "note"
    assert artifact.markdown.startswith("# Hello")
    assert artifact.raw_path is not None and artifact.raw_path.exists()
    assert artifact.metadata == {}


def test_fetch_markitdown_local_file_stores_raw(wiki_paths, monkeypatch) -> None:
    src = paths.AGENT_TMP_DIR / "page.html"
    src.parent.mkdir(parents=True)
    src.write_text("<html><body>x</body></html>", encoding="utf-8")
    monkeypatch.setattr(
        fetch_mod,
        "convert_source",
        lambda value, **kwargs: {"ok": True, "title": "Example", "markdown": "# Ex"},
    )

    artifact = fetch_mod.fetch_markitdown(str(src), category="knowledge")

    assert artifact.source_type == "markitdown"
    assert artifact.title == "Example"
    assert artifact.markdown == "# Ex"
    assert artifact.raw_path is not None and artifact.raw_path.exists()
    assert artifact.metadata == {"converter": "markitdown"}


def test_fetch_youtube_writes_conversion_json(wiki_paths, monkeypatch) -> None:
    monkeypatch.setattr(
        fetch_mod,
        "convert_source",
        lambda value, **kwargs: {"ok": True, "title": "Yt", "markdown": "# t", "transcript": "..."},
    )

    artifact = fetch_mod.fetch_youtube(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ", category="knowledge"
    )

    assert artifact.source_type == "youtube"
    # raw_path is None for URL inputs; conversion.json is written to raw_dir
    saved = paths.WIKI_RAW_DIR / "youtube" / artifact.digest / "conversion.json"
    assert saved.exists()
    parsed = json.loads(saved.read_text(encoding="utf-8"))
    assert parsed["title"] == "Yt"


def test_fetch_web_validates_and_converts(wiki_paths, monkeypatch) -> None:
    class FakeResponse:
        status_code = 200
        text = "<html>raw</html>"

        def raise_for_status(self):
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def get(self, url, follow_redirects=False):  # noqa: ARG002
            return FakeResponse()

    monkeypatch.setattr(fetch_mod, "http_client", lambda **kwargs: FakeClient())
    monkeypatch.setattr(fetch_mod, "_validate_public_web_url", lambda url: None)
    monkeypatch.setattr(
        fetch_mod,
        "convert_source",
        lambda value: {"ok": True, "title": "Web", "markdown": "# w"},
    )

    artifact = fetch_mod.fetch_web("https://example.com/post", category="knowledge")

    assert artifact.source_type == "web"
    assert artifact.title == "Web"
    assert artifact.markdown == "# w"
    assert artifact.raw_path is not None and artifact.raw_path.exists()
    assert artifact.metadata == {"converter": "markitdown"}


def test_fetch_wechat_uses_opencli(wiki_paths, monkeypatch, tmp_path) -> None:
    saved_md = tmp_path / "article" / "article.md"
    saved_md.parent.mkdir(parents=True)
    saved_md.write_text("# WX\n\nbody\n", encoding="utf-8")
    images_dir = saved_md.parent / "images"
    images_dir.mkdir()
    (images_dir / "img_001.png").write_bytes(b"")

    monkeypatch.setattr(
        fetch_mod,
        "opencli_weixin_download",
        lambda url, output_dir: {
            "title": "WX",
            "account": "Acct",
            "publish_time": "2026-05-05",
            "markdown": "# WX\n\nbody\n",
            "saved_md": saved_md,
            "assets_dir": images_dir,
        },
    )

    artifact = fetch_mod.fetch_wechat("https://mp.weixin.qq.com/s/x", category="knowledge")

    assert artifact.source_type == "wechat"
    assert artifact.title == "WX"
    assert artifact.markdown == "# WX\n\nbody\n"
    assert artifact.metadata["provider"] == "opencli"
    assert artifact.metadata["account"] == "Acct"
    assert artifact.assets_dir == images_dir
    assert artifact.raw_path == saved_md


def test_fetch_wechat_raises_on_empty_markdown(wiki_paths, monkeypatch) -> None:
    monkeypatch.setattr(
        fetch_mod,
        "opencli_weixin_download",
        lambda url, output_dir: {"title": "x", "markdown": "", "saved_md": None, "assets_dir": None},
    )
    with pytest.raises(RuntimeError, match="opencli"):
        fetch_mod.fetch_wechat("https://mp.weixin.qq.com/s/x", category="knowledge")


def test_fetch_bilibili_persists_transcript_record(wiki_paths, monkeypatch) -> None:
    monkeypatch.setattr(
        fetch_mod,
        "extract_bilibili",
        lambda url: {
            "ok": True,
            "html": "<html/>",
            "title": "B",
            "markdown": "# B\n\n## Transcript\n\ntext",
            "transcript": "text",
            "metadata": {"bvid": "BV1", "transcript_source": "whisper"},
        },
    )

    artifact = fetch_mod.fetch_bilibili("https://www.bilibili.com/video/BV1", category="knowledge")

    assert artifact.source_type == "bilibili"
    assert artifact.metadata["bvid"] == "BV1"
    transcript_path = Path(artifact.metadata["transcript_path"])
    assert transcript_path.exists()
    record = json.loads(transcript_path.read_text(encoding="utf-8"))
    assert record["text"] == "text"


def test_fetch_bilibili_raises_on_failure(wiki_paths, monkeypatch) -> None:
    monkeypatch.setattr(
        fetch_mod, "extract_bilibili", lambda url: {"ok": False, "error": "boom"}
    )
    with pytest.raises(RuntimeError, match="boom"):
        fetch_mod.fetch_bilibili("https://www.bilibili.com/video/BV1", category="knowledge")


def test_fetch_dispatches_by_detected_source_type(wiki_paths) -> None:
    src = paths.AGENT_TMP_DIR / "note.md"
    src.parent.mkdir(parents=True)
    src.write_text("# Hello\n\nbody", encoding="utf-8")

    artifact = fetch_mod.fetch(str(src), category="knowledge")

    assert artifact.source_type == "markdown"
    assert artifact.title == "note"
    assert artifact.markdown.startswith("# Hello")


def test_fetch_normalizes_spacing(wiki_paths) -> None:
    src = paths.AGENT_TMP_DIR / "note.md"
    src.parent.mkdir(parents=True)
    src.write_text("# Hello\r\n\r\n\r\n\r\nbody  \r\n", encoding="utf-8")

    artifact = fetch_mod.fetch(str(src), category="knowledge")

    assert "\r" not in artifact.markdown
    assert "\n\n\n" not in artifact.markdown
