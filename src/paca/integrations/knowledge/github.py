"""GitHub repo extraction for knowledge ingestion.

Pulls six classes of signal from the public REST API and assembles a
structured markdown packet for the rest of the ingest pipeline. Auth is
optional: with `GITHUB_TOKEN` set, calls go authenticated (5k/h); without,
anonymous (60/h) — enough for ad-hoc personal bookmarking.

Failure policy mirrors the bilibili adapter:
- README fetch is mandatory; failure → RuntimeError.
- All other signal sections fail soft inside their own try/except — the
  packet still ships with whatever was collected.
"""

from __future__ import annotations

import base64
import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from paca.integrations._helpers import http_client, to_jsonable, truncate

logger = logging.getLogger(__name__)

_BASE = "https://api.github.com"
_README_MAX_CHARS = 12000
_MANIFEST_MAX_CHARS = 4000
_RELEASE_BODY_MAX_CHARS = 800
_MANIFEST_CANDIDATES = ("pyproject.toml", "package.json", "Cargo.toml", "go.mod")

# If a configured GITHUB_TOKEN returns 401, we degrade to anonymous for the rest
# of the process and skip attaching the Authorization header on subsequent calls
# — public repos still work even when the user's token is stale. A loud warning
# is logged once so the user knows their token needs rotation.
_AUTH_DISABLED_THIS_SESSION = False


def extract_github(url: str) -> dict[str, Any]:
    """Extract repo metadata + README + activity signals for one GitHub repo URL.

    Returns the bilibili-style dict shape:
        {ok, title, markdown, metadata, raw}
    """
    owner, repo = _parse_repo_url(url)

    repo_data = _get_json(f"/repos/{owner}/{repo}")
    if not repo_data:
        raise RuntimeError(f"github: could not fetch /repos/{owner}/{repo}")

    default_branch = repo_data.get("default_branch") or "HEAD"

    readme_text = _fetch_readme(owner, repo)
    if not readme_text:
        raise RuntimeError(f"github: {owner}/{repo} has no fetchable README")

    contents = _get_json(f"/repos/{owner}/{repo}/contents/", default=[]) or []
    releases = _get_json(f"/repos/{owner}/{repo}/releases", params={"per_page": 3}, default=[]) or []
    manifest_name, manifest_text = _fetch_manifest(owner, repo)
    commits = _get_json(f"/repos/{owner}/{repo}/commits", params={"per_page": 10}, default=[]) or []
    languages = _get_json(f"/repos/{owner}/{repo}/languages", default={}) or {}
    contributors_count = _get_contributors_count(owner, repo)

    title = f"{owner}/{repo}"
    lines: list[str] = [f"# {title}", ""]
    lines.extend(_section_repo_signals(url, repo_data))
    lines.extend(_section_project_layout(contents))
    lines.extend(_section_releases(releases))
    if manifest_name and manifest_text:
        lines.extend(_section_manifest(manifest_name, manifest_text))
    lines.extend(_section_commits(commits))
    lines.extend(_section_activity(contributors_count, languages))
    lines.extend(_section_readme(readme_text))

    metadata: dict[str, Any] = {
        "owner": owner,
        "repo": repo,
        "default_branch": default_branch,
        "description": repo_data.get("description"),
        "stars": repo_data.get("stargazers_count"),
        "forks": repo_data.get("forks_count"),
        "language": repo_data.get("language"),
        "topics": repo_data.get("topics") or [],
        "license": (repo_data.get("license") or {}).get("spdx_id"),
        "homepage": repo_data.get("homepage"),
        "pushed_at": repo_data.get("pushed_at"),
        "created_at": repo_data.get("created_at"),
        "manifest_name": manifest_name,
    }

    return to_jsonable(
        {
            "ok": True,
            "title": title,
            "markdown": "\n".join(lines),
            "metadata": metadata,
            "raw": {
                "repo": repo_data,
                "readme": readme_text,
            },
        }
    )


