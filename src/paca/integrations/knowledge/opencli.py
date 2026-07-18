"""OpenCLI bridge — WeChat Official Account article download.

OpenCLI's `weixin download` subcommand renders a public WeChat article to
Markdown and optionally downloads embedded images as `images/img_NNN.<ext>`
under the article folder. It already tries to rewrite remote image URLs to
local paths, but its rewriter does an exact-string dictionary lookup that
misses because the markdown URLs carry a `#imgIndex=N` fragment from the
source HTML — so the rewrite step is currently broken upstream and we do it
here instead.

Rewrite rule (mirrors OpenCLI's own numbering, see
opencli/dist/src/download/article-download.js):

  * Walk the markdown's `![alt](url)` references in document order; keep the
    first occurrence of each unique base URL (strip `#fragment`).
  * `images/img_NNN.ext` files in the article folder use 1-indexed positions
    against that same deduped list. OpenCLI skips failed downloads silently
    and leaves a gap (e.g. `img_001, img_002, img_004` if slot 3 failed) — so
    the file number is the slot index, not a sequential rename.
  * For each slot whose file exists, replace every `![alt](url-or-fragment)`
    that maps to that base URL with `![alt](images/img_NNN.ext)`.
  * For slots with no file (OpenCLI skipped them), the original `![]()` line
    is removed entirely (along with the trailing newline) — per project
    policy we don't keep dead remote URLs; the wiki copy stays self-contained.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from paca.integrations._helpers import env, to_jsonable

logger = logging.getLogger(__name__)

_DOWNLOAD_TIMEOUT = 300
# Matches a whole markdown image reference line so we can drop failed slots
# cleanly. Allows leading whitespace and an optional title string after the URL.
_IMG_LINE_RE = re.compile(
    r"""^[ \t]*!\[(?P<alt>[^\]]*)\]\((?P<url>[^)\s]+)(?:\s+"[^"]*")?\)[ \t]*$\n?""",
    re.MULTILINE,
)


def _opencli_bin() -> list[str]:
    """Return the argv prefix for invoking OpenCLI.

    `OPENCLI_BIN` is required and may point either at a node entrypoint
    (`/path/to/opencli/dist/src/main.js`) or a wrapper script. The former is
    detected by the `.js` suffix and invoked through `node`.
    """
    value = env("OPENCLI_BIN", hint="set to the opencli main.js path or a wrapper script")
    if value.endswith(".js"):
        return ["node", value]
    return [value]


def _strip_fragment(url: str) -> str:
    return url.split("#", 1)[0]


def _unique_image_urls(markdown: str) -> list[str]:
    """Return base URLs of markdown `![]()` refs in document order, deduped."""
    seen: set[str] = set()
    ordered: list[str] = []
    for match in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", markdown):
        base = _strip_fragment(match.group(1))
        if base in seen:
            continue
        seen.add(base)
        ordered.append(base)
    return ordered


def _index_image_files(images_dir: Path) -> dict[int, Path]:
    """Map 1-indexed slot number (from `img_NNN.ext`) → file path."""
    slots: dict[int, Path] = {}
    if not images_dir.is_dir():
        return slots
    for path in images_dir.iterdir():
        match = re.fullmatch(r"img_(\d+)\.[A-Za-z0-9]+", path.name)
        if not match:
            continue
        slots[int(match.group(1))] = path
    return slots


