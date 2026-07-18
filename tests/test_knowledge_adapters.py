"""Smoke tests for knowledge-management integrations."""

from __future__ import annotations

import os
import subprocess

import pytest

from paca.integrations import gbrain
from paca.integrations.knowledge import bilibili
from paca.integrations.knowledge import github as github_adapter


def test_gbrain_missing_cli_raises(monkeypatch) -> None:
    monkeypatch.delenv("GBRAIN_BIN", raising=False)
    monkeypatch.setattr(gbrain.shutil, "which", lambda _: None)

    import pytest

    with pytest.raises(RuntimeError, match="gbrain CLI not found"):
        gbrain._gbrain_bin()


def test_gbrain_run_returns_structured_result(monkeypatch) -> None:
    monkeypatch.setenv("GBRAIN_BIN", "/bin/gbrain")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr="")

    monkeypatch.setattr(gbrain.subprocess, "run", fake_run)

    result = gbrain._run_gbrain(["search", "test"])
    assert result["ok"] is True
    assert result["stdout"] == "ok"
    assert result["command"] == ["search", "test"]


def test_gbrain_env_maps_paca_home_to_gbrain_home(tmp_path, monkeypatch) -> None:
    home = tmp_path / "gbrain-test"
    monkeypatch.setenv("PACA_GBRAIN_HOME", str(home))
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:5432/paca")
    monkeypatch.delenv("GBRAIN_DATABASE_URL", raising=False)

    env = gbrain.gbrain_env()

    assert env["GBRAIN_HOME"] == str(home)
    assert "DATABASE_URL" not in env


def test_gbrain_env_resolves_relative_home_from_project_root(monkeypatch) -> None:
    monkeypatch.setenv("PACA_GBRAIN_HOME", "state/test-gbrain")

    env = gbrain.gbrain_env()

    assert env["GBRAIN_HOME"] == str(gbrain.PROJECT_ROOT / "state" / "test-gbrain")


def test_gbrain_env_maps_dedicated_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:5432/paca")
    monkeypatch.setenv("PACA_GBRAIN_DATABASE_URL", "postgresql://localhost:5432/gbrain_test")

    env = gbrain.gbrain_env()

    assert env["GBRAIN_DATABASE_URL"] == "postgresql://localhost:5432/gbrain_test"
    assert "DATABASE_URL" not in env


def test_gbrain_slug_sanitizes_unicode_title_for_cli() -> None:
    slug = gbrain._slug_from_path(gbrain.Path("DeepSeek 视觉原语：指代断裂.md"))

    assert slug.startswith("deepseek-")
    assert "/" not in slug


def test_gbrain_slug_keeps_non_ascii_titles_distinct() -> None:
    first = gbrain._slug_from_path(gbrain.Path("knowledge/视觉原语.md"))
    second = gbrain._slug_from_path(gbrain.Path("knowledge/指代断裂.md"))

    assert first.startswith("knowledge-")
    assert second.startswith("knowledge-")
    assert first != second


def test_gbrain_slug_folds_per_article_subfolder() -> None:
    """A `<dir>/<dir>.md` layout collapses to the same slug as `<dir>.md`."""
    flat = gbrain.gbrain_slug_for_path(gbrain.Path("temp-inbox/my-article.md"))
    nested = gbrain.gbrain_slug_for_path(gbrain.Path("temp-inbox/my-article/my-article.md"))
    assert flat == nested
    assert flat == "temp-inbox-my-article"


def test_bilibili_extract_uses_public_subtitle(monkeypatch) -> None:
    html = """
    <html><body>
      <script>window.__INITIAL_STATE__={"videoData":{"bvid":"BV1","aid":1,"cid":2,"title":"AI來了","desc":"AI 代替人類工作","pubdate":1772798343,"duration":808,"owner":{"name":"Example UP"},"pages":[{"page":1,"part":"視覺語言模型","duration":808}],"subtitle":{"list":[{"subtitle_url":"https://example.com/sub.json"}]}}};(function(){})</script>
    </body></html>
    """

    class FakeResponse:
        def __init__(self, text="", data=None):
            self.text = text
            self._data = data

        @staticmethod
        def raise_for_status():
            return None

        def json(self):
            return self._data

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        @staticmethod
        def get(url):
            if url == "https://www.bilibili.com/video/BV1":
                return FakeResponse(text=html)
            if url == "https://example.com/sub.json":
                return FakeResponse(data={"body": [{"content": "這是一個視覺語言模型"}]})
            raise AssertionError(url)

    monkeypatch.setattr(bilibili, "http_client", lambda **kwargs: FakeClient())
    monkeypatch.setattr(
        bilibili,
        "_transcribe_audio_from_video",
        lambda url: (_ for _ in ()).throw(AssertionError("should not transcribe")),
    )

    result = bilibili.extract_bilibili("https://www.bilibili.com/video/BV1")
    assert result["ok"] is True
    assert result["title"] == "AI来了"
    assert result["metadata"]["transcript_source"] == "public_subtitle"
    assert result["metadata"]["owner"] == "Example UP"
    assert "AI 代替人类工作" in result["markdown"]
    assert "- P1: 视觉语言模型 (13:28)" in result["markdown"]
    assert "这是一个视觉语言模型" in result["markdown"]