# ---------------------------------------------------------------------------
# URL parsing (also called from the fetcher as a defensive double-check)


def _parse_repo_url(url: str) -> tuple[str, str]:
    """Return `(owner, repo)` for a github.com root URL or raise."""
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if parsed.scheme not in {"http", "https"} or host != "github.com":
        raise RuntimeError(f"not a github.com URL: {url}")
    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) != 2:
        raise RuntimeError(
            f"unsupported github URL: {url} — only repo root /<owner>/<repo> is supported"
        )
    owner, repo = segments
    # Strip a stray .git suffix some users paste.
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


# ---------------------------------------------------------------------------
# Per-section assembly


def _section_repo_signals(url: str, repo_data: dict[str, Any]) -> list[str]:
    out = ["## Repo Signals", ""]
    pairs = [
        ("Source", url),
        ("Description", repo_data.get("description")),
        ("Homepage", repo_data.get("homepage")),
        ("Language", repo_data.get("language")),
        ("License", (repo_data.get("license") or {}).get("spdx_id")),
        ("Stars", repo_data.get("stargazers_count")),
        ("Forks", repo_data.get("forks_count")),
        ("Open issues", repo_data.get("open_issues_count")),
        ("Watchers", repo_data.get("subscribers_count")),
        ("Default branch", repo_data.get("default_branch")),
        ("Created", repo_data.get("created_at")),
        ("Pushed", repo_data.get("pushed_at")),
    ]
    for label, value in pairs:
        if value is None or value == "":
            continue
        out.append(f"- {label}: {value}")
    topics = repo_data.get("topics") or []
    if topics:
        out.append(f"- Topics: {', '.join(topics)}")
    out.append("")
    return out


def _section_project_layout(contents: list[dict[str, Any]]) -> list[str]:
    if not contents:
        return []
    dirs = sorted(item["name"] for item in contents if item.get("type") == "dir")
    files = sorted(item["name"] for item in contents if item.get("type") == "file")
    out = ["## Project Layout", ""]
    for d in dirs:
        out.append(f"- {d}/")
    for f in files:
        out.append(f"- {f}")
    out.append("")
    return out


def _section_releases(releases: list[dict[str, Any]]) -> list[str]:
    if not releases:
        return []
    out = ["## Recent Releases", ""]
    for rel in releases[:3]:
        name = rel.get("name") or rel.get("tag_name") or "(unnamed)"
        tag = rel.get("tag_name") or ""
        published = rel.get("published_at") or ""
        header = f"### {name}"
        meta_bits = [bit for bit in (tag, published) if bit]
        if meta_bits:
            header += f" ({' · '.join(meta_bits)})"
        out.append(header)
        body = (rel.get("body") or "").strip()
        if body:
            out.append("")
            out.append(truncate(body, _RELEASE_BODY_MAX_CHARS))
        out.append("")
    return out


def _section_manifest(name: str, text: str) -> list[str]:
    out = [f"## Manifest ({name})", "", "```"]
    out.append(truncate(text, _MANIFEST_MAX_CHARS))
    out.extend(["```", ""])
    return out


def _section_commits(commits: list[dict[str, Any]]) -> list[str]:
    if not commits:
        return []
    out = ["## Recent Commits", ""]
    for entry in commits[:10]:
        sha = (entry.get("sha") or "")[:7]
        commit = entry.get("commit") or {}
        message = (commit.get("message") or "").splitlines()[0].strip() if commit.get("message") else ""
        if sha or message:
            out.append(f"- {sha} {message}".rstrip())
    out.append("")
    return out