def rewrite_image_links(markdown: str, images_dir: Path) -> tuple[str, list[str]]:
    """Rewrite remote `![]()` URLs to `images/img_NNN.<ext>` for downloaded images.

    Failed-download slots (no file present) get their entire markdown image
    line deleted. Returns the rewritten markdown plus a list of warnings about
    skipped slots (caller decides how loud to make them).
    """
    unique_urls = _unique_image_urls(markdown)
    slots = _index_image_files(images_dir)

    rewrites: dict[str, str] = {}
    drops: set[str] = set()
    warnings: list[str] = []

    for position, base_url in enumerate(unique_urls, start=1):
        path = slots.get(position)
        if path is None:
            drops.add(base_url)
            warnings.append(f"opencli skipped image #{position} (url={base_url})")
            continue
        rewrites[base_url] = f"images/{path.name}"

    def replace_or_drop(match: re.Match[str]) -> str:
        url = match.group("url")
        base = _strip_fragment(url)
        if base in drops:
            return ""
        local = rewrites.get(base)
        if local is None:
            return match.group(0)
        alt = match.group("alt")
        return f"![{alt}]({local})\n"

    rewritten = _IMG_LINE_RE.sub(replace_or_drop, markdown)
    # Squash any extra blank lines a drop may have introduced.
    rewritten = re.sub(r"\n{3,}", "\n\n", rewritten)
    return rewritten, warnings


def opencli_weixin_download(url: str, output_dir: Path | str) -> dict[str, Any]:
    """Download a WeChat article through OpenCLI and rewrite image links.

    Returns a dict with the parsed metadata plus `markdown` (image-rewritten,
    body only — no frontmatter prepended), `saved_md` (path to the original md
    on disk for raw archival), and `assets_dir` (the per-article `images/`
    folder, or None if the article had no images).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        *_opencli_bin(),
        "weixin", "download",
        "--url", url,
        "--output", str(output_dir),
        "--download-images", "true",
        "-f", "json",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_DOWNLOAD_TIMEOUT,
            check=False,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"opencli weixin download timed out after {e.timeout}s") from e

    if result.returncode != 0:
        raise RuntimeError(
            f"opencli weixin download failed (rc={result.returncode}): "
            f"{(result.stderr or result.stdout).strip()[:1000]}"
        )

    try:
        records = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"opencli returned non-JSON output: {result.stdout[:500]}") from e

    if not records:
        raise RuntimeError("opencli weixin download returned no records")
    record = records[0]
    status = str(record.get("status") or "")
    if not status.startswith("success"):
        raise RuntimeError(f"opencli weixin download status={status!r}: {record}")

    saved_md = Path(record["saved"])
    if not saved_md.is_file():
        raise RuntimeError(f"opencli reported saved path missing: {saved_md}")

    raw_markdown = saved_md.read_text(encoding="utf-8")
    images_dir = saved_md.parent / "images"
    rewritten_md, warnings = rewrite_image_links(raw_markdown, images_dir)
    for warning in warnings:
        logger.warning(warning)

    # Strip the simple `# title / > 公众号 / > 发布时间 / > 原文链接 / --- / # title` preamble
    # that opencli writes, so downstream sees only the article body. Title +
    # account + publish_time are already returned as structured fields.
    body = _strip_opencli_preamble(rewritten_md)

    return to_jsonable(
        {
            "title": record.get("title"),
            "account": record.get("author"),
            "publish_time": record.get("publish_time"),
            "markdown": body,
            "saved_md": saved_md,
            "assets_dir": images_dir if images_dir.is_dir() else None,
            "image_warnings": warnings,
        }
    )


def _strip_opencli_preamble(markdown: str) -> str:
    """Remove opencli's frontmatter-style header so downstream sees only body."""
    lines = markdown.splitlines()
    # opencli emits: H1 title, then 3 quote lines, blank, `---`, blank, H1 title.
    # Skip up to and including the second H1 occurrence if it matches the first.
    if not lines or not lines[0].startswith("# "):
        return markdown
    first_h1 = lines[0]
    for index, line in enumerate(lines[1:8], start=1):
        if line == first_h1 and 0 < index < 12:
            return "\n".join(lines[index + 1:]).lstrip("\n")
    return markdown


def cleanup_opencli_output(output_dir: Path | str) -> None:
    """Best-effort cleanup of a temp output directory used for a one-shot call."""
    path = Path(output_dir)
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def make_tempdir(prefix: str = "opencli-weixin-") -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))
