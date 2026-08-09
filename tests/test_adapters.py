from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from exitpreflight.engine import audit_export
from tests.helpers import create_gmail_export, create_slack_export, write_text


class AdapterTests(unittest.TestCase):
    def test_generic_finds_broken_case_and_cloud_references(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_text(root, "docs/page.md", "[Good](../Asset.txt)\n[Missing](lost.pdf)\n")
            write_text(root, "asset.txt", "content\n")
            write_text(root, "cloud.html", '<a href="https://dropbox.com/s/demo/file">File</a>')
            report = audit_export(root)
            codes = {finding.code for finding in report.findings}
            self.assertIn("local-link-case-mismatch", codes)
            self.assertIn("missing-local-target", codes)
            self.assertIn("cloud-link-dependency", codes)
            self.assertEqual(report.metrics["links.broken_local"], 1)

    def test_slack_counts_messages_and_flags_link_only_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = audit_export(create_slack_export(Path(temporary), missing_user=True))
            self.assertIn("slack", report.adapters)
            self.assertEqual(report.metrics["slack.messages"], 1)
            self.assertEqual(report.metrics["slack.file_links"], 1)
            codes = {finding.code for finding in report.findings}
            self.assertIn("slack-file-link-only", codes)
            self.assertIn("slack-user-reference-missing", codes)

    def test_slack_missing_channel_folder_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_text(root, "channels.json", '[{"id":"C1","name":"general"}]')
            write_text(root, "users.json", "[]")
            report = audit_export(root)
            self.assertIn(
                "slack-channel-folder-missing", {finding.code for finding in report.findings}
            )

    def test_gmail_mbox_preserves_counts_and_flags_cloud_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = audit_export(create_gmail_export(Path(temporary)))
            self.assertIn("gmail", report.adapters)
            self.assertEqual(report.metrics["gmail.messages"], 1)
            self.assertEqual(report.metrics["gmail.messages_with_labels"], 1)
            self.assertIn(
                "gmail-cloud-only-reference", {finding.code for finding in report.findings}
            )
            self.assertNotIn("takeout-browser-missing", {item.code for item in report.findings})

    def test_gmail_missing_labels_and_browser_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_gmail_export(root, labels=False)
            (root / "Takeout" / "archive_browser.html").unlink()
            report = audit_export(root)
            codes = {finding.code for finding in report.findings}
            self.assertIn("gmail-labels-missing", codes)
            self.assertIn("takeout-browser-missing", codes)

    def test_notion_detection_and_duplicate_titles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_text(root, "notion/Plan 0123456789abcdef0123456789abcdef.md", "# Plan")
            write_text(root, "notion/Plan fedcba9876543210fedcba9876543210.md", "# Plan 2")
            write_text(root, "notion/Tasks 0123456789abcdef0123456789abcdef.csv", "Name\nTask")
            report = audit_export(root)
            self.assertIn("notion", report.adapters)
            self.assertEqual(report.metrics["notion.pages"], 2)
            self.assertEqual(report.metrics["notion.databases"], 1)
            self.assertIn("notion-duplicate-title", {item.code for item in report.findings})


if __name__ == "__main__":
    unittest.main()
