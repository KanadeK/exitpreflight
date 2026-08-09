#!/usr/bin/env python3
"""Run the complete repository gate with real success and failure fixtures."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(
    command: list[str],
    *,
    expected: frozenset[int] = frozenset({0}),
    environment: dict[str, str] | None = None,
) -> None:
    print(f"\n>>> {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    if completed.returncode not in expected:
        wanted = ", ".join(str(item) for item in sorted(expected))
        raise RuntimeError(
            f"Command exited {completed.returncode}; expected one of: {wanted}: {' '.join(command)}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-package", action="store_true")
    args = parser.parse_args(argv)
    python = sys.executable
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(ROOT / "src") + (os.pathsep + existing if existing else "")

    run([python, "-m", "ruff", "format", "--check", "."], environment=environment)
    run([python, "-m", "ruff", "check", "."], environment=environment)
    run([python, "-m", "mypy", "src"], environment=environment)
    run([python, "-m", "compileall", "-q", "src", "tests", "scripts"], environment=environment)
    run([python, "-m", "coverage", "erase"], environment=environment)
    run(
        [python, "-m", "coverage", "run", "-m", "unittest", "discover", "-s", "tests", "-v"],
        environment=environment,
    )
    run([python, "-m", "coverage", "report", "-m"], environment=environment)
    run([python, "scripts/secret_scan.py"], environment=environment)
    run([python, "-m", "exitpreflight", "--version"], environment=environment)

    with tempfile.TemporaryDirectory(prefix="exitpreflight-verify-") as temporary:
        scratch = Path(temporary)
        run(
            [
                python,
                "-m",
                "exitpreflight",
                "audit",
                "examples/portable-export",
                "-o",
                str(scratch / "portable"),
                "--strict",
            ],
            environment=environment,
        )
        run(
            [
                python,
                "-m",
                "exitpreflight",
                "audit",
                "examples/risky-export",
                "-o",
                str(scratch / "risky"),
                "--strict",
            ],
            expected=frozenset({1}),
            environment=environment,
        )
        run(
            [
                python,
                "-m",
                "exitpreflight",
                "verify",
                "examples/portable-export",
                "--manifest",
                str(scratch / "portable" / "manifest.sha256"),
                "--strict-extra",
            ],
            environment=environment,
        )
        run(
            [python, "-m", "exitpreflight", "demo", "-o", str(scratch / "demo")],
            environment=environment,
        )
        if not args.skip_package:
            assets = scratch / "assets"
            run(
                [python, "scripts/package_release.py", "--output", str(assets)],
                environment=environment,
            )
            run([python, str(assets / "exitpreflight-0.1.0.pyz"), "--version"])
            run(
                [
                    python,
                    str(assets / "exitpreflight-0.1.0.pyz"),
                    "audit",
                    "examples/portable-export",
                    "-o",
                    str(scratch / "pyz-report"),
                    "--strict",
                ]
            )
    print("\nVERIFY PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"VERIFY FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
