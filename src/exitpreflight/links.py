"""Extract and classify references that can make an export non-portable."""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse

TEXT_EXTENSIONS = {
    ".md",
    ".markdown",
    ".html",
    ".htm",
    ".txt",
    ".csv",
}

CLOUD_HOST_SUFFIXES = (
    "drive.google.com",
    "docs.google.com",
    "notion.so",
    "notion.site",
    "dropbox.com",
    "dropboxusercontent.com",
    "1drv.ms",
    "onedrive.live.com",
    "sharepoint.com",
    "box.com",
    "slack.com",
    "slack-files.com",
    "files.slack.com",
    "discordapp.com",
    "discord.com",
    "figma.com",
    "canva.com",
)

SIGNED_QUERY_KEYS = {
    "x-amz-signature",
    "x-amz-expires",
    "x-goog-signature",
    "x-goog-expires",
    "expires",
    "signature",
    "sig",
    "se",
    "token",
}

MARKDOWN_LINK_RE = re.compile(r"(!?)\[[^\]]*\]\(([^)]+)\)")
PLAIN_URL_RE = re.compile(r"https?://[^\s<>\]\[\"']+")


@dataclass(frozen=True)
class Reference:
    source_path: str
    target: str
    line: int
    kind: str
    is_image: bool = False


class _HTMLReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[tuple[str, str, int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_name = "src" if tag in {"img", "audio", "video", "source"} else "href"
        for name, value in attrs:
            if name.casefold() == attr_name and value:
                self.references.append((value, tag, self.getpos()[0]))


def _clean_markdown_target(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        return value[1 : value.index(">")]
    match = re.match(r"([^\s]+)(?:\s+[\"'].*[\"'])?$", value)
    return match.group(1) if match else value


def extract_references(path: str, text: str) -> list[Reference]:
    found: list[Reference] = []
    seen: set[tuple[str, int, str]] = set()

    for match in MARKDOWN_LINK_RE.finditer(text):
        target = _clean_markdown_target(match.group(2))
        line = text.count("\n", 0, match.start()) + 1
        key = (target, line, "markdown")
        if key not in seen:
            seen.add(key)
            found.append(Reference(path, target, line, "markdown", is_image=bool(match.group(1))))

    if path.casefold().endswith((".html", ".htm")):
        parser = _HTMLReferenceParser()
        parser.feed(text)
        for target, tag, line in parser.references:
            key = (target, line, "html")
            if key not in seen:
                seen.add(key)
                found.append(
                    Reference(path, target, line, "html", is_image=tag in {"img", "source"})
                )

    for match in PLAIN_URL_RE.finditer(text):
        target = match.group(0).rstrip(".,);:")
        line = text.count("\n", 0, match.start()) + 1
        if any(existing.target == target and existing.line == line for existing in found):
            continue
        found.append(Reference(path, target, line, "url"))
    return found


def classify_reference(target: str) -> str:
    stripped = target.strip()
    lowered = stripped.casefold()
    if not stripped or lowered.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
        return "ignored"
    parsed = urlparse(stripped)
    if parsed.scheme in {"http", "https"}:
        host = (parsed.hostname or "").casefold()
        query_keys = {key.casefold() for key in parse_qs(parsed.query, keep_blank_values=True)}
        if query_keys & SIGNED_QUERY_KEYS:
            return "signed"
        if any(host == suffix or host.endswith("." + suffix) for suffix in CLOUD_HOST_SUFFIXES):
            return "cloud"
        return "external"
    if parsed.scheme and parsed.scheme != "file":
        return "external"
    return "local"


def resolve_local_reference(source_path: str, target: str) -> str:
    parsed = urlparse(target)
    raw_path = unquote(parsed.path).replace("\\", "/")
    if raw_path.startswith("/"):
        return posixpath.normpath(raw_path.lstrip("/"))
    parent = posixpath.dirname(source_path)
    return posixpath.normpath(posixpath.join(parent, raw_path))
