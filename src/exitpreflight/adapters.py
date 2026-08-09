"""Format detection and service-specific recoverability checks."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from pathlib import PurePosixPath
from typing import Any

from .links import classify_reference, extract_references, resolve_local_reference
from .models import Finding, Severity
from .source import ExportSource, SourceError

NOTION_ID_RE = re.compile(r"(?:^|\s)[0-9a-f]{32}(?:_all)?$", re.IGNORECASE)
SLACK_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")


@dataclass
class AuditAccumulator:
    metrics: Counter[str] = field(default_factory=Counter)
    findings: list[Finding] = field(default_factory=list)
    max_findings_per_code: int = 60
    _code_counts: Counter[str] = field(default_factory=Counter)

    def add(self, finding: Finding) -> None:
        self._code_counts[finding.code] += 1
        if self._code_counts[finding.code] <= self.max_findings_per_code:
            self.findings.append(finding)
        else:
            self.metrics[f"suppressed.{finding.code}"] += 1


def detect_adapters(source: ExportSource) -> list[str]:
    names = source.names()
    basenames = {PurePosixPath(name).name.casefold() for name in names}
    adapters = ["generic"]
    if {"channels.json", "users.json"}.issubset(basenames):
        adapters.append("slack")
    if any(name.casefold().endswith(".mbox") for name in names):
        adapters.append("gmail")
    notion_signals = sum(
        1
        for name in names
        if PurePosixPath(name).suffix.casefold() in {".md", ".html", ".csv"}
        and NOTION_ID_RE.search(PurePosixPath(name).stem)
    )
    if notion_signals or any(
        "notion" in part.casefold() for name in names for part in PurePosixPath(name).parts
    ):
        adapters.append("notion")
    return adapters


def audit_generic(source: ExportSource, acc: AuditAccumulator) -> None:
    names = source.names()
    exact = set(names)
    folded = {name.casefold(): name for name in names}
    acc.metrics["files.total"] = len(names)
    acc.metrics["bytes.total"] = sum(source.entries[name].size for name in names)

    for name in names:
        entry = source.entries[name]
        if entry.size == 0 and PurePosixPath(name).name not in {".gitkeep", ".keep"}:
            acc.metrics["files.zero_bytes"] += 1
            acc.add(
                Finding(
                    code="zero-byte-file",
                    title="Export contains an empty file",
                    severity=Severity.LOW,
                    summary="The file is zero bytes; confirm that it is intentionally empty.",
                    path=name,
                    repair="Open the source item, then regenerate the export if content is missing.",
                )
            )
        suffix = PurePosixPath(name).suffix.casefold()
        if suffix not in {".md", ".markdown", ".html", ".htm", ".txt", ".csv"}:
            continue
        try:
            text = source.read_text(name)
        except SourceError:
            acc.metrics["text.skipped_large"] += 1
            continue
        for reference in extract_references(name, text):
            classification = classify_reference(reference.target)
            if classification == "ignored" or classification == "external":
                continue
            if classification in {"cloud", "signed"}:
                acc.metrics[f"links.{classification}"] += 1
                acc.add(
                    Finding(
                        code="signed-url-dependency"
                        if classification == "signed"
                        else "cloud-link-dependency",
                        title=(
                            "Export depends on an expiring or signed URL"
                            if classification == "signed"
                            else "Export still depends on cloud-hosted content"
                        ),
                        severity=Severity.HIGH,
                        summary="The referenced content is not proven to exist inside this export.",
                        path=name,
                        target=reference.target,
                        repair="Download the target while access still works, store it locally, and update the reference.",
                        metadata={"line": reference.line, "kind": reference.kind},
                    )
                )
                continue
            resolved = resolve_local_reference(name, reference.target)
            acc.metrics["links.local"] += 1
            if resolved in exact:
                continue
            if resolved.casefold() in folded:
                acc.add(
                    Finding(
                        code="local-link-case-mismatch",
                        title="Local reference differs only by letter case",
                        severity=Severity.MEDIUM,
                        summary="The link may work on Windows but fail on case-sensitive systems.",
                        path=name,
                        target=reference.target,
                        repair=f"Change the reference to the exact exported path: {folded[resolved.casefold()]}",
                        metadata={"line": reference.line},
                    )
                )
                continue
            acc.metrics["links.broken_local"] += 1
            acc.add(
                Finding(
                    code="missing-local-target",
                    title="Local reference has no exported target",
                    severity=Severity.HIGH if reference.is_image else Severity.MEDIUM,
                    summary="A document points to a local file that is absent from the export.",
                    path=name,
                    target=reference.target,
                    repair="Recover the missing target from the source service and regenerate the export.",
                    metadata={"line": reference.line, "resolved_path": resolved},
                )
            )


def _load_json(source: ExportSource, name: str, acc: AuditAccumulator) -> Any | None:
    try:
        return json.loads(source.read_text(name, limit=32 * 1024 * 1024))
    except (json.JSONDecodeError, SourceError) as exc:
        acc.add(
            Finding(
                code="invalid-json",
                title="Export contains unreadable JSON",
                severity=Severity.HIGH,
                summary=str(exc),
                path=name,
                repair="Download or generate the export again, then compare counts with this copy.",
            )
        )
        return None


def audit_slack(source: ExportSource, acc: AuditAccumulator) -> None:
    channel_files = source.basename_matches("channels.json")
    user_files = source.basename_matches("users.json")
    if not channel_files or not user_files:
        return
    channels_value = _load_json(source, channel_files[0], acc)
    users_value = _load_json(source, user_files[0], acc)
    channels = channels_value if isinstance(channels_value, list) else []
    users = users_value if isinstance(users_value, list) else []
    user_ids = {str(item.get("id")) for item in users if isinstance(item, dict) and item.get("id")}
    channel_names = {
        str(item.get("name")) for item in channels if isinstance(item, dict) and item.get("name")
    }
    acc.metrics["slack.channels"] = len(channels)
    acc.metrics["slack.users"] = len(users)

    parents = {str(PurePosixPath(name).parent) for name in source.names()}
    root = str(PurePosixPath(channel_files[0]).parent)
    for channel in sorted(channel_names):
        expected = str(PurePosixPath(root, channel)) if root != "." else channel
        if expected not in parents:
            acc.add(
                Finding(
                    code="slack-channel-folder-missing",
                    title="Slack channel metadata has no message folder",
                    severity=Severity.MEDIUM,
                    summary="The channel exists in channels.json but no corresponding export folder was found.",
                    path=channel_files[0],
                    target=channel,
                    repair="Check the export date range, retention policy, and scope before deleting the workspace.",
                )
            )

    metadata_basenames = {
        "channels.json",
        "users.json",
        "groups.json",
        "dms.json",
        "mpims.json",
        "integration_logs.json",
        "canvases.json",
    }
    for name in source.names():
        basename = PurePosixPath(name).name.casefold()
        if basename in metadata_basenames or not SLACK_DAY_RE.match(basename):
            continue
        value = _load_json(source, name, acc)
        if not isinstance(value, list):
            continue
        for message in value:
            if not isinstance(message, dict):
                continue
            acc.metrics["slack.messages"] += 1
            user = message.get("user")
            if user and str(user) not in user_ids:
                acc.metrics["slack.unknown_users"] += 1
                acc.add(
                    Finding(
                        code="slack-user-reference-missing",
                        title="Slack message references an unknown user",
                        severity=Severity.MEDIUM,
                        summary="The user ID is absent from users.json, reducing message context.",
                        path=name,
                        target=str(user),
                        repair="Confirm the export scope and preserve a member directory before account deletion.",
                    )
                )
            files = message.get("files")
            if not isinstance(files, list):
                continue
            for file_value in files:
                if not isinstance(file_value, dict):
                    continue
                acc.metrics["slack.file_links"] += 1
                target = str(
                    file_value.get("url_private_download")
                    or file_value.get("url_private")
                    or file_value.get("permalink")
                    or ""
                )
                if target:
                    acc.add(
                        Finding(
                            code="slack-file-link-only",
                            title="Slack export contains a file link, not the file",
                            severity=Severity.HIGH,
                            summary="This attachment may become inaccessible after workspace deletion or retention expiry.",
                            path=name,
                            target=target,
                            repair="Download the file while authenticated and store it beside the audited export.",
                            metadata={"file_id": str(file_value.get("id", ""))},
                        )
                    )


def _iter_mbox_messages(source: ExportSource, name: str) -> Iterator[tuple[bytes, bool]]:
    with source.open_binary(name) as stream:
        current = bytearray()
        truncated = False
        saw_boundary = False
        for line in stream:
            if line.startswith(b"From "):
                if saw_boundary and current:
                    yield bytes(current), truncated
                    current.clear()
                    truncated = False
                saw_boundary = True
                continue
            if not saw_boundary and not current and line.strip():
                saw_boundary = True
            if len(current) + len(line) <= 64 * 1024 * 1024:
                current.extend(line)
            else:
                truncated = True
        if current:
            yield bytes(current), truncated


def _message_text(message: Any) -> str:
    parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() not in {"text/plain", "text/html"}:
                continue
            try:
                parts.append(str(part.get_content()))
            except (LookupError, UnicodeError):
                payload = part.get_payload(decode=True) or b""
                parts.append(payload.decode("utf-8", errors="replace"))
    else:
        try:
            parts.append(str(message.get_content()))
        except (LookupError, UnicodeError):
            payload = message.get_payload(decode=True) or b""
            parts.append(payload.decode("utf-8", errors="replace"))
    return "\n".join(parts)


def audit_gmail(source: ExportSource, acc: AuditAccumulator) -> None:
    mbox_names = [name for name in source.names() if name.casefold().endswith(".mbox")]
    parser = BytesParser(policy=policy.default)
    for name in mbox_names:
        message_count = 0
        for raw, truncated in _iter_mbox_messages(source, name):
            message_count += 1
            if truncated:
                acc.add(
                    Finding(
                        code="mbox-message-too-large",
                        title="An MBOX message exceeded the parsing safety limit",
                        severity=Severity.HIGH,
                        summary="The message was counted but only partially inspected.",
                        path=name,
                        repair="Open this MBOX in a trusted mail client and verify the oversized message manually.",
                    )
                )
            try:
                message = parser.parsebytes(raw)
            except Exception as exc:  # email parser failures vary by malformed input
                acc.add(
                    Finding(
                        code="mbox-message-unreadable",
                        title="An MBOX message could not be parsed",
                        severity=Severity.HIGH,
                        summary=str(exc),
                        path=name,
                        repair="Regenerate the Gmail export or preserve this MBOX for manual recovery.",
                        metadata={"message_index": message_count},
                    )
                )
                continue
            if message.get("X-Gmail-Labels"):
                acc.metrics["gmail.messages_with_labels"] += 1
            attachments = sum(
                1
                for part in message.walk()
                if part.get_content_disposition() == "attachment" or part.get_filename()
            )
            acc.metrics["gmail.attachments"] += attachments
            for reference in extract_references(name, _message_text(message)):
                classification = classify_reference(reference.target)
                if classification not in {"cloud", "signed"}:
                    continue
                acc.metrics[f"gmail.links.{classification}"] += 1
                acc.add(
                    Finding(
                        code="gmail-cloud-only-reference",
                        title="Email points to content that is not embedded in the MBOX",
                        severity=Severity.HIGH,
                        summary="The link may stop working after the related cloud account or sharing grant is removed.",
                        path=name,
                        target=reference.target,
                        repair="Download the linked content now and record which message referenced it.",
                        metadata={"message_index": message_count},
                    )
                )
        acc.metrics["gmail.messages"] += message_count
        if source.entries[name].size and message_count == 0:
            acc.add(
                Finding(
                    code="mbox-no-messages",
                    title="Non-empty MBOX contains no parseable messages",
                    severity=Severity.CRITICAL,
                    summary="The file is not recoverable as a normal MBOX stream.",
                    path=name,
                    repair="Request a fresh Gmail export before deleting the source account.",
                )
            )
    if acc.metrics["gmail.messages"] and not acc.metrics["gmail.messages_with_labels"]:
        acc.add(
            Finding(
                code="gmail-labels-missing",
                title="No Gmail label headers were found",
                severity=Severity.MEDIUM,
                summary="Messages are present, but their Gmail folder/label organization may be absent.",
                path=mbox_names[0],
                repair="Confirm the export came from Google Takeout and inspect X-Gmail-Labels headers.",
            )
        )
    takeout_like = any(
        "takeout" in part.casefold()
        for name in source.names()
        for part in PurePosixPath(name).parts
    )
    if takeout_like and not source.basename_matches("archive_browser.html"):
        acc.add(
            Finding(
                code="takeout-browser-missing",
                title="Google Takeout archive browser is missing",
                severity=Severity.MEDIUM,
                summary="The expected format guide/index was not found in this Takeout-like export.",
                repair="Check that every split archive part was downloaded and extracted together.",
            )
        )


def audit_notion(source: ExportSource, acc: AuditAccumulator) -> None:
    title_paths: dict[str, str] = {}
    for name in source.names():
        path = PurePosixPath(name)
        suffix = path.suffix.casefold()
        if suffix in {".md", ".html", ".htm"}:
            acc.metrics["notion.pages"] += 1
        elif suffix == ".csv":
            acc.metrics["notion.databases"] += 1
        else:
            continue
        title = re.sub(r"\s+[0-9a-f]{32}(?:_all)?$", "", path.stem, flags=re.IGNORECASE)
        key = title.casefold()
        if key in title_paths and title_paths[key] != name:
            acc.add(
                Finding(
                    code="notion-duplicate-title",
                    title="Notion pages collapse to the same human title",
                    severity=Severity.MEDIUM,
                    summary="Removing Notion IDs would make these page names ambiguous.",
                    path=name,
                    target=title_paths[key],
                    repair="Keep stable IDs in filenames or create an explicit page-name mapping before migration.",
                )
            )
        else:
            title_paths[key] = name


def run_adapters(source: ExportSource, adapters: list[str], acc: AuditAccumulator) -> None:
    audit_generic(source, acc)
    if "slack" in adapters:
        audit_slack(source, acc)
    if "gmail" in adapters:
        audit_gmail(source, acc)
    if "notion" in adapters:
        audit_notion(source, acc)
