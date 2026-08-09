"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .baseline import compare_reports, load_report
from .demo import create_demo_export
from .engine import audit_export
from .manifest import verify_manifest
from .models import Severity, meets_threshold
from .reporting import write_comparison, write_report_bundle
from .source import SourceError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="exitpreflight",
        description="Audit SaaS exports before deleting, downgrading, or migrating an account.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    audit = commands.add_parser(
        "audit", help="Audit a directory or archive and write a report bundle."
    )
    audit.add_argument("input", help="Export directory, ZIP, TAR, TAR.GZ, or TGZ.")
    audit.add_argument("-o", "--output", default="exitpreflight-output", help="Report directory.")
    audit.add_argument(
        "--share-safe", action="store_true", help="Hash paths and external targets in reports."
    )
    audit.add_argument(
        "--strict", action="store_true", help="Exit 1 when a high/critical finding exists."
    )
    audit.add_argument(
        "--fail-on",
        choices=["none", "critical", "high", "medium", "low"],
        default="none",
        help="Finding severity that makes the command exit 1 (default: none).",
    )

    compare = commands.add_parser("compare", help="Compare two ExitPreflight JSON reports.")
    compare.add_argument("before", help="Earlier exitpreflight-report.json.")
    compare.add_argument("after", help="Later exitpreflight-report.json.")
    compare.add_argument("-o", "--output", default="exitpreflight-compare")
    compare.add_argument(
        "--strict", action="store_true", help="Exit 1 on missing files or count regressions."
    )

    verify = commands.add_parser("verify", help="Verify an export against manifest.sha256.")
    verify.add_argument("input", help="Export directory or archive.")
    verify.add_argument("--manifest", required=True, help="Manifest emitted by an earlier audit.")
    verify.add_argument(
        "--strict-extra", action="store_true", help="Treat unlisted files as a failure."
    )

    demo = commands.add_parser("demo", help="Create and audit a synthetic risky export.")
    demo.add_argument("-o", "--output", default="exitpreflight-demo")
    return parser


def _audit(args: argparse.Namespace) -> int:
    report = audit_export(args.input)
    paths = write_report_bundle(report, args.output, share_safe=args.share_safe)
    print(
        f"ExitPreflight: {report.status} | score {report.readiness_score}/100 | "
        f"{len(report.findings)} findings | {len(report.files)} files"
    )
    print(f"Reports: {Path(args.output).resolve()}")
    for path in paths:
        print(f"  - {path.name}")
    threshold_name = "high" if args.strict else args.fail_on
    if threshold_name == "none":
        return 0
    threshold = Severity(threshold_name)
    return 1 if any(meets_threshold(item.severity, threshold) for item in report.findings) else 0


def _compare(args: argparse.Namespace) -> int:
    value = compare_reports(load_report(args.before), load_report(args.after))
    write_comparison(value, args.output)
    summary = value["summary"]
    print(
        f"ExitPreflight compare: {summary['status']} | missing {summary['missing_files']} | "
        f"metric regressions {summary['metric_regressions']}"
    )
    return 1 if args.strict and summary["status"] == "regressed" else 0


def _verify(args: argparse.Namespace) -> int:
    result = verify_manifest(args.input, args.manifest)
    print(
        f"ExitPreflight verify: checked {result.checked} | missing {len(result.missing)} | "
        f"mismatched {len(result.mismatched)} | unexpected {len(result.unexpected)}"
    )
    for label, paths in (
        ("missing", result.missing),
        ("mismatched", result.mismatched),
        ("unexpected", result.unexpected),
    ):
        for path in paths:
            print(f"  {label}: {path}")
    if not result.ok or (args.strict_extra and result.unexpected):
        return 1
    return 0


def _demo(args: argparse.Namespace) -> int:
    output = Path(args.output)
    export = create_demo_export(output / "synthetic-export")
    report = audit_export(export)
    write_report_bundle(report, output / "report")
    print(f"Synthetic export: {export.resolve()}")
    print(f"Report: {(output / 'report' / 'exitpreflight-report.html').resolve()}")
    print(f"Expected risky result: {report.status} ({report.readiness_score}/100)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            return _audit(args)
        if args.command == "compare":
            return _compare(args)
        if args.command == "verify":
            return _verify(args)
        if args.command == "demo":
            return _demo(args)
    except (SourceError, OSError, ValueError) as exc:
        print(f"exitpreflight: error: {exc}", file=sys.stderr)
        return 2
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
