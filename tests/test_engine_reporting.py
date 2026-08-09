from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from exitpreflight.demo import create_demo_export
from exitpreflight.engine import audit_export
from exitpreflight.reporting import render_html, report_dict, write_report_bundle


class EngineReportingTests(unittest.TestCase):
    def test_demo_is_real_multi_adapter_risky_export(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            export = create_demo_export(Path(temporary) / "export")
            report = audit_export(
                export,
                clock=lambda: datetime(2026, 8, 8, tzinfo=UTC),
            )
            self.assertEqual(set(report.adapters), {"generic", "slack", "gmail", "notion"})
            self.assertEqual(report.generated_at, "2026-08-08T00:00:00Z")
            self.assertEqual(report.status, "needs-attention")
            self.assertLess(report.readiness_score, 100)
            self.assertGreater(len(report.files), 5)

    def test_share_safe_reports_hash_paths_and_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            export = create_demo_export(Path(temporary) / "private-name")
            report = audit_export(export)
            value = report_dict(report, share_safe=True)
            serialized = json.dumps(value)
            self.assertNotIn("private-name", serialized)
            self.assertNotIn("drive.google.com", serialized)
            self.assertTrue(value["input"]["label"].startswith("input-"))

    def test_html_escapes_user_controlled_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "export.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("<script>alert(1)</script>.txt", "")
            report = audit_export(archive)
            rendered = render_html(report.to_dict())
            self.assertNotIn("<script>alert(1)</script>", rendered)
            self.assertIn("&lt;script&gt;", rendered)

    def test_report_bundle_writes_all_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            export = create_demo_export(root / "export")
            paths = write_report_bundle(audit_export(export), root / "report")
            self.assertEqual(len(paths), 5)
            self.assertTrue(all(path.is_file() for path in paths))
            value = json.loads((root / "report" / "exitpreflight-report.json").read_text())
            self.assertEqual(value["schema_version"], "1.0")


if __name__ == "__main__":
    unittest.main()
