from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from exitpreflight.cli import main
from tests.helpers import write_text


class CliTests(unittest.TestCase):
    def test_audit_strict_exit_codes_and_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_text(root, "export/page.md", "![missing](image.png)")
            output = root / "report"
            with redirect_stdout(io.StringIO()):
                normal = main(["audit", str(root / "export"), "-o", str(output)])
                strict = main(["audit", str(root / "export"), "-o", str(output), "--strict"])
            self.assertEqual(normal, 0)
            self.assertEqual(strict, 1)
            self.assertTrue((output / "exitpreflight-report.json").is_file())

    def test_verify_and_compare_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_text(root, "export/a.txt", "one")
            first = root / "first"
            second = root / "second"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["audit", str(root / "export"), "-o", str(first)]), 0)
                self.assertEqual(
                    main(
                        [
                            "verify",
                            str(root / "export"),
                            "--manifest",
                            str(first / "manifest.sha256"),
                        ]
                    ),
                    0,
                )
                self.assertEqual(main(["audit", str(root / "export"), "-o", str(second)]), 0)
                self.assertEqual(
                    main(
                        [
                            "compare",
                            str(first / "exitpreflight-report.json"),
                            str(second / "exitpreflight-report.json"),
                            "-o",
                            str(root / "compare"),
                            "--strict",
                        ]
                    ),
                    0,
                )
            self.assertTrue((root / "compare" / "exitpreflight-compare.json").is_file())

    def test_demo_and_invalid_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["demo", "-o", str(root / "demo")]), 0)
            self.assertTrue((root / "demo" / "report" / "exitpreflight-report.html").is_file())
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = main(["audit", str(root / "missing")])
            self.assertEqual(result, 2)
            self.assertIn("does not exist", stderr.getvalue())

    def test_compare_strict_reports_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_text(root, "export/a.txt", "one")
            with redirect_stdout(io.StringIO()):
                main(["audit", str(root / "export"), "-o", str(root / "before")])
            (root / "export" / "a.txt").unlink()
            write_text(root, "export/b.txt", "two")
            with redirect_stdout(io.StringIO()):
                main(["audit", str(root / "export"), "-o", str(root / "after")])
                result = main(
                    [
                        "compare",
                        str(root / "before" / "exitpreflight-report.json"),
                        str(root / "after" / "exitpreflight-report.json"),
                        "-o",
                        str(root / "comparison"),
                        "--strict",
                    ]
                )
            comparison = json.loads(
                (root / "comparison" / "exitpreflight-compare.json").read_text()
            )
            self.assertEqual(result, 1)
            self.assertEqual(comparison["summary"]["status"], "regressed")


if __name__ == "__main__":
    unittest.main()
