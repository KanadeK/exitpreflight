#!/usr/bin/env python3
"""Build deterministic source/zipapp assets plus wheel and sdist."""

from __future__ import annotations

import argparse
import gzip
import io
import os
import re
import subprocess
import sys
import tarfile
import time
import zipfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "src" / "exitpreflight"
EXCLUDED_PARTS = {
    ".git",
    ".coverage",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "exitpreflight-demo",
    "exitpreflight-output",
    "exitpreflight.egg-info",
    "release-check",
}


def version() -> str:
    text = (PACKAGE_ROOT / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise RuntimeError("Unable to read package version.")
    return match.group(1)


def source_date_epoch() -> int:
    return int(os.environ.get("SOURCE_DATE_EPOCH", "1767225600"))


def zip_timestamp(epoch: int) -> tuple[int, int, int, int, int, int]:
    minimum = datetime(1980, 1, 1, tzinfo=UTC).timestamp()
    return time.gmtime(max(epoch, int(minimum)))[:6]


def write_deterministic_zip(path: Path, entries: list[tuple[str, bytes]], epoch: int) -> None:
    timestamp = zip_timestamp(epoch)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for archive_name, data in sorted(entries, key=lambda item: item[0].casefold()):
            info = zipfile.ZipInfo(archive_name, date_time=timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            output.writestr(info, data)


def normalize_sdist(path: Path, epoch: int) -> None:
    """Rewrite build's sdist with stable tar and gzip metadata."""
    entries: list[tuple[tarfile.TarInfo, bytes | None]] = []
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            stream = archive.extractfile(member) if member.isfile() else None
            data = stream.read() if stream is not None else None
            member.mtime = epoch
            member.uid = 0
            member.gid = 0
            member.uname = ""
            member.gname = ""
            member.mode = 0o755 if member.isdir() else 0o644
            member.pax_headers = {}
            entries.append((member, data))

    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("wb") as raw:
            with gzip.GzipFile(
                filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=epoch
            ) as compressed:
                with tarfile.open(
                    fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT
                ) as output:
                    for member, data in entries:
                        output.addfile(member, io.BytesIO(data) if data is not None else None)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def package_entries() -> list[tuple[str, bytes]]:
    entries = [
        (
            "__main__.py",
            b"from exitpreflight.cli import main\nraise SystemExit(main())\n",
        )
    ]
    for path in sorted(PACKAGE_ROOT.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        relative = path.relative_to(PACKAGE_ROOT).as_posix()
        entries.append((f"exitpreflight/{relative}", path.read_bytes()))
    return entries


def tracked_files() -> list[Path]:
    probe = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--verify", "HEAD"],
        capture_output=True,
        check=False,
    )
    if probe.returncode == 0:
        completed = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z"],
            capture_output=True,
            check=True,
        )
        return [ROOT / item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
        and path.suffix not in {".pyc", ".pyo"}
    ]


def source_entries(release_version: str) -> list[tuple[str, bytes]]:
    prefix = f"exitpreflight-{release_version}"
    return [
        (f"{prefix}/{path.relative_to(ROOT).as_posix()}", path.read_bytes())
        for path in tracked_files()
    ]


def digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def clean_known_assets(output: Path, release_version: str) -> None:
    names = {
        f"exitpreflight-{release_version}.pyz",
        f"exitpreflight-{release_version}-source.zip",
        "SHA256SUMS",
    }
    for path in output.iterdir() if output.exists() else []:
        if (
            path.name in names
            or path.match(f"exitpreflight-{release_version}*.whl")
            or path.match(f"exitpreflight-{release_version}*.tar.gz")
        ):
            path.unlink()


def build(output: Path) -> list[Path]:
    release_version = version()
    epoch = source_date_epoch()
    output.mkdir(parents=True, exist_ok=True)
    clean_known_assets(output, release_version)

    pyz = output / f"exitpreflight-{release_version}.pyz"
    source_zip = output / f"exitpreflight-{release_version}-source.zip"
    write_deterministic_zip(pyz, package_entries(), epoch)
    write_deterministic_zip(source_zip, source_entries(release_version), epoch)

    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = str(epoch)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--wheel",
            "--sdist",
            "--outdir",
            str(output),
            str(ROOT),
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )
    sdists = list(output.glob(f"exitpreflight-{release_version}*.tar.gz"))
    if len(sdists) != 1:
        raise RuntimeError("Expected exactly one sdist from the package build.")
    normalize_sdist(sdists[0], epoch)
    assets = sorted(
        [path for path in output.iterdir() if path.is_file() and path.name != "SHA256SUMS"],
        key=lambda item: item.name.casefold(),
    )
    checksums = output / "SHA256SUMS"
    checksums.write_text(
        "".join(f"{digest(path)}  {path.name}\n" for path in assets), encoding="utf-8", newline="\n"
    )
    return [*assets, checksums]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args(argv)
    assets = build(args.output.resolve())
    print("Release assets:")
    for path in assets:
        print(f"  {path.name} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
