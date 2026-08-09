from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from exitpreflight.baseline import compare_reports
from exitpreflight.engine import audit_export
from exitpreflight.manifest import render_manifest, verify_manifest
from tests.helpers import create_slack_export, write_text


def fixed_time() -> datetime:
    return datetime(2026, 8, 8, tzinfo=UTC)


class ManifestBaselineTests(unittest.TestCase):
    def test_manifest_verifies_then_detects_tamper_and_extra(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_text(root, "export/a.txt", "one")
            report = audit_export(root / "export", clock=fixed_time)
            manifest = root / "manifest.sha256"
            manifest.write_text(render_manifest(report.files), encoding="utf-8")
            clean = verify_manifest(root / "export", manifest)
            self.assertTrue(clean.ok)
            write_text(root, "export/a.txt", "changed")
            write_text(root, "export/extra.txt", "extra")
            changed = verify_manifest(root / "export", manifest)
            self.assertFalse(changed.ok)
            self.assertEqual(changed.mismatched, ["a.txt"])
            self.assertEqual(changed.unexpected, ["extra.txt"])

    def test_compare_detects_missing_files_and_count_regressions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before_root = create_slack_export(root / "before")
            before = audit_export(before_root, clock=fixed_time)
            after_root = root / "after"
            write_text(after_root, "channels.json", '[{"id":"C1","name":"general"}]')
            write_text(after_root, "users.json", '[{"id":"U1","name":"alex"}]')
            after = audit_export(after_root, clock=fixed_time)
            comparison = compare_reports(before, after)
            self.assertEqual(comparison["summary"]["status"], "regressed")
            self.assertGreater(comparison["summary"]["missing_files"], 0)
            self.assertTrue(
                any(item["metric"] == "slack.messages" for item in comparison["regressions"])
            )

    def test_compare_stable_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_text(root, "a.txt", "same")
            report = audit_export(root, clock=fixed_time)
            comparison = compare_reports(report, report)
            self.assertEqual(comparison["summary"]["status"], "stable")


if __name__ == "__main__":
    unittest.main()
