"""Portable SHA-256 manifest creation and verification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .models import FileRecord
from .source import ExportSource, SourceError

MANIFEST_RE = re.compile(r"^([0-9a-fA-F]{64})  (.+)$")


@dataclass(frozen=True)
class ManifestVerification:
    checked: int
    missing: list[str]
    mismatched: list[str]
    unexpected: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing and not self.mismatched


def render_manifest(records: list[FileRecord]) -> str:
    return "".join(
        f"{record.sha256}  {record.path}\n"
        for record in sorted(records, key=lambda item: item.path.casefold())
    )


def parse_manifest(path: str | Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        match = MANIFEST_RE.match(line)
        if not match:
            raise SourceError(f"Invalid manifest line {line_number}: {line}")
        digest, name = match.groups()
        if name in values:
            raise SourceError(f"Duplicate manifest path on line {line_number}: {name}")
        values[name] = digest.casefold()
    return values


def verify_manifest(input_path: str | Path, manifest_path: str | Path) -> ManifestVerification:
    expected = parse_manifest(manifest_path)
    with ExportSource(input_path) as source:
        actual_names = set(source.names())
        missing = sorted(set(expected) - actual_names, key=str.casefold)
        unexpected = sorted(actual_names - set(expected), key=str.casefold)
        mismatched = sorted(
            (
                name
                for name in set(expected) & actual_names
                if source.hash(name).casefold() != expected[name]
            ),
            key=str.casefold,
        )
    return ManifestVerification(
        checked=len(expected) - len(missing),
        missing=missing,
        mismatched=mismatched,
        unexpected=unexpected,
    )