def _section_activity(contributors_count: int | None, languages: dict[str, Any]) -> list[str]:
    if contributors_count is None and not languages:
        return []
    out = ["## Activity", ""]
    if contributors_count is not None:
        out.append(f"- Contributors: {contributors_count}")
    if languages:
        total = sum(v for v in languages.values() if isinstance(v, (int, float))) or 0
        if total > 0:
            ranked = sorted(languages.items(), key=lambda kv: kv[1], reverse=True)[:4]
            parts = [f"{lang} {round(bytes_ / total * 100)}%" for lang, bytes_ in ranked]
            out.append(f"- Languages: {', '.join(parts)}")
    out.append("")
    return out


def _section_readme(readme_text: str) -> list[str]:
    return ["## README", "", truncate(readme_text, _README_MAX_CHARS).strip(), ""]


# ---------------------------------------------------------------------------
# REST helpers


def _headers(*, force_anonymous: bool = False) -> dict[str, str]:
    """Standard GitHub headers; attach Authorization only if a token is set
    and `_AUTH_DISABLED_THIS_SESSION` has not been tripped by a prior 401."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "intelligent-digitalpaca-knowledge-ingest",
    }
    if force_anonymous or _AUTH_DISABLED_THIS_SESSION:
        return headers
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request(path: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
    """GET a GitHub endpoint, retrying anonymously once if the token returns 401."""
    global _AUTH_DISABLED_THIS_SESSION

    with http_client(headers=_headers()) as client:
        response = client.get(f"{_BASE}{path}", params=params)

    if (
        response.status_code == 401
        and not _AUTH_DISABLED_THIS_SESSION
        and os.environ.get("GITHUB_TOKEN", "").strip()
    ):
        logger.warning(
            "github: GITHUB_TOKEN returned 401 — falling back to anonymous "
            "access for this session. Rotate or unset the token to silence "
            "this warning."
        )
        _AUTH_DISABLED_THIS_SESSION = True
        with http_client(headers=_headers(force_anonymous=True)) as client:
            response = client.get(f"{_BASE}{path}", params=params)

    response.raise_for_status()
    return response


def _get_json(
    path: str, *, params: dict[str, Any] | None = None, default: Any = None
) -> Any:
    """GET a JSON endpoint; return `default` (None when omitted) on any failure."""
    try:
        return _request(path, params=params).json()
    except Exception as exc:  # noqa: BLE001 — non-README signal calls fail soft by design
        logger.warning("github: GET %s failed: %s", path, exc)
        return default


def _fetch_readme(owner: str, repo: str) -> str:
    """Mandatory README fetch. Raises if unavailable."""
    data = _request(f"/repos/{owner}/{repo}/readme").json()
    encoding = data.get("encoding")
    content = data.get("content") or ""
    if encoding == "base64":
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return str(content)


def _fetch_manifest(owner: str, repo: str) -> tuple[str | None, str | None]:
    """Try the candidate manifest filenames in order; return the first that exists."""
    for name in _MANIFEST_CANDIDATES:
        data = _get_json(f"/repos/{owner}/{repo}/contents/{name}")
        if not isinstance(data, dict):
            continue
        if data.get("encoding") == "base64":
            try:
                text = base64.b64decode(data.get("content") or "").decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001 — corrupt content; skip and try next
                continue
            return name, text
    return None, None


def _get_contributors_count(owner: str, repo: str) -> int | None:
    """Return a contributor count via the per_page=1 + Link header trick.

    GitHub paginates `/contributors` and exposes the total via the `Link: rel="last"`
    page number when `per_page=1`. Falls back to None on any failure.
    """
    try:
        response = _request(
            f"/repos/{owner}/{repo}/contributors",
            params={"per_page": 1, "anon": "true"},
        )
        link = response.headers.get("Link") or ""
        match = re.search(r'[?&]page=(\d+)[^>]*>;\s*rel="last"', link)
        if match:
            return int(match.group(1))
        # No `last` link → result fits on one page; count what's there.
        body = response.json()
        return len(body) if isinstance(body, list) else None
    except Exception as exc:  # noqa: BLE001 — soft-fail, contributors block is optional
        logger.warning("github: contributors count failed: %s", exc)
        return None
