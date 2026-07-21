from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import paca.workflows.stages.knowledge_ingest.artifact_editor as artifact_editor_mod
import paca.workflows.stages.knowledge_ingest.classify as classify_mod
import paca.workflows.stages.knowledge_ingest.fetch as pipeline_fetch
import paca.workflows.stages.knowledge_ingest.persist as persist_mod
from paca.core import paths
from paca.workflows.stages.knowledge_ingest.classify import detect_source_type
from paca.workflows.knowledge_ingest import ingest_one


@pytest.fixture
def wiki_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("PACA_WIKI_DIR", str(tmp_path / "wiki"))
    monkeypatch.setenv("PACA_WIKI_RAW_DIR", str(tmp_path / "raw"))
    monkeypatch.setattr(paths, "AGENT_TMP_DIR", tmp_path / "agent-tmp")
    monkeypatch.setattr(persist_mod, "gbrain_ingest", lambda path, slug=None: {"ok": True})
    monkeypatch.setattr(
        "paca.workflows.knowledge_ingest._MANIFEST", tmp_path / "knowledge_ingest_manifest.json"
    )

    class _FakeClassifier:
        def run(self, agent_input, **kwargs):
            return _FakeResponse(json.dumps({"category": "knowledge/ai-ml"}))

    monkeypatch.setattr(classify_mod, "build_from_name", lambda name: _FakeClassifier())
    return tmp_path


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


def _stub_editor(
    monkeypatch,
    *,
    title: str | None = None,
    tags: tuple[str, ...] = ("alpha", "beta"),
    summary: str = "a dense factual summary.",
    freshness: str = "stable",
) -> None:
    """Stub both edit-phase agents: the body cleaner echoes the body, the
    frontmatter writer returns the canned fields."""

    class FakeAgent:
        def __init__(self, name: str) -> None:
            self.name = name

        def run(self, agent_input, **kwargs):
            data = json.loads(agent_input)
            if self.name == "knowledge_artifact_editor":
                return _FakeResponse(data["markdown"])
            return _FakeResponse(
                json.dumps(
                    {
                        "title": title if title is not None else data["title"],
                        "summary": summary,
                        "tags": list(tags),
                        "freshness": freshness,
                    },
                    ensure_ascii=False,
                )
            )

    monkeypatch.setattr(artifact_editor_mod, "build_from_name", lambda name: FakeAgent(name))


def _frontmatter(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8").split("---", 2)[1])


def test_detect_source_type() -> None:
    assert detect_source_type("https://mp.weixin.qq.com/s/example") == "wechat"
    assert detect_source_type("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"
    assert detect_source_type("https://www.bilibili.com/video/BV123") == "bilibili"
    assert detect_source_type("https://example.com/post") == "web"
    assert detect_source_type("/tmp/example.md") == "markdown"
    assert detect_source_type("/tmp/example.pdf") == "markitdown"
    assert detect_source_type("/tmp/example.png") == "markitdown"


def test_detect_source_type_github_root() -> None:
    assert detect_source_type("https://github.com/owner/repo") == "github"
    assert detect_source_type("https://github.com/owner/repo/") == "github"


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/owner/repo/blob/main/README.md",
        "https://github.com/owner/repo/tree/main",
        "https://github.com/owner/repo/issues/1",
        "https://github.com/owner/repo/pull/2",
        "https://github.com/owner",
        "https://github.com/",
    ],
)
def test_detect_source_type_github_subpaths_rejected(url: str) -> None:
    with pytest.raises(RuntimeError, match="unsupported github URL"):
        detect_source_type(url)


def test_ingest_markdown_file_writes_clean_and_raw(wiki_paths, monkeypatch) -> None:
    _stub_editor(monkeypatch, tags=("omlx", "local-models"))
    source = paths.AGENT_TMP_DIR / "note.md"
    source.parent.mkdir(parents=True)
    source.write_text("# OMLX\n\nLocal model notes.", encoding="utf-8")

    result = ingest_one(str(source), ingest=False)

    assert result["ok"] is True
    assert Path(result["raw_path"]).exists()
    text = Path(result["markdown_path"]).read_text(encoding="utf-8")
    fm = _frontmatter(result["markdown_path"])
    assert fm["title"] == "note"
    assert fm["source_type"] == "markdown"
    assert fm["tags"] == ["omlx", "local-models"]
    assert fm["freshness"] == "stable"
    assert "# OMLX" in text
    assert "## Summary\n\na dense factual summary." in text


def test_ingest_markdown_file_uses_editor_title_for_filename(wiki_paths, monkeypatch) -> None:
    _stub_editor(monkeypatch, title="OMLX 使用笔记")
    source = paths.AGENT_TMP_DIR / "note.md"
    source.parent.mkdir(parents=True)
    source.write_text("# OMLX\n\nLocal model notes.", encoding="utf-8")

    result = ingest_one(str(source), ingest=False)

    assert Path(result["markdown_path"]).name == "OMLX 使用笔记.md"
    assert _frontmatter(result["markdown_path"])["title"] == "OMLX 使用笔记"


def test_ingest_local_file_rejects_paths_outside_agent_tmp(wiki_paths) -> None:
    source = wiki_paths / "outside.md"
    source.write_text("# Private\n\nDo not read arbitrary paths.", encoding="utf-8")

    with pytest.raises(RuntimeError, match="must be staged"):
        ingest_one(str(source), ingest=False)


def test_web_url_rejects_private_resolved_address(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline_fetch.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, "", ("127.0.0.1", 443))],
    )
    with pytest.raises(RuntimeError, match="refusing private web URL host"):
        pipeline_fetch._validate_public_web_url("https://example.com/article")
