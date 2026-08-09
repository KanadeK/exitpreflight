"""Safe, read-only access to directories and common export archives."""

from __future__ import annotations

import io
import re
import tarfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import IO

from .models import Finding, Severity


class SourceError(RuntimeError):
    """Raised when an input cannot be safely opened as an export source."""


@dataclass(frozen=True)
class SourceEntry:
    path: str
    raw_path: str
    size: int
    kind: str


def _normalize_member_path(raw_path: str) -> tuple[str, bool]:
    candidate = raw_path.replace("\\", "/")
    unsafe = bool(candidate.startswith("/") or re.match(r"^[A-Za-z]:", candidate))
    parts: list[str] = []
    for part in PurePosixPath(candidate).parts:
        if part in {"", ".", "/"}:
            continue
        if part == "..":
            unsafe = True
            if parts:
                parts.pop()
            continue
        parts.append(part)
    normalized = "/".join(parts)
    return normalized, unsafe or not normalized


class ExportSource:
    """A normalized view over a directory, ZIP, TAR, or compressed TAR export."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_entries: int = 250_000,
        max_total_size: int = 512 * 1024 * 1024 * 1024,
    ) -> None:
        self.path = Path(path).expanduser().resolve()
        self.max_entries = max_entries
        self.max_total_size = max_total_size
        self.kind = ""
        self.entries: dict[str, SourceEntry] = {}
        self.structural_findings: list[Finding] = []
        self._zip: zipfile.ZipFile | None = None
        self._tar: tarfile.TarFile | None = None

    def __enter__(self) -> ExportSource:
        if not self.path.exists():
            raise SourceError(f"Input does not exist: {self.path}")
        if self.path.is_dir():
            self.kind = "directory"
            self._load_directory()
        elif zipfile.is_zipfile(self.path):
            self.kind = "zip"
            self._zip = zipfile.ZipFile(self.path, "r")
            self._load_zip()
        elif tarfile.is_tarfile(self.path):
            self.kind = "tar"
            self._tar = tarfile.open(self.path, "r:*")
            self._load_tar()
        else:
            raise SourceError(
                "Unsupported input. Use a directory, .zip, .tar, .tar.gz, or .tgz export."
            )
        self._validate_limits()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._zip is not None:
            self._zip.close()
        if self._tar is not None:
            self._tar.close()

    def _add_entry(self, entry: SourceEntry, *, unsafe: bool = False) -> None:
        if unsafe:
            self.structural_findings.append(
                Finding(
                    code="archive-unsafe-path",
                    title="Archive contains an unsafe path",
                    severity=Severity.CRITICAL,
                    summary="An archive member is absolute or attempts parent-directory traversal.",
                    path=entry.raw_path,
                    repair="Recreate the export and do not extract this archive with an unsafe extractor.",
                )
            )
            return
        if entry.path in self.entries:
            self.structural_findings.append(
                Finding(
                    code="archive-duplicate-path",
                    title="Archive contains duplicate normalized paths",
                    severity=Severity.CRITICAL,
                    summary="Two members resolve to the same portable path, so extraction is ambiguous.",
                    path=entry.path,
                    repair="Recreate the export or keep a verified copy of each colliding member.",
                )
            )
            return
        folded = entry.path.casefold()
        collision = next(
            (existing for existing in self.entries if existing.casefold() == folded), None
        )
        if collision is not None:
            self.structural_findings.append(
                Finding(
                    code="archive-case-collision",
                    title="Paths collide on case-insensitive filesystems",
                    severity=Severity.HIGH,
                    summary=f"'{collision}' and '{entry.path}' cannot coexist reliably on Windows/macOS.",
                    path=entry.path,
                    target=collision,
                    repair="Rename one source item before exporting, then create and audit a fresh export.",
                )
            )
        self.entries[entry.path] = entry

    def _load_directory(self) -> None:
        for child in sorted(self.path.rglob("*"), key=lambda item: item.as_posix().casefold()):
            relative = child.relative_to(self.path).as_posix()
            if child.is_symlink():
                self.structural_findings.append(
                    Finding(
                        code="directory-symlink",
                        title="Export contains a symbolic link",
                        severity=Severity.HIGH,
                        summary="A symbolic link may point outside the export and is not self-contained.",
                        path=relative,
                        repair="Replace the link with a real copy if the target must survive account deletion.",
                    )
                )
                continue
            if child.is_file():
                normalized, unsafe = _normalize_member_path(relative)
                self._add_entry(
                    SourceEntry(normalized, relative, child.stat().st_size, "directory"),
                    unsafe=unsafe,
                )

    def _load_zip(self) -> None:
        assert self._zip is not None
        for info in self._zip.infolist():
            if info.is_dir():
                continue
            normalized, unsafe = _normalize_member_path(info.filename)
            entry = SourceEntry(normalized, info.filename, info.file_size, "zip")
            self._add_entry(entry, unsafe=unsafe)
            if info.file_size > 1024 * 1024 and info.file_size / max(info.compress_size, 1) > 250:
                self.structural_findings.append(
                    Finding(
                        code="archive-extreme-compression",
                        title="Archive member has an extreme compression ratio",
                        severity=Severity.HIGH,
                        summary="The member may consume unexpectedly large resources when extracted.",
                        path=normalized,
                        repair="Inspect the member in an isolated environment or request a new export.",
                        metadata={"uncompressed_bytes": info.file_size},
                    )
                )

    def _load_tar(self) -> None:
        assert self._tar is not None
        for member in self._tar.getmembers():
            normalized, unsafe = _normalize_member_path(member.name)
            if member.issym() or member.islnk():
                self.structural_findings.append(
                    Finding(
                        code="archive-link-entry",
                        title="Archive contains a link entry",
                        severity=Severity.HIGH,
                        summary="Archive links can escape the export or depend on an absent target.",
                        path=member.name,
                        target=member.linkname,
                        repair="Replace links with regular files before treating the export as portable.",
                    )
                )
                continue
            if not member.isfile():
                continue
            self._add_entry(SourceEntry(normalized, member.name, member.size, "tar"), unsafe=unsafe)

    def _validate_limits(self) -> None:
        if len(self.entries) > self.max_entries:
            raise SourceError(
                f"Export has {len(self.entries)} files, above the safety limit of {self.max_entries}."
            )
        total_size = sum(entry.size for entry in self.entries.values())
        if total_size > self.max_total_size:
            raise SourceError(
                f"Export expands to {total_size} bytes, above the safety limit of {self.max_total_size}."
            )

    def names(self) -> list[str]:
        return sorted(self.entries, key=str.casefold)

    @contextmanager
    def open_binary(self, name: str) -> Iterator[IO[bytes]]:
        entry = self.entries[name]
        stream: IO[bytes]
        if entry.kind == "directory":
            stream = (self.path / Path(entry.raw_path)).open("rb")
        elif entry.kind == "zip":
            assert self._zip is not None
            stream = self._zip.open(entry.raw_path, "r")
        else:
            assert self._tar is not None
            extracted = self._tar.extractfile(entry.raw_path)
            if extracted is None:
                raise SourceError(f"Unable to read archive member: {entry.raw_path}")
            stream = extracted
        try:
            yield stream
        finally:
            stream.close()

    def read_bytes(self, name: str, *, limit: int = 8 * 1024 * 1024) -> bytes:
        with self.open_binary(name) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise SourceError(f"Text parsing limit exceeded for {name} ({limit} bytes).")
        return data

    def read_text(self, name: str, *, limit: int = 8 * 1024 * 1024) -> str:
        data = self.read_bytes(name, limit=limit)
        for encoding in ("utf-8-sig", "utf-16", "utf-8"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    def hash(self, name: str) -> str:
        digest = sha256()
        with self.open_binary(name) as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    def test_integrity(self) -> list[Finding]:
        if self._zip is None:
            return []
        bad_member = self._zip.testzip()
        if bad_member is None:
            return []
        return [
            Finding(
                code="archive-crc-failure",
                title="ZIP integrity check failed",
                severity=Severity.CRITICAL,
                summary="At least one ZIP member does not match its stored CRC.",
                path=bad_member,
                repair="Download or generate the export again before deleting the source account.",
            )
        ]

    def basename_matches(self, filename: str) -> list[str]:
        wanted = filename.casefold()
        return [name for name in self.names() if PurePosixPath(name).name.casefold() == wanted]


def binary_stream(data: bytes) -> IO[bytes]:
    """Small test helper that exposes bytes as a binary stream."""

    return io.BytesIO(data)