# ---------------------------------------------------------------------------
# GitHub adapter


def test_github_parse_repo_url_root() -> None:
    assert github_adapter._parse_repo_url("https://github.com/owner/repo") == ("owner", "repo")
    assert github_adapter._parse_repo_url("https://github.com/owner/repo/") == ("owner", "repo")
    assert github_adapter._parse_repo_url("https://github.com/owner/repo.git") == ("owner", "repo")


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/owner/repo/blob/main/README.md",
        "https://github.com/owner/repo/tree/main",
        "https://github.com/owner/repo/issues/1",
        "https://github.com/owner",
        "https://github.com/",
        "https://example.com/owner/repo",
    ],
)
def test_github_parse_repo_url_rejects(url: str) -> None:
    with pytest.raises(RuntimeError):
        github_adapter._parse_repo_url(url)


def test_github_headers_omit_auth_when_token_missing(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    headers = github_adapter._headers()
    assert "Authorization" not in headers
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"


def test_github_headers_include_auth_when_token_set(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tkn_abc")
    monkeypatch.setattr(github_adapter, "_AUTH_DISABLED_THIS_SESSION", False)
    headers = github_adapter._headers()
    assert headers["Authorization"] == "Bearer tkn_abc"


def test_github_401_falls_back_to_anonymous(monkeypatch) -> None:
    """A configured-but-invalid token returns 401 once; we degrade to anonymous
    for the rest of the session so public-repo bookmarking still works."""
    monkeypatch.setenv("GITHUB_TOKEN", "expired_tkn")
    monkeypatch.setattr(github_adapter, "_AUTH_DISABLED_THIS_SESSION", False)

    calls: list[dict] = []

    class FakeResponse:
        def __init__(self, status_code, data=None, headers=None) -> None:
            self.status_code = status_code
            self._data = data or {}
            self.headers = headers or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise github_adapter.httpx.HTTPStatusError(
                    f"HTTP {self.status_code}", request=None, response=self
                )

        def json(self):
            return self._data

    class FakeClient:
        def __init__(self, headers):
            self.headers = headers

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url, params=None):
            calls.append({"auth": self.headers.get("Authorization")})
            if self.headers.get("Authorization"):
                return FakeResponse(401)
            return FakeResponse(200, data={"full_name": "owner/repo"})

    monkeypatch.setattr(
        github_adapter, "http_client", lambda **kwargs: FakeClient(kwargs.get("headers") or {})
    )

    result = github_adapter._get_json("/repos/owner/repo")
    assert result == {"full_name": "owner/repo"}
    # First call carried auth, second did not
    assert calls[0]["auth"] == "Bearer expired_tkn"
    assert calls[1]["auth"] is None
    assert github_adapter._AUTH_DISABLED_THIS_SESSION is True


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("PACA_RUN_NETWORK_TESTS") != "1",
    reason="hits real GitHub REST API; set PACA_RUN_NETWORK_TESTS=1 to run",
)
def test_github_extract_smoke() -> None:
    """Hit a tiny public repo and assert the packet has the structured sections."""
    result = github_adapter.extract_github("https://github.com/octocat/Hello-World")
    assert result["ok"] is True
    assert result["title"] == "octocat/Hello-World"
    md = result["markdown"]
    assert "# octocat/Hello-World" in md
    assert "## Repo Signals" in md
    assert "## README" in md
    assert result["raw"]["repo"]["name"] == "Hello-World"
    assert result["raw"]["readme"]
