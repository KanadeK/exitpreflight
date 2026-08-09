#!/usr/bin/env python3
"""Release preflight: gates, reproducibility, clean install, and author hygiene."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import venv
import zipfile
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_IDENTITY = ("KanadeK", "121669563+KanadeK@users.noreply.github.com")
REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "RELEASE_NOTES.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "docs/ACCEPTANCE.md",
    "docs/REPAIR.md",
    "docs/THREAT_MODEL.md",
    "docs/RESEARCH.md",
    "schema/report.schema.json",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
]


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=capture,
        check=False,
        env={**os.environ, "SOURCE_DATE_EPOCH": "1767225600"},
    )


def file_digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def check_version() -> str:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    expected = str(project["project"]["version"])
    namespace: dict[str, str] = {}
    for line in (ROOT / "src/exitpreflight/__init__.py").read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            namespace["version"] = line.split("=", 1)[1].strip().strip('"')
            break
    if namespace.get("version") != expected:
        raise RuntimeError(
            f"Version mismatch: pyproject={expected}, package={namespace.get('version')}"
        )
    for path in (ROOT / "CHANGELOG.md", ROOT / "RELEASE_NOTES.md"):
        if expected not in path.read_text(encoding="utf-8"):
            raise RuntimeError(f"Version {expected} missing from {path.name}")
    return expected


def check_required_files() -> None:
    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        raise RuntimeError("Missing release files: " + ", ".join(missing))


def check_git(require_clean: bool) -> None:
    head = run(["git", "rev-parse", "--verify", "HEAD"], capture=True)
    if head.returncode != 0:
        if require_clean:
            raise RuntimeError("Repository has no commit; clean release check is impossible.")
        return
    if require_clean:
        status = run(["git", "status", "--porcelain"], capture=True)
        if status.stdout.strip():
            raise RuntimeError("Working tree is not clean:\n" + status.stdout)
    log = run(["git", "log", "--format=%an%x09%ae%x09%cn%x09%ce"], capture=True)
    for line in log.stdout.splitlines():
        author_name, author_email, committer_name, committer_email = line.split("\t")
        if (author_name, author_email) != ALLOWED_IDENTITY:
            raise RuntimeError(f"Unexpected author: {author_name} <{author_email}>")
        if (committer_name, committer_email) != ALLOWED_IDENTITY:
            raise RuntimeError(f"Unexpected committer: {committer_name} <{committer_email}>")
    messages = run(["git", "log", "--format=%B%x00"], capture=True).stdout
    trailer_name = "Co-authored" + "-by:"
    if trailer_name.casefold() in messages.casefold():
        raise RuntimeError("Commit history contains a co-author trailer.")


def compare_builds(first: Path, second: Path) -> list[str]:
    first_files = {path.name: path for path in first.iterdir() if path.is_file()}
    second_files = {path.name: path for path in second.iterdir() if path.is_file()}
    if set(first_files) != set(second_files):
        raise RuntimeError("Separate builds produced different asset names.")
    mismatches = [
        name
        for name in sorted(first_files)
        if file_digest(first_files[name]) != file_digest(second_files[name])
    ]
    if mismatches:
        raise RuntimeError("Non-deterministic release assets: " + ", ".join(mismatches))
    return sorted(first_files)


def clean_install(asset_dir: Path, version: str, scratch: Path) -> None:
    wheels = list(asset_dir.glob(f"exitpreflight-{version}-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("Expected exactly one wheel asset.")
    environment = scratch / "venv"
    venv.EnvBuilder(with_pip=True, clear=True).create(environment)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    install = subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", str(wheels[0])],
        capture_output=True,
        text=True,
        check=False,
    )
    if install.returncode:
        raise RuntimeError("Clean wheel install failed:\n" + install.stdout + install.stderr)
    for command in (
        [str(python), "-m", "exitpreflight", "--version"],
        [
            str(python),
            "-m",
            "exitpreflight",
            "audit",
            str(ROOT / "examples/portable-export"),
            "-o",
            str(scratch / "report"),
            "--strict",
        ],
    ):
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode:
            raise RuntimeError(
                "Clean-environment smoke failed:\n" + completed.stdout + completed.stderr
            )


def inspect_assets(asset_dir: Path, version: str) -> None:
    pyz = asset_dir / f"exitpreflight-{version}.pyz"
    source = asset_dir / f"exitpreflight-{version}-source.zip"
    checksums = asset_dir / "SHA256SUMS"
    for path in (pyz, source, checksums):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"Missing or empty release asset: {path.name}")
    with zipfile.ZipFile(pyz) as archive:
        names = set(archive.namelist())
        if "__main__.py" not in names or "exitpreflight/cli.py" not in names:
            raise RuntimeError("Zipapp is missing its entrypoint or CLI implementation.")
        if archive.testzip() is not None:
            raise RuntimeError("Zipapp CRC check failed.")
    lines = checksums.read_text(encoding="utf-8").splitlines()
    listed = {line.split("  ", 1)[1] for line in lines if "  " in line}
    actual = {path.name for path in asset_dir.iterdir() if path.is_file() and path != checksums}
    if listed != actual:
        raise RuntimeError("SHA256SUMS does not cover the exact release asset set.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    checks: list[dict[str, str]] = []

    def perform(name: str, action: Callable[[], None]) -> None:
        try:
            action()
        except Exception as exc:
            checks.append({"name": name, "status": "FAIL", "detail": str(exc)})
            raise
        checks.append({"name": name, "status": "PASS", "detail": "ok"})

    try:
        release_version = check_version()
        checks.append({"name": "version", "status": "PASS", "detail": release_version})
        perform("required-files", check_required_files)
        perform("git-history", lambda: check_git(args.require_clean))
        verify = run([sys.executable, "scripts/verify.py", "--skip-package"], capture=True)
        if verify.returncode:
            raise RuntimeError(verify.stdout + verify.stderr)
        checks.append({"name": "verification", "status": "PASS", "detail": "full gate"})
        with tempfile.TemporaryDirectory(prefix="exitpreflight-release-") as temporary:
            scratch = Path(temporary)
            first = scratch / "first"
            second = scratch / "second"
            for destination in (first, second):
                result = run(
                    [
                        sys.executable,
                        "scripts/package_release.py",
                        "--output",
                        str(destination),
                    ],
                    capture=True,
                )
                if result.returncode:
                    raise RuntimeError(result.stdout + result.stderr)
            names = compare_builds(first, second)
            checks.append(
                {"name": "deterministic-assets", "status": "PASS", "detail": ", ".join(names)}
            )
            inspect_assets(first, release_version)
            checks.append(
                {"name": "asset-inspection", "status": "PASS", "detail": "hashes and CRC"}
            )
            clean_install(first, release_version, scratch)
            checks.append({"name": "clean-install", "status": "PASS", "detail": "wheel and CLI"})
    except Exception as exc:
        if not checks or checks[-1]["status"] != "FAIL":
            checks.append({"name": "release-check", "status": "FAIL", "detail": str(exc)})
        result = {"ok": False, "checks": checks}
        print(
            json.dumps(result, ensure_ascii=False, indent=2)
            if args.json
            else f"RELEASE CHECK FAIL: {exc}"
        )
        return 1
    result = {"ok": True, "checks": checks}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for check in checks:
            print(f"{check['status']:4} {check['name']}: {check['detail']}")
        print("RELEASE CHECK PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
