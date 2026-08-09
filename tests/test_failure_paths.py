from __future__ import annotations

import io
import runpy
import sys
import tarfile
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from exitpreflight.adapters import AuditAccumulator
from exitpreflight.engine import audit_export
from exitpreflight.manifest import parse_manifest
from exitpreflight.models import Finding, Severity
from exitpreflight.source import ExportSource, SourceError
from tests.helpers import write_text


class FailurePathTests(unittest.TestCase):
    def test_accumulator_caps_repeated_findings(self) -> None:
        accumulator = AuditAccumulator(max_findings_per_code=1)
        finding = Finding("repeat", "Repeated", Severity.HIGH, "same")
        accumulator.add(finding)
        accumulator.add(finding)
        self.assertEqual(len(accumulator.findings), 1)
        self.assertEqual(accumulator.metrics["suppressed.repeat"], 1)

    def test_invalid_slack_json_is_a_high_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_text(root, "channels.json", "{not-json")
            write_text(root, "users.json", "[]")
            report = audit_export(root)
            self.assertIn("invalid-json", {finding.code for finding in report.findings})

    def test_generic_skips_large_text_and_ignores_safe_references(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_text(
                root,
                "docs/page.md",
                "[Local](asset.txt) [Anchor](#part) [Web](https://example.com)\n",
            )
            write_text(root, "docs/asset.txt", "present")
            (root / "large.txt").write_bytes(b"x" * (8 * 1024 * 1024 + 1))
            report = audit_export(root)
            self.assertEqual(report.metrics["text.skipped_large"], 1)
            self.assertNotIn("missing-local-target", {item.code for item in report.findings})

    def test_mbox_streams_multiple_messages_and_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            message = (
                "From first@example.com Sat Aug  1 00:00:00 2026\n"
                "From: first@example.com\nSubject: Attachment\nX-Gmail-Labels: Inbox\n"
                "MIME-Version: 1.0\nContent-Type: multipart/mixed; boundary=demo\n\n"
                "--demo\nContent-Type: text/plain; charset=utf-8\n\nLocal body\n"
                "--demo\nContent-Type: application/octet-stream\n"
                "Content-Disposition: attachment; filename=proof.txt\n"
                "Content-Transfer-Encoding: base64\n\ncHJvb2Y=\n--demo--\n"
                "From second@example.com Sat Aug  1 00:01:00 2026\n"
                "From: second@example.com\nSubject: Second\nX-Gmail-Labels: Sent\n\nDone\n"
            )
            write_text(root, "Mail/messages.mbox", message)
            report = audit_export(root)
            self.assertEqual(report.metrics["gmail.messages"], 2)
            self.assertEqual(report.metrics["gmail.attachments"], 1)

    def test_extreme_zip_compression_and_unsafe_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "export.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
                output.writestr("huge.txt", b"0" * (2 * 1024 * 1024))
                output.writestr("../escape.txt", "unsafe")
            report = audit_export(archive)
            codes = {finding.code for finding in report.findings}
            self.assertIn("archive-extreme-compression", codes)
            self.assertIn("archive-unsafe-path", codes)
            self.assertEqual(report.status, "blocked")

    def test_tar_link_is_reported_without_following(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "export.tar"
            with tarfile.open(archive, "w") as output:
                info = tarfile.TarInfo("outside-link")
                info.type = tarfile.SYMTYPE
                info.linkname = "../../private"
                output.addfile(info)
            with ExportSource(archive) as source:
                self.assertIn(
                    "archive-link-entry",
                    {finding.code for finding in source.structural_findings},
                )

    def test_text_limit_and_invalid_manifests_raise_source_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "large.txt").write_bytes(b"abc")
            with ExportSource(root) as source:
                with self.assertRaises(SourceError):
                    source.read_bytes("large.txt", limit=2)
            invalid = root / "invalid.sha256"
            invalid.write_text("not a manifest\n", encoding="utf-8")
            with self.assertRaises(SourceError):
                parse_manifest(invalid)
            duplicate = root / "duplicate.sha256"
            duplicate.write_text(("0" * 64 + "  a.txt\n") * 2, encoding="utf-8")
            with self.assertRaises(SourceError):
                parse_manifest(duplicate)

    def test_module_entrypoint_and_medium_review_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_text(root, "docs/page.md", "[case](../ASSET.txt)")
            write_text(root, "asset.txt", "present")
            report = audit_export(root)
            self.assertEqual(report.status, "review")
        with patch.object(sys, "argv", ["exitpreflight", "--version"]):
            with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as raised:
                runpy.run_module("exitpreflight", run_name="__main__")
        self.assertEqual(raised.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
