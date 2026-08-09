from __future__ import annotations

import tarfile
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

from exitpreflight.source import ExportSource, SourceError


class SourceTests(unittest.TestCase):
    def test_directory_inventory_hash_and_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "hello.txt").write_bytes(b"hello\n")
            with ExportSource(root) as source:
                self.assertEqual(source.kind, "directory")
                self.assertEqual(source.names(), ["hello.txt"])
                self.assertEqual(source.read_text("hello.txt"), "hello\n")
                self.assertEqual(
                    source.hash("hello.txt"),
                    "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03",
                )

    def test_zip_flags_traversal_and_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "export.zip"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(archive, "w") as output:
                    output.writestr("../escape.txt", "bad")
                    output.writestr("safe.txt", "one")
                    output.writestr("safe.txt", "two")
            with ExportSource(archive) as source:
                codes = {finding.code for finding in source.structural_findings}
                self.assertIn("archive-unsafe-path", codes)
                self.assertIn("archive-duplicate-path", codes)
                self.assertEqual(source.names(), ["safe.txt"])

    def test_zip_flags_case_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "export.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("Readme.md", "one")
                output.writestr("README.md", "two")
            with ExportSource(archive) as source:
                self.assertIn(
                    "archive-case-collision",
                    {finding.code for finding in source.structural_findings},
                )

    def test_tar_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_file = root / "source.txt"
            source_file.write_text("tar content", encoding="utf-8")
            archive = root / "export.tar.gz"
            with tarfile.open(archive, "w:gz") as output:
                output.add(source_file, arcname="folder/source.txt")
            with ExportSource(archive) as source:
                self.assertEqual(source.kind, "tar")
                self.assertEqual(source.read_text("folder/source.txt"), "tar content")

    def test_unsupported_input_and_limits_fail_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            file_path = root / "plain.bin"
            file_path.write_bytes(b"not archive")
            with self.assertRaises(SourceError):
                with ExportSource(file_path):
                    pass
            (root / "one").write_text("1", encoding="utf-8")
            (root / "two").write_text("2", encoding="utf-8")
            with self.assertRaises(SourceError):
                with ExportSource(root, max_entries=1):
                    pass


if __name__ == "__main__":
    unittest.main()
